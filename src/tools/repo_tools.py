"""
Repository Analysis Tools
======================

This module provides LLM-friendly functions for scanning and analyzing repositories.
These wrapper functions use the core RepoScanner utility with standardized input/output formats.
"""

import os
from typing import Dict, List, Any

from ..utils import RepoScanner
from ..utils.logging import core_logger  # Import core_logger

logger = core_logger()

def scan_repository(repo_path: str, 
                   include_patterns: List[str] = None,
                   exclude_patterns: List[str] = None,
                   use_gitignore: bool = True) -> Dict[str, Any]:
    """
    Scan and analyze a repository for documentation purposes.
    
    Args:
        repo_path: Path to the repository
        include_patterns: List of glob patterns to include
        exclude_patterns: List of glob patterns to exclude
        use_gitignore: Whether to use .gitignore patterns
        
    Returns:
        Dictionary containing analysis results
    """
    try:
        # Normalize repository path
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "message": f"Repository path does not exist: {repo_path}",
                "file_count": 0
            }
            
        scanner = RepoScanner(
            repo_path=repo_path,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            use_gitignore=use_gitignore
        )
        
        # Get analysis results
        analysis = scanner.analyze_repository()
        files = analysis.get("files", [])
        
        # Format response for LLM consumption (simplified)
        result = {
            "success": True,
            "message": f"Repository analysis completed successfully with {len(files)} files",
            "file_count": len(files),
            "files": files[:25] if len(files) > 25 else files,  # Limit file list to first 25
        }
        
        # Format technologies and languages in the expected output format
        technologies = analysis.get("technologies", {})
        if technologies:
            # Ensure technologies output format matches expectations
            formatted_tech = {}
            for category, techs in technologies.items():
                # Convert from set to list if needed
                formatted_tech[category] = sorted(list(techs)) if isinstance(techs, set) else techs
            result["technologies"] = formatted_tech
        else:
            result["technologies"] = {}
            
        # Format languages
        languages = analysis.get("languages", {})
        if languages:
            result["languages"] = languages
        else:
            result["languages"] = {}
            
        return result
        
    except Exception as e:
        logger.error(f"Error scanning repository: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Error scanning repository: {str(e)}",
            "file_count": 0
        }

def get_tech_stack(repo_path: str) -> Dict[str, Any]:
    """
    Detect the technology stack, including specific API frameworks, used in the repository.
    This function utilizes the RepoScanner's enhanced framework detection capabilities.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with detected technologies, including a specific 'api_frameworks' key.
    """
    try:
        # Normalize path
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "message": f"Repository path does not exist: {repo_path}",
                "tech_stack": {}
            }
            
        scanner = RepoScanner(repo_path)
        tech_stack, api_frameworks = scanner.detect_frameworks()
        
        # Convert sets to lists for JSON serialization
        formatted_tech = {}
        for category, techs in tech_stack.items():
            formatted_tech[category] = sorted(list(techs))
            
        # Add the specifically identified API frameworks
        formatted_tech["api_frameworks"] = sorted(list(api_frameworks))
        
        # Determine primary API framework if possible
        primary_api_framework = None
        if api_frameworks:
            # Simple heuristic: Prefer common Python/JS frameworks if multiple detected
            preferred_order = ["fastapi", "flask", "django", "express", "nestjs"]
            for fw in preferred_order:
                if fw in api_frameworks:
                    primary_api_framework = fw
                    break
            if not primary_api_framework:
                primary_api_framework = sorted(list(api_frameworks))[0] # Fallback to alphabetical

        return {
            "success": True,
            "message": "Technology stack detection completed",
            "tech_stack": formatted_tech,
            "primary_api_framework": primary_api_framework
        }
    except Exception as e:
        logger.error(f"Error detecting technologies: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Error detecting technologies: {str(e)}",
            "tech_stack": {}
        }

def identify_api_components(repo_path: str) -> Dict[str, Any]:
    """
    Identify API components in a repository using framework-specific patterns.
    This tool leverages the enhanced RepoScanner.identify_api_components method.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with categorized API component file paths.
    """
    try:
        # Initialize scanner
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "message": f"Repository path does not exist: {repo_path}",
                "components": {}
            }
            
        scanner = RepoScanner(repo_path)
        
        # Get API components using the dedicated RepoScanner method
        api_components = scanner.identify_api_components() # This now returns Dict[str, List[str]]
        
        return {
            "success": True,
            "message": f"API component identification completed. Found {sum(len(v) for v in api_components.values())} component files.",
            "components": api_components
        }
        
    except Exception as e:
        logger.error(f"Error identifying API components: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Error identifying API components: {str(e)}",
            "components": {}
        }

def generate_repo_tree(repo_path: str, 
                         output_format: str = "markdown", 
                         max_depth: int = 5) -> Dict[str, Any]:
    """
    Generate a tree representation of the repository structure.
    
    Args:
        repo_path: Path to the repository
        output_format: Format for the tree ('markdown' or 'text')
        max_depth: Maximum depth to traverse for the tree
        
    Returns:
        Dictionary containing the repository tree string
    """
    try:
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(repo_path):
            return {"success": False, "error": f"Repository path not found: {repo_path}"}
            
        scanner = RepoScanner(repo_path)
        
        if output_format.lower() == "markdown":
            tree_string = scanner.create_markdown_tree(max_depth=max_depth)
        elif output_format.lower() == "text":
            tree_string = scanner.create_tree(max_depth=max_depth)
        else:
            return {"success": False, "error": f"Unsupported format: {output_format}. Use 'markdown' or 'text'."}
            
        return {
            "success": True,
            "tree": tree_string,
            "format": output_format,
            "max_depth": max_depth
        }
        
    except Exception as e:
        logger.error(f"Error generating repository tree: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error generating repository tree: {str(e)}"
        }