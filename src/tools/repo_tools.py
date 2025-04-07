"""
Repository Analysis Tools
======================

This module provides LLM-friendly functions for scanning and analyzing repositories.
These wrapper functions use the core RepoScanner utility with standardized input/output formats.
"""

import os
import json
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from pathlib import Path
import logging
from collections import defaultdict

from ..utils import RepoScanner

logger = logging.getLogger(__name__)

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
        logger.error(f"Error scanning repository: {str(e)}")
        return {
            "success": False,
            "message": f"Error scanning repository: {str(e)}",
            "file_count": 0
        }

def get_tech_stack(repo_path: str) -> Dict[str, Any]:
    """
    Get the technology stack used in the repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with detected technologies by category
    """
    try:
        scanner = RepoScanner(repo_path)
        tech_stack = scanner.detect_frameworks()
        
        # Convert sets to lists for JSON serialization
        formatted_tech = {}
        for category, techs in tech_stack.items():
            formatted_tech[category] = sorted(list(techs))
        
        return {
            "success": True,
            "message": "Technology stack detection completed",
            "tech_stack": formatted_tech
        }
    except Exception as e:
        logger.error(f"Error detecting technologies: {str(e)}")
        return {
            "success": False,
            "message": f"Error detecting technologies: {str(e)}",
            "technologies": {}
        }

def get_code_files(repo_path: str, language: str = None) -> Dict[str, Any]:
    """
    Get a list of code files in the repository, optionally filtered by language.
    
    Args:
        repo_path: Path to the repository
        language: Optional programming language to filter by
        
    Returns:
        Dictionary with code files by language
    """
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path)
        
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
            result["files"] = filtered_files[:50]  # Limit to 50 files
            result["file_count"] = len(filtered_files)
            
            if len(filtered_files) > 50:
                result["note"] = f"Showing first 50 of {len(filtered_files)} {normalized_language} files"
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
        logger.error(f"Error getting code files: {str(e)}")
        return {
            "success": False,
            "message": f"Error getting code files: {str(e)}",
            "total_files": 0
        }

def identify_api_components(repo_path: str) -> Dict[str, Any]:
    """
    Identify API components in a repository for focused documentation.
    
    This function detects:
    1. API directories and modules
    2. Router/endpoint definition files
    3. API controller/handler files
    4. Schema/model definition files
    5. Main application entry points
    
    Focus is on API components that require documentation for developers
    to efficiently integrate with and understand the API.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with API components categorized by type
    """
    try:
        # Initialize scanner
        scanner = RepoScanner(repo_path)
        
        # Get all files
        files = scanner.scan_files()
        
        # Get language analysis to determine primary language
        languages, extensions = scanner.analyze_languages(files)
        primary_language = max(languages.items(), key=lambda x: x[1])[0] if languages else "Unknown"
        
        # Common API file patterns across languages
        api_components = {
            "api_directories": [],
            "entry_points": [],
            "routers": [],
            "handlers": [],
            "schemas": [],
            "config": []
        }
        
        # Detect API directories
        api_dir_patterns = [
            "/api/", "apis/", "/endpoints/", "/routes/", 
            "/controllers/", "/views/", "/handlers/"
        ]
        
        # Special case patterns by language
        lang_specific_patterns = {
            "Python": {
                "entry_points": ["app.py", "main.py", "server.py", "api.py", "application.py"],
                "router_patterns": ["router", "routes", "urls.py", "endpoints"],
                "schema_patterns": ["schema", "model", "dto", "types"],
                "file_extensions": [".py"]
            },
            "JavaScript": {
                "entry_points": ["app.js", "server.js", "index.js", "api.js", "main.js"],
                "router_patterns": ["router", "routes", "controller", "api.js"],
                "schema_patterns": ["schema", "model", "type", "interface", "dto"],
                "file_extensions": [".js", ".ts", ".jsx", ".tsx"]
            },
            "TypeScript": {
                "entry_points": ["app.ts", "server.ts", "index.ts", "api.ts", "main.ts"],
                "router_patterns": ["router", "routes", "controller", "api.ts"],
                "schema_patterns": ["schema", "model", "type", "interface", "dto"],
                "file_extensions": [".ts", ".tsx"]
            },
            "Java": {
                "entry_points": ["Application.java", "Main.java", "ApiApplication.java"],
                "router_patterns": ["Controller", "Resource", "Endpoint", "Route"],
                "schema_patterns": ["DTO", "Model", "Entity", "Schema"],
                "file_extensions": [".java"]
            },
            "Ruby": {
                "entry_points": ["application.rb", "api.rb", "server.rb"],
                "router_patterns": ["routes", "controller"],
                "schema_patterns": ["model", "schema"],
                "file_extensions": [".rb"]
            },
            "Go": {
                "entry_points": ["main.go", "server.go", "api.go", "app.go"],
                "router_patterns": ["handler", "controller", "route"],
                "schema_patterns": ["model", "schema", "type", "struct"],
                "file_extensions": [".go"]
            },
            "PHP": {
                "entry_points": ["index.php", "api.php", "app.php"],
                "router_patterns": ["controller", "route", "api"],
                "schema_patterns": ["model", "entity", "schema"],
                "file_extensions": [".php"]
            }
        }
        
        # Framework-specific patterns (for improved precision)
        framework_patterns = {
            "fastapi": {
                "entry_pattern": ["app = FastAPI()", "fastapi.FastAPI()", "from fastapi import"],
                "router_pattern": ["APIRouter", "@app."],
                "file_detection": lambda f: any(pattern in f.lower() for pattern in ["/routes/", "/api/"])
            },
            "flask": {
                "entry_pattern": ["Flask(__name__", "from flask import"],
                "router_pattern": ["@app.route", "flask.Blueprint"],
                "file_detection": lambda f: any(pattern in f.lower() for pattern in ["/routes/", "/views/"])
            },
            "express": {
                "entry_pattern": ["express()", "require('express')", "import express"],
                "router_pattern": ["router", "app.use", "app.get", "app.post"],
                "file_detection": lambda f: any(pattern in f.lower() for pattern in ["/routes/", "/controllers/"])
            },
            "django": {
                "entry_pattern": ["Django", "urls.py"],
                "router_pattern": ["urlpatterns", "path("],
                "file_detection": lambda f: "urls.py" in f.lower() or "/views/" in f.lower()
            },
            "spring": {
                "entry_pattern": ["@SpringBootApplication", "SpringApplication.run"],
                "router_pattern": ["@RestController", "@Controller", "@RequestMapping"],
                "file_detection": lambda f: any(pattern in f.lower() for pattern in ["controller", "resource"])
            },
        }
        
        # 1. First scan - Find API directories
        api_directories = set()
        for file in files:
            for pattern in api_dir_patterns:
                if pattern in file.lower():
                    # Get the directory containing the pattern
                    parts = file.split('/')
                    dir_index = 0
                    for i, part in enumerate(parts):
                        if pattern.strip('/') in part.lower():
                            dir_index = i
                            break
                    
                    if dir_index > 0:
                        api_dir = '/'.join(parts[:dir_index+1])
                        api_directories.add(api_dir)
        
        api_components["api_directories"] = sorted(list(api_directories))
        
        # 2. Now process each file by category
        for file in files:
            file_lower = file.lower()
            filename = os.path.basename(file_lower)
            file_ext = os.path.splitext(file_lower)[1]
            
            # Check if file is in an API directory
            in_api_dir = any(file.startswith(api_dir) for api_dir in api_directories)
            
            # Analyze file content for key patterns if needed
            file_content = None
            
            # 2.1 API Entry points (main app files)
            is_entry_point = False
            
            # Check filename-based patterns for entry points
            for lang, patterns in lang_specific_patterns.items():
                if any(filename == entry_file.lower() for entry_file in patterns["entry_points"]):
                    is_entry_point = True
                    break
            
            # If not identified by filename, check API directories for main file patterns
            if not is_entry_point and in_api_dir:
                # For files in API directories, check for main app patterns
                if any(file_ext == ext for lang_patterns in lang_specific_patterns.values() 
                       for ext in lang_patterns["file_extensions"]):
                    
                    # Check for entry point patterns in content (lazy load content if needed)
                    for framework, patterns in framework_patterns.items():
                        if file_content is None:
                            try:
                                with open(os.path.join(repo_path, file), 'r', encoding='utf-8', errors='ignore') as f:
                                    file_content = f.read()
                            except Exception:
                                file_content = ""  # Failed to read file
                        
                        if any(pattern in file_content for pattern in patterns["entry_pattern"]):
                            is_entry_point = True
                            break
            
            if is_entry_point:
                api_components["entry_points"].append(file)
            
            # 2.2 Router files
            is_router = False
            
            # Check filename-based patterns
            if any(router_pattern in file_lower for lang_patterns in lang_specific_patterns.values() 
                  for router_pattern in lang_patterns["router_patterns"]):
                is_router = True
            
            # If not identified by filename, check content for router patterns
            if not is_router and in_api_dir:
                if any(file_ext == ext for lang_patterns in lang_specific_patterns.values() 
                       for ext in lang_patterns["file_extensions"]):
                    
                    # Check for router patterns in content (lazy load content if needed)
                    for framework, patterns in framework_patterns.items():
                        if file_content is None:
                            try:
                                with open(os.path.join(repo_path, file), 'r', encoding='utf-8', errors='ignore') as f:
                                    file_content = f.read()
                            except Exception:
                                file_content = ""  # Failed to read file
                        
                        if any(pattern in file_content for pattern in patterns["router_pattern"]):
                            is_router = True
                            break
            
            if is_router:
                api_components["routers"].append(file)
            
            # 2.3 Handler/Controller files
            # Files in api/controllers or similar directories
            handler_patterns = ["/controllers/", "/handlers/", "service", "controller"]
            if any(pattern in file_lower for pattern in handler_patterns) and not is_router and not is_entry_point:
                if file_ext in [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"]:
                    api_components["handlers"].append(file)
            
            # 2.4 Schema/model files
            schema_patterns = ["schema", "model", "entity", "dto", "type", "interface"]
            if any(pattern in file_lower for pattern in schema_patterns):
                if any(file_ext == ext for lang_patterns in lang_specific_patterns.values() 
                       for ext in lang_patterns["file_extensions"]):
                    api_components["schemas"].append(file)
            
            # 2.5 Config files specifically for APIs
            if in_api_dir and any(pattern in file_lower for pattern in ["config", "settings"]):
                api_components["config"].append(file)
        
        # Filter out empty categories
        api_components = {k: v for k, v in api_components.items() if v}
        
        # Calculate stats
        total_api_files = sum(len(files) for files in api_components.values())
        
        # Create result
        result = {
            "success": True,
            "message": f"Identified {total_api_files} API-related files across {len(api_components)} categories",
            "api_components": api_components,
            "metrics": {
                "total_api_files": total_api_files,
                "api_directories": len(api_components.get("api_directories", [])),
                "primary_language": primary_language
            }
        }
        
        return result
    except Exception as e:
        logger.error(f"Error identifying API components: {str(e)}")
        return {
            "success": False,
            "message": f"Error identifying API components: {str(e)}",
            "api_components": {}
        }

def generate_repo_tree(repo_path: str) -> Dict[str, Any]:
    """
    Generate a visually enhanced text-based directory tree for the repository.
    
    Features:
    - Shows the repository structure with intuitive tree connectors (├─→, └─→)
    - Includes file and directory icons for better visual distinction
    - Starts with the repository name at the top
    - Maintains proper vertical connection lines
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary containing the text tree representation
    """
    try:
        # Normalize repository path
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "message": f"Repository path does not exist: {repo_path}",
                "text_tree": ""
            }
            
        scanner = RepoScanner(
            repo_path=repo_path,
            use_gitignore=True
        )
        
        # Generate text tree
        text_tree = scanner.create_tree()
        
        return {
            "success": True,
            "message": "Repository tree generated successfully",
            "text_tree": text_tree
        }
        
    except Exception as e:
        logger.error(f"Error generating repository tree: {str(e)}")
        return {
            "success": False,
            "message": f"Error generating repository tree: {str(e)}",
            "text_tree": ""
        }