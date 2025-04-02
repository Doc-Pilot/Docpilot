"""
Workflow Orchestration Module
============================

This module orchestrates the complete workflow for repository analysis and documentation generation.
"""
import os
import sys
import logging
import json
import time
import random
import string
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

# Import Docpilot workflow modules
from .metrics import WorkflowMetrics
from .repository import scan_repository, analyze_repository, create_directory_tree
from .documentation import generate_readme, generate_api_documentation, generate_component_documentation

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DocpilotWorkflow:
    """
    Main workflow class for repository analysis and documentation generation
    
    This class handles the entire process of analyzing a repository, generating
    documentation, and tracking metrics.
    """
    
    def __init__(
        self, 
        repo_path: str, 
        output_dir: Optional[str] = None,
        excluded_dirs: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the DocpilotWorkflow
        
        Args:
            repo_path: Path to the repository
            output_dir: Directory to save generated documentation
            excluded_dirs: Directories to exclude from analysis
            config: Configuration options
        """
        self.repo_path = os.path.abspath(repo_path)
        self.repo_name = os.path.basename(self.repo_path)
        
        # Set up default excluded directories
        self.excluded_dirs = excluded_dirs or [
            '.git', '.github', 'node_modules', 'venv', '.venv', 'env',
            '__pycache__', '.pytest_cache', '.mypy_cache', 'build', 'dist'
        ]
        
        # Set up output directory
        if output_dir:
            self.output_dir = output_dir
        else:
            # Use the global workflow_output directory instead of creating one in the repository
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            workflow_output = os.path.join(project_root, "workflow_output")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            job_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            self.output_dir = os.path.join(workflow_output, f"job_{timestamp}_{job_id}")
        
        # Initialize metrics tracking with project name
        self.metrics = WorkflowMetrics(self.output_dir, project_name=self.repo_name)
        
        # Configuration options with defaults
        self.config = {
            "analyze_repo": True,
            "generate_readme": True,
            "find_api_files": True,
            "generate_api_docs": True,
            "find_component_files": True,
            "generate_component_docs": True,
            "max_directory_depth": 3,
            "openapi_version": "3.0.0",
            "save_intermediate_results": True,
        }
        
        # Update config with user-provided options
        if config:
            self.config.update(config)
        
        # Initialize state for tracking results
        self.results = {
            "repo_data": {},
            "analysis_data": {},
            "readme_data": {},
            "api_doc_data": {},
            "component_doc_data": {}
        }
        
        # Check if repository path exists
        if not os.path.exists(self.repo_path):
            raise ValueError(f"Repository path {self.repo_path} does not exist")
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Output directory set to {self.output_dir}")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the complete workflow
        
        Returns:
            Dictionary with workflow results
        """
        try:
            logger.info(f"Starting Docpilot workflow for {self.repo_name}")
            
            # Start workflow metrics
            self.metrics.start_workflow("main", {"repo_name": self.repo_name})
            
            # Step 1: Scan repository
            self._scan_repository()
            
            # Step 2: Analyze repository structure
            if self.config["analyze_repo"]:
                self._analyze_repository()
            
            # Step 3: Generate README
            if self.config["generate_readme"]:
                self._generate_readme()
            
            # Step 4: Generate API documentation
            if self.config["find_api_files"] and self.config["generate_api_docs"]:
                self._generate_api_docs()
            
            # Step 5: Generate component documentation
            if self.config["find_component_files"] and self.config["generate_component_docs"]:
                self._generate_component_docs()
            
            # End workflow metrics
            self.metrics.end_workflow("main")
            
            # Save all metrics
            self.metrics.save_summary()
            logger.info(f"Workflow completed successfully. Output saved to {self.output_dir}")
            
            # Return results
            return {
                "success": True,
                "output_dir": self.output_dir,
                "metrics": self.metrics.get_summary(),
                "results": self.results
            }
            
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}", exc_info=True)
            
            # Log error event
            if hasattr(self, 'metrics'):
                self.metrics.log_event("main", "ERROR", {"error": str(e)})
                self.metrics.end_workflow("main", success=False)
                self.metrics.save_summary()
            
            return {
                "success": False,
                "error": str(e),
                "output_dir": self.output_dir if hasattr(self, 'output_dir') else None,
                "results": self.results
            }
    
    def _scan_repository(self) -> None:
        """Scan repository and collect basic information"""
        self.metrics.start_workflow("repo_scanning", {
            "excluded_dirs": self.excluded_dirs
        })
        
        logger.info(f"Scanning repository {self.repo_path}")
        
        # Scan repository
        repo_data = scan_repository(
            self.repo_path, 
            self.excluded_dirs,
            self.metrics
        )
        
        # Generate directory tree
        directory_tree = create_directory_tree(
            self.repo_path,
            max_depth=self.config["max_directory_depth"],
            excluded_dirs=self.excluded_dirs
        )
        repo_data["directory_tree"] = directory_tree
        
        # Save scanned data
        if self.config["save_intermediate_results"]:
            scan_file = os.path.join(self.output_dir, "repo_scan.json")
            with open(scan_file, "w", encoding="utf-8") as f:
                # Convert paths to relative for better portability
                serializable_data = {}
                for key, value in repo_data.items():
                    if key == "files":
                        serializable_data[key] = value
                    elif key == "directory_tree":
                        serializable_data[key] = value
                    else:
                        serializable_data[key] = value
                json.dump(serializable_data, f, indent=2)
        
        # Store results
        self.results["repo_data"] = repo_data
        
        # End scanning workflow
        self.metrics.end_workflow("repo_scanning")
        logger.info("Repository scanning completed")
    
    def _analyze_repository(self) -> None:
        """Analyze repository structure"""
        if not self.results.get("repo_data"):
            logger.error("Repository must be scanned before analysis")
            raise ValueError("Repository must be scanned before analysis")
        
        self.metrics.start_workflow("repo_analysis")
        
        # Analyze repository structure
        analysis_data = analyze_repository(
            self.repo_path,
            self.results["repo_data"],
            self.metrics
        )
        
        # Store results
        self.results["analysis_data"] = analysis_data
        
        # End analysis workflow
        self.metrics.end_workflow("repo_analysis")
        logger.info("Repository analysis completed")
    
    def _generate_readme(self) -> None:
        """Generate README.md file"""
        if not self.results.get("repo_data") or not self.results.get("analysis_data"):
            logger.error("Repository must be scanned and analyzed before generating README")
            raise ValueError("Repository must be scanned and analyzed before generating README")
        
        self.metrics.start_workflow("readme_generation")
        
        # Generate README
        readme_data = generate_readme(
            self.repo_path,
            self.results["repo_data"],
            self.results["analysis_data"],
            self.metrics
        )
        
        # Store results
        self.results["readme_data"] = readme_data
        
        # End README generation workflow
        self.metrics.end_workflow("readme_generation")
        logger.info("README generation completed")
    
    def _generate_api_docs(self) -> None:
        """Generate API documentation"""
        if not self.results.get("repo_data") or not self.results.get("analysis_data"):
            logger.error("Repository must be scanned and analyzed before generating API docs")
            raise ValueError("Repository must be scanned and analyzed before generating API docs")
        
        self.metrics.start_workflow("api_documentation")
        
        # Find API files
        api_files = []
        if self.config["find_api_files"]:
            files = self.results["repo_data"].get("files", [])
            api_files = self._find_api_files(files)
            logger.info(f"Found {len(api_files)} API files")
        
        # Generate API documentation
        api_doc_data = generate_api_documentation(
            self.repo_path,
            api_files,
            self.results["repo_data"],
            self.results["analysis_data"],
            self.metrics
        )
        
        # Store results
        self.results["api_doc_data"] = api_doc_data
        
        # End API documentation workflow
        self.metrics.end_workflow("api_documentation")
        logger.info("API documentation generation completed")
    
    def _generate_component_docs(self) -> None:
        """Generate component documentation"""
        if not self.results.get("repo_data") or not self.results.get("analysis_data"):
            logger.error("Repository must be scanned and analyzed before generating component docs")
            raise ValueError("Repository must be scanned and analyzed before generating component docs")
        
        self.metrics.start_workflow("component_documentation")
        
        # Find component files
        component_files = []
        if self.config["find_component_files"]:
            files = self.results["repo_data"].get("files", [])
            frameworks = self.results["repo_data"].get("frameworks", {})
            component_files = self._find_component_files(files, frameworks)
            logger.info(f"Found {len(component_files)} component files")
        
        # Generate component documentation
        component_doc_data = generate_component_documentation(
            self.repo_path,
            component_files,
            self.results["repo_data"],
            self.results["analysis_data"],
            self.metrics
        )
        
        # Store results
        self.results["component_doc_data"] = component_doc_data
        
        # End component documentation workflow
        self.metrics.end_workflow("component_documentation")
        logger.info("Component documentation generation completed")
    
    def _find_api_files(self, files: List[str]) -> List[str]:
        """
        Find API files in the repository
        
        Args:
            files: List of files in the repository
            
        Returns:
            List of API files
        """
        api_files = []
        
        # Common API file patterns
        api_patterns = [
            r"api[/\\].*\.py$",
            r"routes[/\\].*\.py$",
            r"endpoints[/\\].*\.py$",
            r"controllers[/\\].*\.js$",
            r"api[/\\].*\.js$",
            r"routes[/\\].*\.js$",
            r".*Controller\.java$",
            r".*Resource\.java$",
            r"controllers[/\\].*\.rb$",
            r"routes[/\\].*\.php$",
            r"api[/\\].*\.go$",
            r"routers[/\\].*\.go$",
            r"handlers[/\\].*\.go$",
        ]
        
        # TODO: Use more sophisticated detection based on content analysis
        import re
        for file_path in files:
            for pattern in api_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    api_files.append(file_path)
                    break
        
        return api_files
    
    def _find_component_files(self, files: List[str], frameworks: Dict[str, Any]) -> List[str]:
        """
        Find component files in the repository
        
        Args:
            files: List of files in the repository
            frameworks: Framework information from repository scanning
            
        Returns:
            List of component files
        """
        component_files = []
        
        # Patterns based on detected frameworks
        component_patterns = []
        
        # React/Vue/Angular components
        if any(fw in frameworks.get("frontend", []) for fw in ["react", "vue", "angular"]):
            component_patterns.extend([
                r"components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue)$",
                r"src[/\\]components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue)$",
                r"src[/\\].*[/\\]components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue)$",
            ])
        
        # Django/Flask components
        if any(fw in frameworks.get("backend", []) for fw in ["django", "flask"]):
            component_patterns.extend([
                r"views[/\\].*\.py$",
                r"models[/\\].*\.py$",
                r"forms[/\\].*\.py$",
            ])
        
        # Spring components
        if "spring" in frameworks.get("backend", []):
            component_patterns.extend([
                r".*Service\.java$",
                r".*Repository\.java$",
                r".*Component\.java$",
            ])
        
        # Default patterns if no specific framework detected
        if not component_patterns:
            component_patterns = [
                r"components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue|py|java|rb|php|go)$",
                r"src[/\\]components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue|py|java|rb|php|go)$",
                r"src[/\\].*[/\\]components[/\\][^/\\]+\.(js|jsx|ts|tsx|vue|py|java|rb|php|go)$",
            ]
        
        # Find component files based on patterns
        import re
        for file_path in files:
            for pattern in component_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    component_files.append(file_path)
                    break
        
        return component_files 