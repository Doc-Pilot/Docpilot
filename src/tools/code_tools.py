"""
Code Analysis Tools
==================

This module provides functions for code analysis using tree-sitter parsing.
These functions are optimized for tool calling by LLMs with well-structured inputs and outputs.
"""

import os
import re
import json
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from ..utils.code_parser import (
    parse_file,
    parse_code,
    detect_language,
    is_supported_language,
    CodeModule,
    CodeFunction,
    CodeClass,
    extract_structure
)

def get_code_structure(file_path: str) -> Dict[str, Any]:
    """
    Extract the complete structure of a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary with the code structure including functions, classes, and docstrings
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    
    if not is_supported_language(file_path):
        return {"success": False, "error": f"Unsupported file type: {file_path}"}
    
    # Use extract_structure which has more robust function detection
    parsed_structure = extract_structure(file_path)
    if not parsed_structure:
        return {"success": False, "error": f"Failed to parse file: {file_path}"}
    
    # Create result with correct format
    result = {
        "success": True,
        "file_path": file_path,
        "language": parsed_structure["language"],
        "module_docstring": parsed_structure["docstring"],
        "functions": parsed_structure["functions"],
        "classes": parsed_structure["classes"]
    }
    
    return result

def parse_code_snippet(code: str, language: str) -> Dict[str, Any]:
    """
    Parse a code snippet and extract its structure.
    
    Args:
        code: Code snippet as string
        language: Programming language of the code (e.g., 'python', 'javascript')
        
    Returns:
        Dictionary with the extracted code structure
    """
    if not code or not language:
        return {"success": False, "error": "Code or language not provided"}
    
    module = parse_code(code, language)
    if not module:
        return {"success": False, "error": f"Failed to parse {language} code"}
    
    result = {
        "success": True,
        "language": module.language,
        "functions": [],
        "classes": []
    }
    
    # Add functions
    for func in module.functions:
        result["functions"].append({
            "name": func.name,
            "params": func.params,
            "docstring": func.docstring
        })
    
    # Add classes with their methods
    for cls in module.classes:
        class_info = {
            "name": cls.name,
            "docstring": cls.docstring,
            "methods": []
        }
        
        for method in cls.methods:
            class_info["methods"].append({
                "name": method.name,
                "params": method.params,
                "docstring": method.docstring
            })
            
        result["classes"].append(class_info)
    
    return result

def find_undocumented_elements(file_path: str) -> Dict[str, Any]:
    """
    Find undocumented functions, classes, and methods in a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary listing undocumented elements with their locations
    """
    structure = get_code_structure(file_path)
    if not structure.get("success", False):
        return structure
    
    undocumented = {
        "success": True,
        "file_path": file_path,
        "language": structure["language"],
        "undocumented_functions": [],
        "undocumented_classes": [],
        "undocumented_methods": []
    }
    
    # Check functions
    for func in structure["functions"]:
        if not func.get("docstring"):
            undocumented["undocumented_functions"].append({
                "name": func["name"],
                "start_line": func["start_line"],
                "end_line": func["end_line"]
            })
    
    # Check classes and methods
    for cls in structure["classes"]:
        if not cls.get("docstring"):
            undocumented["undocumented_classes"].append({
                "name": cls["name"],
                "start_line": cls["start_line"],
                "end_line": cls["end_line"]
            })
        
        for method in cls.get("methods", []):
            if not method.get("docstring"):
                undocumented["undocumented_methods"].append({
                    "class_name": cls["name"],
                    "method_name": method["name"],
                    "start_line": method["start_line"],
                    "end_line": method["end_line"]
                })
    
    # Add summary statistics
    undocumented["statistics"] = {
        "total_functions": len(structure["functions"]),
        "undocumented_functions": len(undocumented["undocumented_functions"]),
        "total_classes": len(structure["classes"]),
        "undocumented_classes": len(undocumented["undocumented_classes"]),
        "total_methods": sum(len(cls.get("methods", [])) for cls in structure["classes"]),
        "undocumented_methods": len(undocumented["undocumented_methods"]),
        "documentation_coverage": calculate_documentation_coverage(structure)
    }
    
    return undocumented

def calculate_documentation_coverage(structure: Dict[str, Any]) -> float:
    """
    Calculate the documentation coverage percentage for a code structure.
    
    Args:
        structure: Code structure dictionary from get_code_structure
        
    Returns:
        Percentage of documented elements (0-100)
    """
    total_elements = len(structure["functions"]) + len(structure["classes"])
    documented_elements = 0
    
    # Count documented functions
    for func in structure["functions"]:
        if func.get("docstring"):
            documented_elements += 1
    
    # Count documented classes
    for cls in structure["classes"]:
        if cls.get("docstring"):
            documented_elements += 1
        
        # Add methods to total count
        total_elements += len(cls.get("methods", []))
        
        # Count documented methods
        for method in cls.get("methods", []):
            if method.get("docstring"):
                documented_elements += 1
    
    if total_elements == 0:
        return 100.0  # If there are no elements, consider it fully documented
    
    return round((documented_elements / total_elements) * 100, 2)

def get_function_details(file_path: str, function_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific function in a file.
    
    Args:
        file_path: Path to the code file
        function_name: Name of the function to find
        
    Returns:
        Dictionary with function details or error
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    
    module = parse_file(file_path)
    if not module:
        return {"success": False, "error": f"Failed to parse file: {file_path}"}
    
    # Try to find the function in the module
    for func in module.functions:
        if func.name == function_name:
            return {
                "success": True,
                "name": func.name,
                "params": func.params,
                "docstring": func.docstring,
                "body": func.body,
                "start_line": func.start_line,
                "end_line": func.end_line,
                "language": module.language
            }
    
    # Try to find the function as a method in a class
    for cls in module.classes:
        for method in cls.methods:
            if method.name == function_name:
                return {
                    "success": True,
                    "name": method.name,
                    "class_name": cls.name,
                    "is_method": True,
                    "params": method.params,
                    "docstring": method.docstring,
                    "body": method.body,
                    "start_line": method.start_line,
                    "end_line": method.end_line,
                    "language": module.language
                }
    
    return {
        "success": False,
        "error": f"Function '{function_name}' not found in {file_path}"
    }

def get_class_details(file_path: str, class_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific class in a file.
    
    Args:
        file_path: Path to the code file
        class_name: Name of the class to find
        
    Returns:
        Dictionary with class details including its methods
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    
    module = parse_file(file_path)
    if not module:
        return {"success": False, "error": f"Failed to parse file: {file_path}"}
    
    # Try to find the class in the module
    for cls in module.classes:
        if cls.name == class_name:
            result = {
                "success": True,
                "name": cls.name,
                "docstring": cls.docstring,
                "start_line": cls.start_line,
                "end_line": cls.end_line,
                "language": module.language,
                "methods": []
            }
            
            # Add methods
            for method in cls.methods:
                result["methods"].append({
                    "name": method.name,
                    "params": method.params,
                    "docstring": method.docstring,
                    "body": method.body,
                    "start_line": method.start_line,
                    "end_line": method.end_line
                })
                
            return result
    
    return {
        "success": False,
        "error": f"Class '{class_name}' not found in {file_path}"
    }

def get_supported_languages() -> Dict[str, Any]:
    """
    Get a list of programming languages supported by the code parser.
    
    Returns:
        Dictionary with list of supported languages and file extensions
    """
    from ..utils.code_parser import FILE_EXT_TO_LANGUAGE
    
    languages = set(FILE_EXT_TO_LANGUAGE.values())
    extensions_by_language = {}
    
    # Group extensions by language
    for ext, lang in FILE_EXT_TO_LANGUAGE.items():
        if lang not in extensions_by_language:
            extensions_by_language[lang] = []
        extensions_by_language[lang].append(ext)
    
    return {
        "success": True,
        "supported_languages": sorted(list(languages)),
        "file_extensions": extensions_by_language
    } 