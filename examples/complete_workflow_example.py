"""
Complete Documentation Workflow Example
=======================================

This example demonstrates a complete documentation workflow that:
1. Analyzes a repository structure
2. Generates API documentation
3. Creates or updates README
4. Saves detailed metrics about time, cost, and tokens used
"""
import os
import sys
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
import logging
import csv
from typing import Dict, Any, Optional, List, Tuple

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.utils.repo_scanner import RepoScanner
from src.agents import (
    AgentConfig,
    RepoAnalyzer,
    RepoStructureInput,
    APIDocGenerator,
    APIDocInput,
    ReadmeGenerator,
    ReadmeInput
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class WorkflowMetrics:
    """Track metrics for different workflows with file-based persistence"""
    def __init__(self, output_dir: str, workflow_id: Optional[str] = None):
        self.start_time = time.time()
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.total_cost = 0.0
        self.total_tokens = 0
        
        # Generate a unique ID for this workflow run
        self.workflow_id = workflow_id or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Set up output directory
        self.output_dir = os.path.join(output_dir, self.workflow_id)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up metrics log files
        self.summary_file = os.path.join(self.output_dir, "metrics_summary.json")
        self.csv_log = os.path.join(self.output_dir, "metrics_log.csv")
        self.detailed_log = os.path.join(self.output_dir, "detailed_log.txt")
        
        # Initialize CSV log with headers
        with open(self.csv_log, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Timestamp', 'Workflow', 'Action', 'Duration', 'Cost', 'Tokens'])
        
        # Initialize detailed log
        with open(self.detailed_log, 'w') as f:
            f.write(f"Workflow Run ID: {self.workflow_id}\n")
            f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
        logger.info(f"Metrics will be saved to: {self.output_dir}")
    
    def start_workflow(self, name: str):
        """Start timing a workflow"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.workflows[name] = {
            'start_time': time.time(),
            'timestamp': timestamp,
            'cost': 0.0,
            'tokens': 0
        }
        
        # Log to detailed log
        with open(self.detailed_log, 'a') as f:
            f.write(f"[{timestamp}] STARTED: {name}\n")
        
        # Log to CSV
        with open(self.csv_log, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([timestamp, name, 'START', 0, 0, 0])
    
    def end_workflow(self, name: str, cost: float = 0.0, tokens: int = 0, metadata: Optional[Dict[str, Any]] = None):
        """End timing a workflow and record metrics"""
        if name in self.workflows:
            end_time = time.time()
            duration = end_time - self.workflows[name]['start_time']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.workflows[name].update({
                'end_time': end_time,
                'end_timestamp': timestamp,
                'duration': duration,
                'cost': cost,
                'tokens': tokens,
                'metadata': metadata or {}
            })
            
            self.total_cost += cost
            self.total_tokens += tokens
            
            # Log to detailed log
            with open(self.detailed_log, 'a') as f:
                f.write(f"[{timestamp}] COMPLETED: {name}\n")
                f.write(f"  Duration: {duration:.2f} seconds\n")
                f.write(f"  Cost: ${cost:.4f}\n")
                f.write(f"  Tokens: {tokens:,}\n")
                if metadata:
                    f.write("  Metadata:\n")
                    for key, value in metadata.items():
                        f.write(f"    {key}: {value}\n")
                f.write("\n")
            
            # Log to CSV
            with open(self.csv_log, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([timestamp, name, 'END', duration, cost, tokens])
    
    def log_event(self, workflow: str, event: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an event within a workflow"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Log to detailed log
        with open(self.detailed_log, 'a') as f:
            f.write(f"[{timestamp}] EVENT: {workflow} - {event}\n")
            if metadata:
                for key, value in metadata.items():
                    f.write(f"    {key}: {value}\n")
            f.write("\n")
        
        # Log to CSV
        with open(self.csv_log, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([timestamp, workflow, event, 0, 0, 0])
    
    def save_summary(self):
        """Save a final summary of all metrics to JSON"""
        total_duration = time.time() - self.start_time
        
        summary = {
            "workflow_id": self.workflow_id,
            "start_time": datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_duration": total_duration,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "workflows": self.workflows
        }
        
        with open(self.summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Also append to the detailed log
        with open(self.detailed_log, 'a') as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("WORKFLOW SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Total Duration: {total_duration:.2f} seconds\n")
            f.write(f"Total Cost: ${self.total_cost:.4f}\n")
            f.write(f"Total Tokens: {self.total_tokens:,}\n\n")
            
            f.write("Individual Workflows:\n")
            f.write("-" * 80 + "\n")
            for name, metrics in self.workflows.items():
                if 'duration' in metrics:
                    f.write(f"{name}:\n")
                    f.write(f"  Duration: {metrics['duration']:.2f} seconds\n")
                    f.write(f"  Cost: ${metrics['cost']:.4f}\n")
                    f.write(f"  Tokens: {metrics['tokens']:,}\n\n")
        
        logger.info(f"Metrics summary saved to: {self.summary_file}")
        return summary
    
    def get_summary(self) -> str:
        """Generate a summary of all workflow metrics"""
        total_duration = time.time() - self.start_time
        summary = [
            f"\nWorkflow Metrics Summary (ID: {self.workflow_id}):",
            "=" * 80,
            f"Total Duration: {total_duration:.2f} seconds",
            f"Total Cost: ${self.total_cost:.4f}",
            f"Total Tokens: {self.total_tokens:,}",
            f"Results saved to: {self.output_dir}",
            "\nIndividual Workflows:",
            "-" * 80
        ]
        
        for name, metrics in self.workflows.items():
            if 'duration' in metrics:
                summary.append(
                    f"{name}:"
                    f"\n  Duration: {metrics['duration']:.2f} seconds"
                    f"\n  Cost: ${metrics['cost']:.4f}"
                    f"\n  Tokens: {metrics['tokens']:,}"
                )
        
        return "\n".join(summary)


def get_repo_api_files(repo_path: str) -> List[Tuple[str, str]]:
    """Find API-related files in the repository"""
    api_files = []
    api_extensions = ['.py', '.js', '.ts']
    api_patterns = ['api', 'route', 'endpoint', 'controller', 'view']
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if any(file.endswith(ext) for ext in api_extensions):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check if file path or name contains API patterns
                if any(pattern in file.lower() or pattern in rel_path.lower() for pattern in api_patterns):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        api_files.append((rel_path, content))
                    except Exception as e:
                        logger.error(f"Error reading {file_path}: {e}")
    
    return api_files


def run_complete_workflow(repo_path: str, output_dir: str = "output"):
    """Run a complete workflow with full metrics tracking"""
    # Create absolute paths
    repo_path = os.path.abspath(repo_path)
    output_dir = os.path.join(repo_path, "examples", output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize metrics
    metrics = WorkflowMetrics(output_dir)
    
    # Configure agents
    agent_config = AgentConfig()
    
    try:
        # Step 1: Scan and analyze repository
        metrics.start_workflow("repository_scanning")
        logger.info(f"Starting repository analysis at: {repo_path}")
        
        # Initialize repository scanner
        scanner = RepoScanner(repo_path)
        
        # Scan the repository
        logger.info("Scanning repository files...")
        files = scanner.scan_files()
        logger.info(f"Found {len(files)} files")
        
        # Record file stats as metadata
        extension_breakdown = scanner.get_file_extension_breakdown(files)
        file_stats = {
            "total_files": len(files),
            "top_extensions": dict(sorted(extension_breakdown.items(), 
                                          key=lambda x: x[1], 
                                          reverse=True)[:5])
        }
        
        # Detect frameworks
        logger.info("Detecting frameworks...")
        frameworks = scanner.detect_framework_patterns(files)
        
        # Identify documentation files
        doc_files = scanner.identify_documentation_files(files)
        logger.info(f"Found {len(doc_files)} documentation files")
        
        # Identify entry points
        entry_points = scanner.identify_entry_points(files)
        logger.info(f"Found {len(entry_points)} potential entry points")
        
        # Complete repository scanning workflow with metadata
        metrics.end_workflow("repository_scanning", metadata=file_stats)
        
        # Step 2: Analyze repository structure
        metrics.start_workflow("repository_analysis")
        logger.info("Analyzing repository structure...")
        
        # Initialize repository analyzer
        repo_analyzer = RepoAnalyzer(config=agent_config)
        
        # Start time for just the LLM call
        llm_start = time.time()
        
        # Analyze repo structure (this is where the AI model is called)
        repo_structure = repo_analyzer.analyze_repo_structure(
            RepoStructureInput(
                repo_path=repo_path,
                files=files
            )
        )
        
        # Calculate LLM time and estimated cost
        llm_duration = time.time() - llm_start
        # Estimate cost based on token count (adjust these values based on your model)
        estimated_input_tokens = 3000  # Approximate input tokens
        estimated_output_tokens = 2000  # Approximate output tokens
        input_token_cost = 0.00001  # Cost per input token (adjust for your model)
        output_token_cost = 0.00003  # Cost per output token (adjust for your model)
        estimated_cost = (estimated_input_tokens * input_token_cost) + (estimated_output_tokens * output_token_cost)
        total_tokens = estimated_input_tokens + estimated_output_tokens
        
        # Log event with important stats
        metrics.log_event("repository_analysis", "LLM_CALL_COMPLETED", {
            "duration": llm_duration,
            "estimated_cost": estimated_cost,
            "estimated_tokens": total_tokens
        })
        
        # Save repository analysis results
        analysis_results = {
            "summary": repo_structure.summary,
            "technologies": list(repo_structure.technologies),
            "architecture_pattern": repo_structure.architecture_pattern,
            "components": [{"name": c.name, "description": c.description} for c in repo_structure.components]
        }
        
        analysis_file = os.path.join(metrics.output_dir, "repo_analysis.json")
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, indent=2)
        
        # Generate repository structure tree
        directory_tree = create_directory_tree(repo_path)
        tree_file = os.path.join(metrics.output_dir, "directory_tree.txt")
        with open(tree_file, "w", encoding="utf-8") as f:
            f.write(directory_tree)
        
        # Identify documentation needs
        doc_needs = repo_analyzer.identify_documentation_needs(repo_structure)
        doc_needs_file = os.path.join(metrics.output_dir, "documentation_needs.json")
        with open(doc_needs_file, "w", encoding="utf-8") as f:
            json.dump({k: list(v) for k, v in doc_needs.items()}, f, indent=2)
        
        # Complete repository analysis with metrics
        metrics.end_workflow("repository_analysis", cost=estimated_cost, 
                             tokens=total_tokens, 
                             metadata={"analysis_saved_to": analysis_file})
        
        # Step 3: API Documentation Generation (if applicable)
        metrics.start_workflow("api_documentation")
        logger.info("Searching for API files...")
        
        # Find API files
        api_files = get_repo_api_files(repo_path)
        
        if api_files:
            logger.info(f"Found {len(api_files)} potential API files")
            
            # Initialize API documentation generator
            api_doc_generator = APIDocGenerator(config=agent_config)
            
            # Start time for just the LLM call
            llm_start = time.time()
            
            # Generate API documentation
            api_doc_input = APIDocInput(
                api_files=api_files,
                project_description=repo_structure.summary,
                directory_structure=directory_tree,
                technologies=list(repo_structure.technologies),
                authentication_details={},  # Add if available
                dependencies=[],  # Add if available
                target_audience="Developers"
            )
            
            api_docs = api_doc_generator.generate_api_docs(api_doc_input)
            
            # Calculate LLM time and estimated cost (API docs generation usually uses more tokens)
            llm_duration = time.time() - llm_start
            # Estimate cost based on token count (adjust these values based on your model)
            api_input_tokens = 5000  # Approximate input tokens
            api_output_tokens = 3000  # Approximate output tokens
            api_cost = (api_input_tokens * input_token_cost) + (api_output_tokens * output_token_cost)
            api_total_tokens = api_input_tokens + api_output_tokens
            
            # Save API documentation
            api_doc_file = os.path.join(metrics.output_dir, "api_documentation.md")
            with open(api_doc_file, "w", encoding="utf-8") as f:
                f.write(api_docs.content)
            
            # Generate OpenAPI spec
            openapi_spec = api_doc_generator.convert_to_openapi(api_docs)
            openapi_file = os.path.join(metrics.output_dir, "openapi_spec.json")
            with open(openapi_file, "w", encoding="utf-8") as f:
                json.dump(openapi_spec, f, indent=2)
            
            # Complete API documentation with metrics
            metrics.end_workflow("api_documentation", cost=api_cost, 
                                 tokens=api_total_tokens,
                                 metadata={"api_docs_saved_to": api_doc_file,
                                          "openapi_spec_saved_to": openapi_file})
        else:
            logger.info("No API files found, skipping API documentation generation")
            metrics.end_workflow("api_documentation", metadata={"status": "skipped"})
        
        # Step 4: README Generation
        metrics.start_workflow("readme_generation")
        logger.info("Generating README...")
        
        # Initialize README generator
        readme_generator = ReadmeGenerator(config=agent_config)
        
        # Check for existing README
        readme_path = os.path.join(repo_path, "README.md")
        existing_readme = None
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                existing_readme = f.read()
            logger.info("Existing README.md found")
        
        # Prepare README input with enhanced context
        repo_name = os.path.basename(os.path.abspath(repo_path))
        
        # Create enhanced input with context from repository analysis
        enhanced_input = ReadmeInput(
            repo_name=repo_name,
            repo_description=repo_structure.summary,
            repo_structure=repo_structure,
            directory_structure=directory_tree,
            technologies=repo_structure.technologies,
            architecture_pattern=repo_structure.architecture_pattern,
            components=[(c.name, c.description) for c in repo_structure.components],
            entry_points=entry_points,
            documentation_needs=doc_needs,
            framework_info=frameworks,
            file_statistics={
                "total_files": len(files),
                "extensions": extension_breakdown,
                "doc_files": len(doc_files)
            }
        )
        
        # Start time for just the LLM call
        llm_start = time.time()
        
        if existing_readme:
            # Update existing README
            enhanced_input.existing_readme = existing_readme
            readme_result = readme_generator.update_readme(enhanced_input)
        else:
            # Generate new README
            readme_result = readme_generator.generate_readme(enhanced_input)
        
        # Calculate LLM time and estimated cost
        llm_duration = time.time() - llm_start
        readme_input_tokens = 4000
        readme_output_tokens = 2500
        readme_cost = (readme_input_tokens * input_token_cost) + (readme_output_tokens * output_token_cost)
        readme_total_tokens = readme_input_tokens + readme_output_tokens
        
        # Save the generated README
        output_readme = os.path.join(metrics.output_dir, "README.md")
        with open(output_readme, "w", encoding="utf-8") as f:
            f.write(readme_result.markdown)
        
        # Complete README generation with metrics
        metrics.end_workflow("readme_generation", cost=readme_cost, 
                            tokens=readme_total_tokens,
                            metadata={"readme_saved_to": output_readme})
        
        # Step 5: Save all metrics and generate visualization
        logger.info("Workflow completed successfully!")
        metrics_summary = metrics.save_summary()
        
        # Generate a simple visualization (ASCII chart of costs)
        visualize_metrics(metrics, os.path.join(metrics.output_dir, "metrics_visualization.txt"))
        
        # Print summary to console
        logger.info(metrics.get_summary())
        
        return metrics.output_dir, metrics_summary
        
    except Exception as e:
        logger.error(f"Error in workflow: {str(e)}", exc_info=True)
        # Still try to save metrics even if we had an error
        metrics.log_event("error", "workflow_error", {"error": str(e)})
        metrics.save_summary()
        raise

def visualize_metrics(metrics: WorkflowMetrics, output_file: str):
    """Create a simple ASCII visualization of metrics"""
    # Calculate max width for cost bar (50 characters)
    max_cost = max([w.get('cost', 0) for w in metrics.workflows.values()] or [0.001])
    max_width = 50
    
    lines = [
        "Workflow Metrics Visualization",
        "=" * 80,
        "",
        "Cost Distribution ($):",
        "-" * 80,
    ]
    
    # Add cost bars
    for name, data in sorted(metrics.workflows.items(), key=lambda x: x[1].get('cost', 0), reverse=True):
        if 'cost' in data:
            cost = data['cost']
            bar_width = int((cost / max_cost) * max_width)
            bar = "█" * bar_width
            lines.append(f"{name.ljust(25)} | {bar} ${cost:.4f}")
    
    lines.append("")
    lines.append("Duration Distribution (seconds):")
    lines.append("-" * 80)
    
    # Calculate max width for duration bar
    max_duration = max([w.get('duration', 0) for w in metrics.workflows.values()] or [0.001])
    
    # Add duration bars
    for name, data in sorted(metrics.workflows.items(), key=lambda x: x[1].get('duration', 0), reverse=True):
        if 'duration' in data:
            duration = data['duration']
            bar_width = int((duration / max_duration) * max_width)
            bar = "█" * bar_width
            lines.append(f"{name.ljust(25)} | {bar} {duration:.2f}s")
    
    # Save to file
    with open(output_file, 'w') as f:
        f.write("\n".join(lines))

def create_directory_tree(repo_path, max_depth=3, excluded_dirs=None):
    """
    Create a structured directory tree representation of the repository
    with conventional top-level directories highlighted
    """
    if excluded_dirs is None:
        excluded_dirs = ['.git', '.pytest_cache', '__pycache__', 'node_modules', 'venv', '.venv', 'env']
    
    # Define conventional top-level directories with descriptions
    conventional_dirs = {
        'src': 'Source code',
        'tests': 'Test files',
        'docs': 'Documentation files',
        'examples': 'Example code and usage',
        'scripts': 'Utility scripts',
        'config': 'Configuration files',
        'build': 'Build artifacts',
        'dist': 'Distribution files',
    }
    
    def _generate_tree(path, prefix='', depth=0):
        if depth > max_depth:
            return prefix + "...\n"
        
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            return ""
        
        result = ""
        try:
            dirs = []
            files = []
            
            for item in path_obj.iterdir():
                if item.is_dir():
                    if item.name not in excluded_dirs:
                        dirs.append(item)
                else:
                    files.append(item)
            
            # Sort directories and files
            dirs.sort(key=lambda x: x.name.lower())
            files.sort(key=lambda x: x.name.lower())
            
            # Process directories first
            for i, dir_path in enumerate(dirs):
                is_last = (i == len(dirs) - 1 and len(files) == 0)
                
                # Add description for conventional directories
                dir_name = dir_path.name
                description = f" - {conventional_dirs[dir_name]}" if dir_name in conventional_dirs else ""
                
                if is_last:
                    result += f"{prefix}└── {dir_name}/{description}\n"
                    result += _generate_tree(dir_path, prefix + "    ", depth + 1)
                else:
                    result += f"{prefix}├── {dir_name}/{description}\n"
                    result += _generate_tree(dir_path, prefix + "│   ", depth + 1)
            
            # Then process files (limited to important ones at higher levels)
            important_extensions = ['.md', '.py', '.js', '.ts', '.json', '.yml', '.yaml', '.toml']
            files_truncated = False
            
            if depth <= 1:  # At top level, show all files
                file_subset = files
            else:  # At deeper levels, only show important files
                file_subset = [f for f in files if any(f.name.endswith(ext) for ext in important_extensions)]
                
                # Limit number of files shown at deeper levels
                if len(file_subset) > 5 and depth > 2:
                    file_subset = file_subset[:5]
                    omitted = len(files) - 5
                    files_truncated = True
            
            for i, file_path in enumerate(file_subset):
                is_last = (i == len(file_subset) - 1)
                
                if is_last and not files_truncated:
                    result += f"{prefix}└── {file_path.name}\n"
                else:
                    result += f"{prefix}├── {file_path.name}\n"
            
            if files_truncated:
                result += f"{prefix}└── ... ({omitted} more files)\n"
                
        except (PermissionError, OSError):
            result += f"{prefix}└── (Permission denied)\n"
        
        return result
    
    # Get repository name
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    # Create the tree starting with the repository name
    return f"{repo_name}/\n" + _generate_tree(repo_path)

if __name__ == "__main__":
    # If a path is provided as an argument, use it; otherwise use the current directory
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        repo_path = os.getcwd()
    
    # Run the complete workflow
    output_dir, metrics = run_complete_workflow(repo_path)
    
    # Print final summary
    print(f"\nResults saved to: {output_dir}")
    print(f"Total Cost: ${metrics['total_cost']:.4f}")
    print(f"Total Duration: {metrics['total_duration']:.2f} seconds") 