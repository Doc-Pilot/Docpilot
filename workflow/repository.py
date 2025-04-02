"""
Repository Analysis Module
=========================

This module provides functions for scanning and analyzing repository structures.
"""
import os
import json
import time
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Import Docpilot components
from src.utils.repo_scanner import RepoScanner
from src.agents import AgentConfig, RepoAnalyzer, RepoStructureInput

# Import token cost tracker
from .metrics import ModelTokenCost

logger = logging.getLogger(__name__)

def scan_repository(
    repo_path: str, 
    excluded_dirs: Optional[List[str]] = None,
    metrics = None
) -> Dict[str, Any]:
    """
    Scan repository to collect basic information
    
    Args:
        repo_path: Path to the repository
        excluded_dirs: Directories to exclude from analysis
        metrics: Metrics tracking object
        
    Returns:
        Dictionary with repository information
    """
    excluded_dirs = excluded_dirs or []
    logger.info(f"Scanning repository: {repo_path}")
    repo_name = os.path.basename(repo_path)
    
    # Start metrics for file scanning
    if metrics:
        metrics.log_event("repo_scanning", "SCAN_STARTED", {
            "repo_path": repo_path,
            "excluded_dirs": excluded_dirs
        })
    
    scan_start = time.time()
    
    # Collect file information
    files = []
    file_stats = {
        "total_files": 0,
        "total_size": 0,
        "by_extension": {}
    }
    frameworks = {
        "frontend": [],
        "backend": [],
        "dependencies": []
    }
    entry_points = []
    
    # Look for signs of frameworks
    framework_indicators = {
        # Frontend frameworks
        "react": ["package.json", "react", "jsx"],
        "vue": ["package.json", "vue"],
        "angular": ["package.json", "angular.json", "ngModule"],
        "svelte": ["package.json", "svelte"],
        # Backend frameworks
        "express": ["package.json", "express"],
        "nextjs": ["package.json", "next"],
        "django": ["settings.py", "urls.py", "wsgi.py"],
        "flask": ["app.py", "flask"],
        "fastapi": ["main.py", "fastapi"],
        "spring": ["pom.xml", "gradle", "Application.java"],
        "laravel": ["composer.json", "artisan"],
        # Other common dependencies
        "typescript": ["tsconfig.json"],
        "webpack": ["webpack.config.js"],
        "babel": [".babelrc", "babel.config.js"],
        "docker": ["Dockerfile", "docker-compose.yml"]
    }
    
    # Collect framework evidence
    framework_evidence = {k: 0 for k in framework_indicators.keys()}
    
    # Walk the directory
    for root, dirs, filenames in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        # Process files
        for filename in filenames:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, repo_path)
            
            # Skip files larger than 10MB
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:
                continue
            
            # Track file statistics
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext:
                if file_ext not in file_stats["by_extension"]:
                    file_stats["by_extension"][file_ext] = {"count": 0, "size": 0}
                file_stats["by_extension"][file_ext]["count"] += 1
                file_stats["by_extension"][file_ext]["size"] += file_size
            
            file_stats["total_files"] += 1
            file_stats["total_size"] += file_size
            
            # Check for framework indicators
            file_content = ""
            try:
                if file_size < 1 * 1024 * 1024:  # Only read files smaller than 1MB
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
            except Exception:
                pass
            
            # Check for entry points
            if (
                filename in ["main.py", "app.py", "index.js", "server.js", "app.js"] or
                "main" in filename.lower() and "class" in file_content.lower() and "public static void main" in file_content
            ):
                entry_points.append(relative_path)
            
            # Detect frameworks
            for framework, indicators in framework_indicators.items():
                for indicator in indicators:
                    if (
                        indicator in filename or
                        indicator in relative_path or
                        (file_content and indicator in file_content)
                    ):
                        framework_evidence[framework] += 1
            
            # Add to files list
            files.append(relative_path)
    
    # Determine most likely frameworks
    for framework, evidence in framework_evidence.items():
        if evidence > 0:
            # Categorize framework
            if framework in ["react", "vue", "angular", "svelte"]:
                frameworks["frontend"].append(framework)
            elif framework in ["express", "nextjs", "django", "flask", "fastapi", "spring", "laravel"]:
                frameworks["backend"].append(framework)
            else:
                frameworks["dependencies"].append(framework)
    
    # Generate directory tree (simple version)
    directory_tree = create_directory_tree(repo_path, excluded_dirs=excluded_dirs)
    
    # Analyze package management files for dependencies
    dependencies = extract_dependencies(repo_path, files)
    if dependencies:
        frameworks["dependencies"].extend(dependencies)
    
    # Calculate scan duration
    scan_duration = time.time() - scan_start
    
    # Log the completion event
    if metrics:
        metrics.log_event("repo_scanning", "SCAN_COMPLETED", {
            "duration": scan_duration,
            "file_count": file_stats["total_files"],
            "repo_size_kb": file_stats["total_size"] // 1024
        })
    
    # Return repository data
    return {
        "repo_name": repo_name,
        "file_count": file_stats["total_files"],
        "repo_size": file_stats["total_size"],
        "files": files,
        "file_stats": file_stats,
        "frameworks": frameworks,
        "entry_points": entry_points,
        "directory_tree": directory_tree
    }

def extract_dependencies(repo_path: str, files: List[str]) -> List[str]:
    """
    Extract dependencies from package management files
    
    Args:
        repo_path: Path to the repository
        files: List of files in the repository
        
    Returns:
        List of detected dependencies
    """
    dependencies = []
    
    # Common package management files
    package_files = [
        f for f in files if f in [
            "package.json", 
            "requirements.txt", 
            "Pipfile", 
            "pom.xml", 
            "build.gradle", 
            "composer.json"
        ]
    ]
    
    # Extract dependencies from each package file
    for package_file in package_files:
        try:
            file_path = os.path.join(repo_path, package_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Handle package.json (Node.js)
                if package_file == "package.json":
                    import json
                    try:
                        data = json.loads(content)
                        deps = []
                        if "dependencies" in data:
                            deps.extend(data["dependencies"].keys())
                        if "devDependencies" in data:
                            deps.extend(data["devDependencies"].keys())
                        dependencies.extend(deps)
                    except json.JSONDecodeError:
                        pass
                
                # Handle requirements.txt (Python)
                elif package_file == "requirements.txt":
                    lines = content.split("\n")
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Extract package name without version
                            match = re.match(r'^([a-zA-Z0-9_\-]+)', line)
                            if match:
                                dependencies.append(match.group(1))
                
                # Handle Pipfile (Python)
                elif package_file == "Pipfile":
                    if "[packages]" in content:
                        packages_section = content.split("[packages]")[1].split("[")[0]
                        matches = re.findall(r'([a-zA-Z0-9_\-]+)\s*=', packages_section)
                        dependencies.extend(matches)
                
                # Handle pom.xml (Java)
                elif package_file == "pom.xml":
                    matches = re.findall(r'<artifactId>([^<]+)</artifactId>', content)
                    dependencies.extend(matches)
        
        except Exception as e:
            logger.error(f"Error extracting dependencies from {package_file}: {e}")
    
    return list(set(dependencies))  # Remove duplicates

def analyze_repository(
    repo_path: str,
    repo_data: Dict[str, Any],
    metrics
) -> Dict[str, Any]:
    """
    Analyze repository structure and documentation needs
    
    Args:
        repo_path: Path to the repository
        repo_data: Data from repository scanning
        metrics: Metrics tracking object
        
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"Analyzing repository structure: {repo_path}")
    
    # Start metrics for analysis
    metrics.start_workflow("repo_structure_analysis")
    
    # Configure agent
    agent_config = AgentConfig()
    
    # Get the model name for cost calculation
    model_name = agent_config.model_name
    
    # Initialize analyzer
    repo_analyzer = RepoAnalyzer(config=agent_config)
    
    # Create enhanced input for repo analyzer
    repo_structure_input = RepoStructureInput(
        repo_name=repo_data["repo_name"],
        repo_path=repo_path,
        files=repo_data["files"],
        frameworks=repo_data["frameworks"],
        directory_structure=repo_data.get("directory_tree", "")
    )
    
    # Start time for the LLM call
    llm_start = time.time()
    
    # Analyze repository structure
    result = repo_analyzer.analyze_repo_structure(repo_structure_input)
    
    # Get documentation needs
    doc_needs = repo_analyzer.identify_documentation_needs(repo_structure_input, result)
    
    # Calculate LLM time
    llm_duration = time.time() - llm_start
    
    # Get the result context if available
    result_context = getattr(result, "_context", None)
    
    # Log event with important stats
    metrics.log_event(
        "repo_structure_analysis", 
        "LLM_CALL_COMPLETED", 
        {
            "duration": llm_duration,
            "file_count": len(repo_data["files"])
        },
        model=model_name,
        result=result_context,
        agent=repo_analyzer
    )
    
    # Save analysis results
    analysis_file = os.path.join(metrics.output_dir, "repo_analysis.json")
    with open(analysis_file, "w", encoding="utf-8") as f:
        # Convert to JSON-serializable format
        serializable_result = {
            "summary": result.summary,
            "architecture_pattern": result.architecture_pattern,
            "technologies": list(result.technologies),
            "components": [
                {"name": c.name, "description": c.description} 
                for c in result.components
            ]
        }
        json.dump(serializable_result, f, indent=2)
    logger.info(f"Analysis results saved to {analysis_file}")
    
    # Save documentation needs
    doc_needs_file = os.path.join(metrics.output_dir, "documentation_needs.json")
    with open(doc_needs_file, "w", encoding="utf-8") as f:
        json.dump(doc_needs, f, indent=2)
    logger.info(f"Documentation needs saved to {doc_needs_file}")
    
    # Create and save detailed directory tree
    try:
        tree_file = os.path.join(metrics.output_dir, "directory_tree.txt")
        with open(tree_file, "w", encoding="utf-8") as f:
            f.write(repo_data.get("directory_tree", ""))
        logger.info(f"Directory tree saved to {tree_file}")
    except Exception as e:
        logger.error(f"Error saving directory tree: {e}")
    
    # End analysis workflow
    metrics.end_workflow("repo_structure_analysis")
    
    return {
        "repo_structure": result,
        "doc_needs": doc_needs
    }

def create_directory_tree(
    repo_path: str, 
    max_depth: int = 3, 
    excluded_dirs: Optional[List[str]] = None
) -> str:
    """
    Create a text representation of the directory structure
    
    Args:
        repo_path: Path to the repository
        max_depth: Maximum depth to display
        excluded_dirs: Directories to exclude
        
    Returns:
        Text representation of the directory structure
    """
    excluded_dirs = excluded_dirs or []
    repo_name = os.path.basename(repo_path)
    result = [f"{repo_name}/"]
    
    def _add_directory(path, prefix, depth):
        if depth > max_depth:
            result.append(f"{prefix}...")
            return
            
        entries = sorted(os.listdir(path))
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and e not in excluded_dirs]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        
        # Limit the number of files shown per directory
        max_files = 10
        if len(files) > max_files:
            files = files[:max_files] + ["..."]
        
        # Add all directories first
        for i, d in enumerate(dirs):
            is_last_dir = i == len(dirs) - 1 and not files
            new_prefix = prefix + ("└── " if is_last_dir else "├── ")
            result.append(f"{new_prefix}{d}/")
            _add_directory(
                os.path.join(path, d),
                prefix + ("    " if is_last_dir else "│   "),
                depth + 1
            )
        
        # Then add all files
        for i, f in enumerate(files):
            is_last = i == len(files) - 1
            result.append(f"{prefix}{'└── ' if is_last else '├── '}{f}")
    
    try:
        _add_directory(repo_path, "", 1)
        return "\n".join(result)
    except Exception as e:
        logger.error(f"Error creating directory tree: {e}")
        return f"{repo_name}/ (Error: {str(e)})" 