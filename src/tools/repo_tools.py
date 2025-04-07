"""
Repository Analysis Tools
======================

This module provides functions for scanning and analyzing repositories.
These functions are optimized for tool calling by LLMs with standardized input parameters and return formats.
"""

import os
import json
from typing import Dict, List, Any, Optional, Union, Set
from pathlib import Path

from ..utils.repo_scanner import RepoScanner

def scan_repository(repo_path: str, include_patterns: List[str] = None, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Scan a repository and provide a comprehensive analysis of its structure.
    
    Args:
        repo_path: Path to the repository
        include_patterns: Optional list of glob patterns to include
        exclude_patterns: Optional list of glob patterns to exclude
        
    Returns:
        Dictionary with repository analysis results
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize repository scanner with optional patterns
        scanner = RepoScanner(
            repo_path=repo_path,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns
        )
        
        # Perform comprehensive analysis
        analysis = scanner.analyze_repository()
        
        # Add success flag and format the response for LLM consumption
        result = {
            "success": True,
            "message": f"Repository analysis completed successfully with {analysis.get('file_count', 0)} files",
            "file_count": analysis.get("file_count", 0),
            "technologies": analysis.get("technologies", {}),
            "languages": analysis.get("languages", {}),
            "extension_breakdown": analysis.get("extension_breakdown", {}),
            "directory_structure": analysis.get("directory_tree", {})
        }
        
        # Add module information
        modules = analysis.get("modules", {})
        if modules:
            result["modules"] = {}
            for module_name, files in modules.items():
                # Limit the number of files shown for each module to avoid overwhelming responses
                result["modules"][module_name] = {
                    "file_count": len(files),
                    "sample_files": files[:5] if len(files) > 5 else files
                }
        
        # Add file samples for further exploration
        file_samples = analysis.get("file_samples", {})
        if file_samples:
            result["file_samples"] = file_samples
            
        return result
    except Exception as e:
        return {"success": False, "error": f"Error scanning repository: {str(e)}"}

def get_tech_stack(repo_path: str) -> Dict[str, Any]:
    """
    Detect the technology stack used in a repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with detected technologies by category
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Detect frameworks and technologies
        technologies = scanner.detect_frameworks()
        
        # Format the results for easy consumption
        result = {
            "success": True,
            "message": "Technology stack detection completed",
            "tech_stack": {}
        }
        
        # Convert sets to lists for JSON serialization
        for category, techs in technologies.items():
            result["tech_stack"][category] = sorted(list(techs))
        
        return result
    except Exception as e:
        return {"success": False, "error": f"Error detecting technology stack: {str(e)}"}

def get_code_files(repo_path: str, language: str = None) -> Dict[str, Any]:
    """
    Get a list of code files in the repository, optionally filtered by language.
    
    Args:
        repo_path: Path to the repository
        language: Optional programming language to filter by
        
    Returns:
        Dictionary with code files by language
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Get all files
        files = scanner.scan_files()
        
        # Analyze languages
        language_counts, extension_counts = scanner.analyze_languages(files)
        
        # Initialize result
        result = {
            "success": True,
            "message": f"Found {len(files)} total files in the repository",
            "total_files": len(files),
            "language_breakdown": language_counts
        }
        
        # Filter by language if specified
        if language:
            language = language.lower()
            normalized_language = language
            
            # Handle common language name variations
            language_map = {
                "js": "javascript",
                "ts": "typescript",
                "py": "python",
                "rb": "ruby",
                "go": "go",
                "java": "java",
                "cs": "c#",
                "cpp": "c++",
                "c++": "c++",
                "php": "php"
            }
            
            normalized_language = language_map.get(language, language)
            
            # Map language to extensions
            language_extensions = {
                "python": [".py"],
                "javascript": [".js", ".jsx"],
                "typescript": [".ts", ".tsx"],
                "java": [".java"],
                "c#": [".cs"],
                "c++": [".cpp", ".hpp", ".cc", ".hh"],
                "go": [".go"],
                "ruby": [".rb"],
                "php": [".php"],
                "rust": [".rs"],
                "swift": [".swift"],
                "kotlin": [".kt"]
            }
            
            # Get extensions for the requested language
            extensions = language_extensions.get(normalized_language, [])
            
            # Filter files by extension
            filtered_files = []
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if extensions and ext in extensions:
                    filtered_files.append(file)
                elif not extensions and normalized_language in file.lower():
                    # Fallback if no extensions defined
                    filtered_files.append(file)
            
            result["message"] = f"Found {len(filtered_files)} {normalized_language} files in the repository"
            result["language"] = normalized_language
            result["files"] = filtered_files[:100]  # Limit to 100 files
            result["file_count"] = len(filtered_files)
            
            if len(filtered_files) > 100:
                result["note"] = f"Showing first 100 of {len(filtered_files)} {normalized_language} files"
        else:
            # Group files by language
            files_by_language = {}
            
            # Map extensions to languages
            extension_to_language = {}
            for ext, count in extension_counts.items():
                if ext.startswith('.'):
                    if ext in ['.py']:
                        extension_to_language[ext] = 'python'
                    elif ext in ['.js', '.jsx']:
                        extension_to_language[ext] = 'javascript'
                    elif ext in ['.ts', '.tsx']:
                        extension_to_language[ext] = 'typescript'
                    elif ext in ['.java']:
                        extension_to_language[ext] = 'java'
                    elif ext in ['.cs']:
                        extension_to_language[ext] = 'c#'
                    elif ext in ['.cpp', '.hpp']:
                        extension_to_language[ext] = 'c++'
                    elif ext in ['.go']:
                        extension_to_language[ext] = 'go'
                    # Add more mappings as needed
            
            # Group files by detected language
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                lang = extension_to_language.get(ext, 'other')
                
                if lang not in files_by_language:
                    files_by_language[lang] = []
                
                files_by_language[lang].append(file)
            
            # Add language breakdown and sample files for each language
            result["files_by_language"] = {}
            for lang, lang_files in files_by_language.items():
                result["files_by_language"][lang] = {
                    "file_count": len(lang_files),
                    "sample_files": lang_files[:5] if len(lang_files) > 5 else lang_files
                }
        
        return result
    except Exception as e:
        return {"success": False, "error": f"Error getting code files: {str(e)}"}

def get_directory_structure(repo_path: str, max_depth: int = 3) -> Dict[str, Any]:
    """
    Get a hierarchical directory tree structure of the repository.
    
    Args:
        repo_path: Path to the repository
        max_depth: Maximum depth of the directory tree (to limit response size)
        
    Returns:
        Dictionary with directory tree structure
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Get directory tree
        full_tree = scanner.create_directory_tree()
        
        # Function to limit tree depth
        def limit_tree_depth(tree, current_depth=0):
            if current_depth >= max_depth:
                # Return a simplified representation
                files_count = len(tree.get("files", []))
                dirs_count = len(tree.get("dirs", {}))
                
                return {
                    "files_count": files_count,
                    "dirs_count": dirs_count,
                    "note": f"Tree truncated at depth {max_depth}, {files_count} files and {dirs_count} subdirectories not shown"
                }
            
            result = {}
            
            if "files" in tree:
                result["files"] = tree["files"]
            
            if "dirs" in tree:
                result["dirs"] = {}
                for name, subtree in tree["dirs"].items():
                    result["dirs"][name] = limit_tree_depth(subtree, current_depth + 1)
            
            return result
        
        # Limit tree depth
        limited_tree = limit_tree_depth(full_tree)
        
        return {
            "success": True,
            "message": "Directory structure retrieved successfully",
            "directory_tree": limited_tree,
            "max_depth": max_depth
        }
    except Exception as e:
        return {"success": False, "error": f"Error getting directory structure: {str(e)}"}

def get_module_files(repo_path: str, module_name: str) -> Dict[str, Any]:
    """
    Get files that belong to a specific module in the repository.
    
    Args:
        repo_path: Path to the repository
        module_name: Name of the module to get files for
        
    Returns:
        Dictionary with files belonging to the module
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Get all files
        files = scanner.scan_files()
        
        # Identify modules
        modules = scanner.identify_modules(files)
        
        # Check if the requested module exists
        if module_name not in modules:
            # Try case-insensitive matching
            module_found = False
            for mod_name in modules.keys():
                if mod_name.lower() == module_name.lower():
                    module_name = mod_name
                    module_found = True
                    break
            
            if not module_found:
                # List available modules
                available_modules = list(modules.keys())
                return {
                    "success": False,
                    "error": f"Module '{module_name}' not found in repository",
                    "available_modules": available_modules
                }
        
        # Get files for the module
        module_files = modules[module_name]
        
        # Group files by extension
        files_by_extension = {}
        for file in module_files:
            ext = os.path.splitext(file)[1].lower()
            if not ext:
                ext = "(no extension)"
                
            if ext not in files_by_extension:
                files_by_extension[ext] = []
                
            files_by_extension[ext].append(file)
        
        return {
            "success": True,
            "message": f"Found {len(module_files)} files in module '{module_name}'",
            "module": module_name,
            "files": module_files,
            "file_count": len(module_files),
            "files_by_extension": files_by_extension
        }
    except Exception as e:
        return {"success": False, "error": f"Error getting module files: {str(e)}"}

def find_important_files(repo_path: str) -> Dict[str, Any]:
    """
    Find important files in the repository that provide context about the project.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with important files categorized by type
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Get all files
        files = scanner.scan_files()
        
        # Collect file samples
        file_samples = scanner.collect_file_samples(files)
        
        # Important files by category
        important_files = {
            "documentation": [f for f in files if f.lower().endswith('.md') or f.lower().endswith('.rst')],
            "configuration": [f for f in files if any(f.lower().endswith(ext) for ext in ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'])],
            "package_info": [f for f in files if os.path.basename(f).lower() in ['package.json', 'requirements.txt', 'setup.py', 'pyproject.toml', 'cargo.toml', 'gemfile', 'composer.json']],
            "infrastructure": [f for f in files if any(f.lower().endswith(ext) for ext in ['.dockerfile', '.dockerignore']) or os.path.basename(f).lower() in ['dockerfile', 'docker-compose.yml', 'docker-compose.yaml']],
            "ci_cd": [f for f in files if '.github/workflows' in f.lower() or '.gitlab-ci.yml' in f.lower() or '.travis.yml' in f.lower() or '.jenkins' in f.lower()],
            "main_entrypoint": [f for f in files if os.path.basename(f).lower() in ['main.py', 'app.py', 'index.js', 'server.js', 'main.go', 'main.java', 'program.cs']]
        }
        
        # Find README files
        readme_files = [f for f in files if os.path.basename(f).lower().startswith('readme')]
        important_files["readme"] = readme_files
        
        # Combine the automatic samples with our categorized files
        for category, sample_files in file_samples.items():
            if category not in important_files:
                important_files[category] = sample_files
        
        return {
            "success": True,
            "message": "Important files identified in repository",
            "important_files": important_files
        }
    except Exception as e:
        return {"success": False, "error": f"Error finding important files: {str(e)}"}

def analyze_file_relationships(repo_path: str) -> Dict[str, Any]:
    """
    Analyze relationships between files in the repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with related files and their relationships
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Get all files
        files = scanner.scan_files()
        
        # Get related files
        related_files = scanner.get_file_extension_breakdown(files)
        
        # Format response
        file_relationships = {}
        
        # Process each group of related files
        for base_name, rel_files in related_files.items():
            if len(rel_files) > 1:  # Only include if there are multiple related files
                file_relationships[base_name] = {
                    "files": rel_files,
                    "count": len(rel_files)
                }
        
        return {
            "success": True,
            "message": f"Found {len(file_relationships)} groups of related files",
            "file_relationships": file_relationships
        }
    except Exception as e:
        return {"success": False, "error": f"Error analyzing file relationships: {str(e)}"}

def get_repository_summary(repo_path: str) -> Dict[str, Any]:
    """
    Generate a high-level summary of the repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with repository summary information
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path=repo_path)
        
        # Perform comprehensive analysis
        analysis = scanner.analyze_repository()
        
        # Get key metrics and information
        file_count = analysis.get("file_count", 0)
        languages = analysis.get("languages", {})
        tech_stack = analysis.get("technologies", {})
        
        # Get top languages
        top_languages = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5])
        
        # Get key technologies by category
        key_tech = {}
        for category, techs in tech_stack.items():
            # Convert set to list for serialization
            key_tech[category] = list(techs)
        
        # Get main directories
        directories = set()
        for file in analysis.get("file_paths", []):
            parts = file.split('/')
            if len(parts) > 1 and parts[0]:
                directories.add(parts[0])
        
        # Find README files
        readme_files = [
            file for file in analysis.get("file_paths", [])
            if os.path.basename(file).lower().startswith('readme')
        ]
        
        # Identify modules/components
        modules = analysis.get("modules", {})
        top_modules = sorted(modules.keys(), key=lambda m: len(modules[m]), reverse=True)[:10]
        
        # Create repository summary
        summary = {
            "repo_name": os.path.basename(os.path.abspath(repo_path)),
            "file_count": file_count,
            "top_languages": top_languages,
            "tech_stack": key_tech,
            "main_directories": list(directories),
            "readme_files": readme_files,
            "top_modules": [
                {"name": module, "file_count": len(modules[module])}
                for module in top_modules
            ]
        }
        
        return {
            "success": True,
            "message": "Repository summary generated successfully",
            "summary": summary
        }
    except Exception as e:
        return {"success": False, "error": f"Error generating repository summary: {str(e)}"} 