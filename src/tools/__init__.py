"""
Tools Module
===========

This module provides a collection of tools that can be used by LLM agents 
to interact with code and documentation. Each tool is a standalone function
that can be called directly or via an agent system.

Categories:
- Code Analysis: Tools for parsing and analyzing code structure
- Documentation: Tools for generating and evaluating documentation
- API Tools: Tools for API documentation and analysis
- Repository: Tools for interacting with repositories
"""

import os
import json
from typing import Dict, List, Optional, Union, Any
from pathlib import Path

from ..utils import (
    # Code parsing
    parse_file,
    parse_code,
    extract_structure,
    extract_api_routes,
    detect_language,
    get_supported_languages,
    CodeModule,
    APIDocumentation,
    
    # Doc scanning
    scan_file_docstrings,
    DocScanner,
    
    # Repository scanning
    RepoScanner,
    
    # Logging
    logger
)

# ============================================================================
# Code Analysis Tools
# ============================================================================

def extract_code_structure(file_path: str) -> Dict[str, Any]:
    """
    Extract the structure of a code file, including functions, classes, and methods.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary containing the code structure
    """
    logger.info(f"Extracting code structure from {file_path}")
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    module = parse_file(file_path)
    if not module:
        return {"error": f"Failed to parse file: {file_path}"}
    
    # Convert to a dictionary for easy serialization
    return {
        "file_path": file_path,
        "language": module.language,
        "functions": [
            {
                "name": func.name,
                "params": func.params,
                "docstring": func.docstring,
                "start_line": func.start_line,
                "end_line": func.end_line
            }
            for func in module.functions
        ],
        "classes": [
            {
                "name": cls.name,
                "docstring": cls.docstring,
                "start_line": cls.start_line,
                "end_line": cls.end_line,
                "methods": [
                    {
                        "name": method.name,
                        "params": method.params,
                        "docstring": method.docstring,
                        "start_line": method.start_line,
                        "end_line": method.end_line
                    }
                    for method in cls.methods
                ]
            }
            for cls in module.classes
        ],
        "imports": module.imports,
        "docstring": module.docstring
    }

def find_undocumented_elements(file_path: str) -> Dict[str, Any]:
    """
    Find undocumented functions, classes, and methods in a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary listing undocumented elements
    """
    logger.info(f"Finding undocumented elements in {file_path}")
    
    structure = extract_code_structure(file_path)
    if "error" in structure:
        return structure
    
    undocumented = {
        "file_path": file_path,
        "functions": [
            func["name"] 
            for func in structure["functions"] 
            if not func.get("docstring")
        ],
        "classes": [
            cls["name"] 
            for cls in structure["classes"] 
            if not cls.get("docstring")
        ],
        "methods": []
    }
    
    # Process methods
    for cls in structure["classes"]:
        for method in cls.get("methods", []):
            if not method.get("docstring"):
                undocumented["methods"].append(f"{cls['name']}.{method['name']}")
    
    # Add summary stats
    undocumented["stats"] = {
        "total_functions": len(structure["functions"]),
        "undocumented_functions": len(undocumented["functions"]),
        "total_classes": len(structure["classes"]),
        "undocumented_classes": len(undocumented["classes"]),
        "total_methods": sum(len(cls.get("methods", [])) for cls in structure["classes"]),
        "undocumented_methods": len(undocumented["methods"])
    }
    
    return undocumented

def analyze_code_complexity(file_path: str) -> Dict[str, Any]:
    """
    Analyze the complexity of a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary with complexity metrics
    """
    logger.info(f"Analyzing code complexity of {file_path}")
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}
    
    # Get code structure
    module = parse_file(file_path)
    if not module:
        return {"error": f"Failed to parse file: {file_path}"}
    
    # Calculate basic metrics
    lines = content.split('\n')
    code_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    
    # Count control structures
    control_keywords = ['if', 'else', 'elif', 'for', 'while', 'try', 'except', 'with']
    control_count = 0
    for line in code_lines:
        for keyword in control_keywords:
            if re.search(r'\b' + keyword + r'\b', line):
                control_count += 1
                break
    
    # Calculate metrics
    metrics = {
        "file_path": file_path,
        "language": module.language,
        "total_lines": len(lines),
        "code_lines": len(code_lines),
        "blank_lines": len(lines) - len(code_lines),
        "function_count": len(module.functions),
        "class_count": len(module.classes),
        "method_count": sum(len(cls.methods) for cls in module.classes),
        "control_structures": control_count,
        "average_function_length": sum(func.end_line - func.start_line for func in module.functions) / len(module.functions) if module.functions else 0,
        "complexity_score": (
            len(code_lines) * 0.1 + 
            control_count * 0.3 + 
            len(module.functions) * 0.5 + 
            len(module.classes) * 0.7
        )
    }
    
    return metrics

# ============================================================================
# Documentation Tools
# ============================================================================

def analyze_docstring_quality(file_path: str) -> Dict[str, Any]:
    """
    Analyze the quality of docstrings in a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary with docstring quality metrics
    """
    logger.info(f"Analyzing docstring quality in {file_path}")
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    # Scan docstrings
    doc_stats = scan_file_docstrings(file_path)
    if not doc_stats:
        return {"error": f"Failed to scan docstrings in {file_path}"}
    
    # Get code structure for additional context
    module = parse_file(file_path)
    if not module:
        return {"error": f"Failed to parse file: {file_path}"}
    
    # Calculate coverage percentage
    total_elements = len(module.functions) + len(module.classes) + sum(len(cls.methods) for cls in module.classes)
    documented_elements = doc_stats.documented_functions + doc_stats.documented_classes + doc_stats.documented_methods
    
    coverage = (documented_elements / total_elements * 100) if total_elements > 0 else 0
    
    # Analyze completeness of docstrings
    completeness_scores = []
    
    # Check functions
    for func in module.functions:
        if func.docstring:
            score = _calculate_docstring_completeness(func.docstring, func.params)
            completeness_scores.append(score)
    
    # Check classes
    for cls in module.classes:
        if cls.docstring:
            score = _calculate_docstring_completeness(cls.docstring)
            completeness_scores.append(score)
            
        # Check methods
        for method in cls.methods:
            if method.docstring:
                score = _calculate_docstring_completeness(method.docstring, method.params)
                completeness_scores.append(score)
    
    avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
    
    return {
        "file_path": file_path,
        "coverage_percent": round(coverage, 2),
        "documented_functions": doc_stats.documented_functions,
        "total_functions": len(module.functions),
        "documented_classes": doc_stats.documented_classes,
        "total_classes": len(module.classes),
        "documented_methods": doc_stats.documented_methods,
        "total_methods": sum(len(cls.methods) for cls in module.classes),
        "average_completeness": round(avg_completeness * 100, 2),
        "quality_score": round((coverage + avg_completeness * 100) / 2, 2)
    }

def _calculate_docstring_completeness(docstring: str, params: str = None) -> float:
    """
    Calculate the completeness of a docstring.
    
    Args:
        docstring: The docstring to analyze
        params: Optional parameter string to check against docstring
        
    Returns:
        Completeness score between 0.0 and 1.0
    """
    if not docstring:
        return 0.0
    
    score = 0.0
    max_score = 4.0  # Base max score
    
    # Check for description (simple existence check)
    if len(docstring.strip()) > 0:
        score += 1.0
    
    # Check for parameters section
    if params and 'param' in docstring.lower() or 'args' in docstring.lower():
        score += 1.0
        max_score += 1.0
        
        # Extract parameter names from params string
        param_names = []
        if params:
            # Simple extraction logic - could be improved
            params_clean = params.strip('()')
            if params_clean:
                param_parts = [p.strip() for p in params_clean.split(',')]
                param_names = [p.split(':')[0].split('=')[0].strip() for p in param_parts]
                param_names = [p for p in param_names if p and p != 'self' and p != 'cls']
        
        # Check if all parameters are documented
        if param_names:
            param_count = 0
            for param in param_names:
                if param in docstring:
                    param_count += 1
            
            if param_count > 0:
                param_coverage = param_count / len(param_names)
                score += param_coverage
    
    # Check for returns section
    if 'return' in docstring.lower():
        score += 1.0
    
    # Check for examples
    if 'example' in docstring.lower():
        score += 1.0
    
    # Normalize to 0.0-1.0 range
    return score / max_score

# ============================================================================
# API Documentation Tools
# ============================================================================

def extract_api_documentation(file_path: str) -> Dict[str, Any]:
    """
    Extract API documentation from a file (FastAPI or Flask).
    
    Args:
        file_path: Path to the API file
        
    Returns:
        Dictionary with API documentation
    """
    logger.info(f"Extracting API documentation from {file_path}")
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    api_doc = extract_api_routes(file_path)
    if not api_doc:
        return {"error": f"No API routes found in {file_path}"}
    
    # Convert to dictionary for serialization
    result = {
        "file_path": file_path,
        "routes": []
    }
    
    for route in api_doc.routes:
        route_dict = {
            "path": route.path,
            "method": route.http_method,
            "function": route.function_name,
            "description": route.description,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.type_hint,
                    "required": param.required,
                    "description": param.description,
                    "default": param.default_value
                }
                for param in route.parameters
            ]
        }
        
        result["routes"].append(route_dict)
    
    return result

def generate_api_markdown(file_path: str) -> Dict[str, Any]:
    """
    Generate Markdown API documentation for a file.
    
    Args:
        file_path: Path to the API file
        
    Returns:
        Dictionary with Markdown content
    """
    logger.info(f"Generating API Markdown for {file_path}")
    
    api_info = extract_api_documentation(file_path)
    if "error" in api_info:
        return api_info
    
    if not api_info["routes"]:
        return {"error": "No API routes found"}
    
    # Generate Markdown
    md_lines = []
    
    # Title
    file_name = os.path.basename(file_path)
    md_lines.append(f"# API Documentation: {file_name}\n")
    
    # Group routes by path for better organization
    routes_by_path = {}
    for route in api_info["routes"]:
        path = route["path"]
        if path not in routes_by_path:
            routes_by_path[path] = []
        routes_by_path[path].append(route)
    
    # Generate documentation for each endpoint
    for path, routes in routes_by_path.items():
        md_lines.append(f"## Endpoint: `{path}`\n")
        
        for route in routes:
            # Method and function
            md_lines.append(f"### {route['method']} - `{route['function']}`\n")
            
            # Description
            if route.get("description"):
                md_lines.append(f"{route['description']}\n")
            
            # Parameters
            if route.get("parameters"):
                md_lines.append("#### Parameters\n")
                md_lines.append("| Name | Type | Required | Description |")
                md_lines.append("|------|------|----------|-------------|")
                
                for param in route["parameters"]:
                    name = param["name"]
                    type_str = param.get("type") or "any"
                    required = "Yes" if param.get("required", True) else "No"
                    default = f" (default: `{param['default']}`)" if param.get("default") else ""
                    desc = (param.get("description") or "") + default
                    
                    md_lines.append(f"| `{name}` | `{type_str}` | {required} | {desc} |")
                
                md_lines.append("")
            
            md_lines.append("---\n")
    
    return {
        "file_path": file_path,
        "markdown": "\n".join(md_lines)
    }

# ============================================================================
# Repository Tools
# ============================================================================

def scan_repository(repo_path: str) -> Dict[str, Any]:
    """
    Scan a repository to get information about its files and structure.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with repository information
    """
    logger.info(f"Scanning repository at {repo_path}")
    
    if not os.path.isdir(repo_path):
        return {"error": f"Not a valid directory: {repo_path}"}
    
    try:
        scanner = RepoScanner(repo_path)
        stats = scanner.scan()
        
        return {
            "repo_path": repo_path,
            "file_count": stats.total_files,
            "language_stats": {
                lang: {
                    "files": info.file_count,
                    "lines": info.line_count,
                    "percentage": round(info.percentage, 2)
                }
                for lang, info in stats.languages.items()
            },
            "largest_files": [
                {
                    "path": file.path,
                    "language": file.language,
                    "lines": file.line_count,
                    "size_bytes": file.size_bytes
                }
                for file in stats.largest_files[:10]  # Top 10 largest files
            ]
        }
    except Exception as e:
        return {"error": f"Error scanning repository: {str(e)}"}

def find_documentation_issues(repo_path: str) -> Dict[str, Any]:
    """
    Find documentation issues in a repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary with documentation issues
    """
    logger.info(f"Finding documentation issues in {repo_path}")
    
    if not os.path.isdir(repo_path):
        return {"error": f"Not a valid directory: {repo_path}"}
    
    try:
        # Get all code files in the repository
        scanner = RepoScanner(repo_path)
        stats = scanner.scan()
        
        # Filter for Python files (most reliable for docstring analysis)
        # Could be expanded to other languages in the future
        python_files = [
            file.path 
            for file in scanner.files 
            if file.language == "python" and not file.path.endswith("__init__.py")
        ]
        
        if not python_files:
            return {"warning": "No Python files found for docstring analysis"}
        
        # Set up scanner
        doc_scanner = DocScanner()
        
        # Analyze files
        results = {
            "repo_path": repo_path,
            "files_analyzed": len(python_files),
            "files_with_issues": [],
            "summary": {
                "total_functions": 0,
                "undocumented_functions": 0,
                "total_classes": 0,
                "undocumented_classes": 0,
                "total_methods": 0,
                "undocumented_methods": 0
            }
        }
        
        for file_path in python_files:
            issues = find_undocumented_elements(file_path)
            if "error" not in issues:
                # Only add files with actual issues
                if (issues["undocumented_functions"] or 
                    issues["undocumented_classes"] or 
                    issues["undocumented_methods"]):
                    
                    results["files_with_issues"].append({
                        "file": os.path.relpath(file_path, repo_path),
                        "undocumented_functions": issues["functions"],
                        "undocumented_classes": issues["classes"],
                        "undocumented_methods": issues["methods"]
                    })
                
                # Update summary stats
                for key in results["summary"]:
                    results["summary"][key] += issues["stats"][key]
        
        # Calculate percentages
        total_elements = (
            results["summary"]["total_functions"] + 
            results["summary"]["total_classes"] + 
            results["summary"]["total_methods"]
        )
        
        undocumented_elements = (
            results["summary"]["undocumented_functions"] + 
            results["summary"]["undocumented_classes"] + 
            results["summary"]["undocumented_methods"]
        )
        
        if total_elements > 0:
            results["summary"]["documentation_coverage"] = round(
                (total_elements - undocumented_elements) / total_elements * 100, 2
            )
        else:
            results["summary"]["documentation_coverage"] = 0
        
        return results
    except Exception as e:
        return {"error": f"Error analyzing documentation: {str(e)}"}

__all__ = [
    # Code Analysis
    "extract_code_structure",
    "find_undocumented_elements",
    "analyze_code_complexity",
    
    # Documentation
    "analyze_docstring_quality",
    
    # API Documentation
    "extract_api_documentation",
    "generate_api_markdown",
    
    # Repository
    "scan_repository",
    "find_documentation_issues"
] 