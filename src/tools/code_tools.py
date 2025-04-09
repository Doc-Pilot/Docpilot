"""
Code Analysis Tools
==================

This module provides functions for code analysis using tree-sitter parsing.
These functions are optimized for tool calling by LLMs with well-structured inputs and outputs.
"""

# Importing Dependencies
import os
from typing import Dict, Any

from ..utils.code_parser import (
    parse_file,
    parse_code,
    is_supported_language,
    extract_structure
)
from ..utils.logging import core_logger

# Set up logger
logger = core_logger()

def get_code_structure(file_path: str) -> Dict[str, Any]:
    """
    Extract the complete structure of a code file.
    
    Args:
        file_path: Path to the code file
        
    Returns:
        Dictionary with the code structure including functions, classes, and docstrings
    """
    logger.info(f"Getting code structure for {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"success": False, "error": f"File not found: {file_path}"}
    
    if not is_supported_language(file_path):
        logger.warning(f"Unsupported file type for structure extraction: {file_path}")
        return {"success": False, "error": f"Unsupported file type: {file_path}"}
    
    # Use extract_structure which has more robust function detection
    try:
        parsed_structure = extract_structure(file_path)
        if not parsed_structure:
            logger.error(f"Failed to parse file: {file_path}")
            return {"success": False, "error": f"Failed to parse file: {file_path}"}
    except Exception as e:
        logger.exception(f"Error extracting structure from {file_path}: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Error parsing file: {str(e)}"}
    
    # Create result with correct format
    result = {
        "success": True,
        "file_path": file_path,
        "language": parsed_structure["language"],
        "module_docstring": parsed_structure["docstring"],
        "functions": parsed_structure["functions"],
        "classes": parsed_structure["classes"]
    }
    
    logger.info(f"Successfully extracted structure for {file_path}")
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
    logger.info(f"Parsing code snippet for language: {language}")
    if not code or not language:
        logger.error("Code snippet or language not provided")
        return {"success": False, "error": "Code or language not provided"}
    
    try:
        module = parse_code(code, language)
        if not module:
            logger.error(f"Failed to parse {language} code snippet")
            return {"success": False, "error": f"Failed to parse {language} code"}
    except Exception as e:
        logger.exception(f"Error parsing {language} code snippet: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Error parsing code: {str(e)}"}
    
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
    
    logger.info(f"Successfully parsed code snippet for {language}")
    return result

def get_function_details(file_path: str, function_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific function in a file.
    
    Args:
        file_path: Path to the code file
        function_name: Name of the function to find
        
    Returns:
        Dictionary with function details or error
    """
    logger.info(f"Getting details for function '{function_name}' in {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        module = parse_file(file_path)
        if not module:
            logger.error(f"Failed to parse file for function details: {file_path}")
            return {"success": False, "error": f"Failed to parse file: {file_path}"}
    except Exception as e:
        logger.exception(f"Error parsing file {file_path} for function details: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Error parsing file: {str(e)}"}
    
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
    
    logger.warning(f"Function '{function_name}' not found in {file_path}")
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
    logger.info(f"Getting details for class '{class_name}' in {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        module = parse_file(file_path)
        if not module:
            logger.error(f"Failed to parse file for class details: {file_path}")
            return {"success": False, "error": f"Failed to parse file: {file_path}"}
    except Exception as e:
        logger.exception(f"Error parsing file {file_path} for class details: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Error parsing file: {str(e)}"}
    
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
    
    logger.warning(f"Class '{class_name}' not found in {file_path}")
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
    
    logger.info("Getting list of supported languages")
    logger.debug(f"Supported languages: {languages}")
    return {
        "success": True,
        "supported_languages": sorted(list(languages)),
        "file_extensions": extensions_by_language
    } 