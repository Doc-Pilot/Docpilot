"""
Repository Analysis and Documentation Example
============================================

This example demonstrates how to analyze a repository structure and generate documentation
using DocPilot's agents with enhanced context for better results.
"""
# Importing Dependencies
import os
import sys
from pathlib import Path
import json
import time
from datetime import datetime
from typing import Dict, Any
import logging

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.utils.repo_scanner import RepoScanner
from src.agents import (
    AgentConfig,
    RepoAnalyzer,
    RepoStructureInput,
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
    """Track metrics for different workflows"""
    def __init__(self):
        self.start_time = time.time()
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.total_cost = 0.0
        self.total_tokens = 0
    
    def start_workflow(self, name: str):
        """Start timing a workflow"""
        self.workflows[name] = {
            'start_time': time.time(),
            'cost': 0.0,
            'tokens': 0
        }
    
    def end_workflow(self, name: str, cost: float = 0.0, tokens: int = 0):
        """End timing a workflow and record metrics"""
        if name in self.workflows:
            end_time = time.time()
            duration = end_time - self.workflows[name]['start_time']
            self.workflows[name].update({
                'end_time': end_time,
                'duration': duration,
                'cost': cost,
                'tokens': tokens
            })
            self.total_cost += cost
            self.total_tokens += tokens
    
    def get_summary(self) -> str:
        """Generate a summary of all workflow metrics"""
        total_duration = time.time() - self.start_time
        summary = [
            "\nWorkflow Metrics Summary:",
            "=" * 50,
            f"Total Duration: {total_duration:.2f} seconds",
            f"Total Cost: ${self.total_cost:.4f}",
            f"Total Tokens: {self.total_tokens:,}",
            "\nIndividual Workflows:",
            "-" * 50
        ]
        
        for name, metrics in self.workflows.items():
            summary.append(
                f"{name}:"
                f"\n  Duration: {metrics['duration']:.2f} seconds"
                f"\n  Cost: ${metrics['cost']:.4f}"
                f"\n  Tokens: {metrics['tokens']:,}"
            )
        
        return "\n".join(summary)

def analyze_repository(repo_path: str):
    """Analyze a repository and generate documentation with enhanced context"""
    metrics = WorkflowMetrics()
    logger.info(f"Starting repository analysis at: {repo_path}")
    
    # Configure agents
    agent_config = AgentConfig()
    
    # Initialize repository scanner
    metrics.start_workflow("repository_scanning")
    scanner = RepoScanner(repo_path)
    
    # Scan the repository
    logger.info("Scanning repository files...")
    files = scanner.scan_files()
    logger.info(f"Found {len(files)} files")
    
    # Analyze file extensions
    extension_breakdown = scanner.get_file_extension_breakdown(files)
    logger.info("\nFile Extension Breakdown:")
    for ext, count in sorted(extension_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]:
        logger.info(f"  {ext}: {count}")
    
    # Detect frameworks
    logger.info("\nDetecting frameworks...")
    frameworks = scanner.detect_framework_patterns(files)
    if frameworks:
        logger.info(f"Detected frameworks: {', '.join(frameworks)}")
    else:
        logger.info("No frameworks detected")
    
    # Identify documentation files
    doc_files = scanner.identify_documentation_files(files)
    logger.info(f"\nFound {len(doc_files)} documentation files:")
    for doc_file in doc_files[:5]:  # Show first 5
        logger.info(f"  {doc_file}")
    if len(doc_files) > 5:
        logger.info(f"  ... and {len(doc_files) - 5} more")
    
    # Identify entry points
    entry_points = scanner.identify_entry_points(files)
    logger.info(f"\nFound {len(entry_points)} potential entry points:")
    for entry_point in entry_points:
        logger.info(f"  {entry_point}")
    
    metrics.end_workflow("repository_scanning")
    
    # Initialize repository analyzer agent
    metrics.start_workflow("repository_analysis")
    repo_analyzer = RepoAnalyzer(config=agent_config)
    
    # Perform repository structure analysis
    logger.info("\nAnalyzing repository structure...")
    repo_structure = repo_analyzer.analyze_repo_structure(
        RepoStructureInput(
            repo_path=repo_path,
            files=files
        )
    )
    
    # Print analysis results
    logger.info("\nRepository Analysis Results:")
    logger.info(f"Summary: {repo_structure.summary}")
    logger.info(f"Technologies: {', '.join(repo_structure.technologies)}")
    if repo_structure.architecture_pattern:
        logger.info(f"Architecture Pattern: {repo_structure.architecture_pattern}")
    
    logger.info("\nComponents:")
    for component in repo_structure.components:
        logger.info(f"  {component.name}: {component.description}")
    
    # Generate markdown summary
    logger.info("\nGenerating repository structure information...")
    markdown_summary = repo_analyzer.generate_markdown_summary(repo_structure)
    
    # Identify documentation needs
    logger.info("\nIdentifying documentation needs...")
    doc_needs = repo_analyzer.identify_documentation_needs(repo_structure)
    for category, needs in doc_needs.items():
        logger.info(f"\n{category}:")
        for need in needs:
            logger.info(f"  - {need}")
    
    metrics.end_workflow("repository_analysis", cost=0.05, tokens=5000)  # Example values
    
    # Create directory tree representation
    metrics.start_workflow("directory_tree_generation")
    directory_tree = create_directory_tree(repo_path)
    logger.info("\nDirectory Structure:")
    logger.info(directory_tree)
    metrics.end_workflow("directory_tree_generation")
    
    # Generate or update README if needed
    metrics.start_workflow("readme_generation")
    readme_path = os.path.join(repo_path, "examples/output/README.md")
    existing_readme = None
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            existing_readme = f.read()
        logger.info("\nExisting README.md found")
    
    # Initialize README generator
    readme_generator = ReadmeGenerator(config=agent_config)
    
    # Prepare README input with enhanced context
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    # Create enhanced input with more detailed structure information
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
    
    if existing_readme:
        # Update existing README with enhanced context
        logger.info("\nUpdating README.md with enhanced context...")
        enhanced_input.existing_readme = existing_readme
        readme_result = readme_generator.update_readme(enhanced_input)
    else:
        # Generate new README with enhanced context
        logger.info("\nGenerating new README.md with enhanced context...")
        readme_result = readme_generator.generate_readme(enhanced_input)
    
    # Save README
    os.makedirs(os.path.dirname(readme_path), exist_ok=True)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_result.markdown)
    logger.info(f"Saved enhanced README.md to {readme_path}")
    
    # Save the enhanced context as a JSON file for reference
    context_path = os.path.join(repo_path, "examples/output/enhanced_context.json")
    with open(context_path, "w", encoding="utf-8") as f:
        # Convert data to a serializable format
        serializable_context = {
            "repo_name": repo_name,
            "repo_description": repo_structure.summary,
            "directory_structure": directory_tree,
            "technologies": list(repo_structure.technologies),
            "architecture_pattern": repo_structure.architecture_pattern,
            "components": [{"name": c.name, "description": c.description} for c in repo_structure.components],
            "entry_points": list(entry_points),
            "documentation_needs": {k: list(v) for k, v in doc_needs.items()},
            "framework_info": list(frameworks) if frameworks else [],
            "file_statistics": {
                "total_files": len(files),
                "extensions": {str(k): v for k, v in extension_breakdown.items()},
                "doc_files": len(doc_files)
            }
        }
        json.dump(serializable_context, f, indent=2)
    logger.info(f"Saved enhanced context to {context_path}")
    
    metrics.end_workflow("readme_generation", cost=0.08, tokens=8000)  # Example values
    
    # Print final metrics summary
    logger.info(metrics.get_summary())

def create_directory_tree(repo_path, max_depth=4, excluded_dirs=None):
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
        'public': 'Public assets',
        'static': 'Static assets',
        'assets': 'Project assets',
        'data': 'Data files',
        'migrations': 'Database migrations',
        'lib': 'Library files',
        'bin': 'Binary files',
        'tools': 'Development tools'
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
            important_extensions = ['.md', '.py', '.js', '.ts', '.json', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.txt']
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
    
    analyze_repository(repo_path) 