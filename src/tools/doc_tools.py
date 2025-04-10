"""
Documentation Analysis Tools
=======================

This module provides functions for scanning and analyzing documentation within repositories.
These functions are optimized for tool calling by LLMs with standardized input parameters and return formats.
"""

import os
import re
import logging
import subprocess
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from ..utils.doc_scanner import (
    scan_documentation,
    get_doc_type,
    extract_title,
    get_changed_files,
    find_related_docs,
    should_update_documentation,
    check_for_significant_changes,
    get_last_modified
)
from ..utils.logging import core_logger  # Import core_logger

# Set up module logger
logger = core_logger()

def standard_error_response(error_message: str, error_type: str = "unexpected_error") -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        error_message: The error message
        error_type: The type of error
        
    Returns:
        Standardized error response dictionary
    """
    logger.error(f"{error_type}: {error_message}", exc_info=True)
    return {
        "success": False, 
        "error": error_message, 
        "error_type": error_type
    }

def scan_docs(repo_path: str, skip_ignored: bool = True) -> Dict[str, Any]:
    """
    Scan a repository for documentation files.
    
    Args:
        repo_path: Path to the git repository
        skip_ignored: Whether to skip files ignored by git (default: True)
        
    Returns:
        Dictionary with documentation files and their metadata
    """
    # Validate repository path
    if not os.path.exists(repo_path):
        return standard_error_response(f"Repository path not found: {repo_path}", "file_not_found")
    
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return standard_error_response(f"Not a git repository: {repo_path}", "invalid_repo")
    
    try:
        doc_files = scan_documentation(repo_path, skip_ignored=skip_ignored)
        
        if not doc_files:
            return {
                "success": True,
                "message": "No documentation files found in the repository",
                "doc_files": [],
                "file_count": 0
            }
        
        # Convert to a list for easier consumption by LLMs
        doc_list = []
        for file_path, metadata in doc_files.items():
            doc_list.append({
                "path": file_path,
                "type": metadata.get("type", "unknown"),
                "title": metadata.get("title", os.path.basename(file_path)),
                "last_modified": metadata.get("last_modified", "")
            })
        
        return {
            "success": True,
            "message": f"Found {len(doc_list)} documentation files",
            "doc_files": doc_list,
            "file_count": len(doc_list)
        }
    except Exception as e:
        return standard_error_response(f"Error scanning documentation: {str(e)}", "scan_error")

def find_docs_to_update(repo_path: str, base_ref: str = "HEAD~1", target_ref: str = "HEAD", skip_ignored: bool = True) -> Dict[str, Any]:
    """
    Find documentation that needs updating based on code changes.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base git reference (e.g., 'HEAD~1', a commit hash, or branch name)
        target_ref: Target git reference (e.g., 'HEAD', a commit hash, or branch name)
        skip_ignored: Whether to skip files ignored by git (default: True)
        
    Returns:
        Dictionary with documentation files that need updating
    """
    # Validate repository path
    if not os.path.exists(repo_path):
        return standard_error_response(f"Repository path not found: {repo_path}", "file_not_found")
    
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return standard_error_response(f"Not a git repository: {repo_path}", "invalid_repo")
    
    try:
        # Get changes between the git references
        changed_files = get_changed_files(repo_path, base_ref, target_ref)
        
        # If no changes detected
        if not changed_files:
            return {
                "success": True,
                "message": "No changes detected between references",
                "docs_to_update": [],
                "changed_files": []
            }
        
        # Scan for documentation files
        doc_files = scan_documentation(repo_path, skip_ignored=skip_ignored)
        if not doc_files:
            return {
                "success": True,
                "message": "No documentation files found in the repository",
                "docs_to_update": [],
                "changed_files": changed_files
            }
        
        # Find related documentation files
        related_docs = find_related_docs(changed_files, doc_files)
        
        # Determine which docs need updates
        docs_to_update = []
        for doc_path, related_files in related_docs.items():
            if should_update_documentation(repo_path, doc_path, related_files):
                doc_meta = doc_files.get(doc_path, {})
                docs_to_update.append({
                    "path": doc_path,
                    "type": doc_meta.get("type", "documentation"),
                    "title": doc_meta.get("title", os.path.basename(doc_path)),
                    "related_files": related_files,
                    "last_modified": doc_meta.get("last_modified", "")
                })
        
        return {
            "success": True,
            "message": f"Found {len(docs_to_update)} documentation files that need updating",
            "docs_to_update": docs_to_update,
            "changed_files": changed_files,
            "all_docs": list(doc_files.keys())
        }
    except subprocess.SubprocessError as e:
        logger.error(f"Git subprocess error: {str(e)}", exc_info=True)
        return standard_error_response(f"Git command failed: {str(e)}", "git_error")
    except Exception as e:
        logger.error(f"Error finding docs to update: {str(e)}", exc_info=True)
        return standard_error_response(f"Error finding docs to update: {str(e)}", "unexpected_error")

def get_doc_update_suggestions(repo_path: str, doc_path: str, related_files: List[str]) -> Dict[str, Any]:
    """
    Generate suggestions for updating a documentation file based on code changes.
    
    Args:
        repo_path: Path to the git repository
        doc_path: Path to the documentation file, relative to repo_path
        related_files: List of related changed files
        
    Returns:
        Dictionary with update suggestions
    """
    # Validate repository path
    if not os.path.exists(repo_path):
        return standard_error_response(f"Repository path not found: {repo_path}", "file_not_found")
    
    # Validate doc path
    doc_abs_path = os.path.join(repo_path, doc_path)
    if not os.path.exists(doc_abs_path):
        return standard_error_response(f"Documentation file not found: {doc_path}", "file_not_found")
    
    try:
        # Check if doc itself has changed
        if doc_path in related_files:
            return {
                "success": True,
                "message": "This documentation file has been modified directly",
                "doc_path": doc_path,
                "suggestion_type": "modified",
                "update_needed": False
            }
        
        # Get doc content
        try:
            with open(doc_abs_path, 'r', encoding='utf-8') as f:
                doc_content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"Unable to read {doc_path} as text, may be binary file")
            return standard_error_response(f"Unable to read {doc_path} as text", "encoding_error")
        
        # Get significant changes
        significant_changes = check_for_significant_changes(repo_path, related_files)
        
        # Read related files to provide context
        related_file_content = {}
        for file in related_files[:5]:  # Limit to prevent overwhelming response
            file_path = os.path.join(repo_path, file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        related_file_content[file] = f.read()
                except Exception as file_error:
                    logger.warning(f"Error reading related file {file}: {str(file_error)}", exc_info=True)
                    # Skip files we can't read but don't fail the whole operation
                    continue
        
        # Generate update suggestions
        suggestions = []
        
        # Add basic suggestions based on what changed
        for file_path, content in related_file_content.items():
            # Look for function and class definitions
            func_matches = re.findall(r'def\s+(\w+)\s*\(', content)
            class_matches = re.findall(r'class\s+(\w+)\s*\(', content)
            
            # Check if they're mentioned in the doc
            for func in func_matches:
                if func not in doc_content:
                    suggestions.append({
                        "type": "function",
                        "name": func,
                        "file": file_path,
                        "suggestion": f"Add documentation for function `{func}`"
                    })
            
            for cls in class_matches:
                if cls not in doc_content:
                    suggestions.append({
                        "type": "class",
                        "name": cls,
                        "file": file_path,
                        "suggestion": f"Add documentation for class `{cls}`"
                    })
        
        return {
            "success": True,
            "message": "Generated documentation update suggestions",
            "doc_path": doc_path,
            "related_files": related_files,
            "has_significant_changes": significant_changes.get("has_significant_changes", False),
            "change_details": significant_changes.get("details", []),
            "suggestions": suggestions,
            "update_needed": significant_changes.get("has_significant_changes", False) or len(suggestions) > 0
        }
    except Exception as e:
        logger.error(f"Error generating update suggestions: {str(e)}", exc_info=True)
        return standard_error_response(f"Error generating update suggestions: {str(e)}", "suggestions_error")

def get_doc_content(repo_path: str, doc_path: str) -> Dict[str, Any]:
    """
    Get the content of a documentation file.
    
    Args:
        repo_path: Path to the git repository
        doc_path: Path to the documentation file, relative to repo_path
        
    Returns:
        Dictionary with doc content and metadata
    """
    # Validate repository path
    if not os.path.exists(repo_path):
        return standard_error_response(f"Repository path not found: {repo_path}", "file_not_found")
    
    # Validate doc path
    doc_abs_path = os.path.join(repo_path, doc_path)
    if not os.path.exists(doc_abs_path):
        return standard_error_response(f"Documentation file not found: {doc_path}", "file_not_found")
    
    try:
        # Read the file content
        with open(doc_abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get document metadata
        doc_type = get_doc_type(doc_path)
        title = extract_title(doc_abs_path)
        last_modified = get_last_modified(repo_path, doc_path)
        
        # Get file stats
        file_stats = os.stat(doc_abs_path)
        file_size = file_stats.st_size
        
        return {
            "success": True,
            "message": "Successfully retrieved document content",
            "doc_path": doc_path,
            "content": content,
            "title": title,
            "type": doc_type,
            "last_modified": last_modified,
            "file_size": file_size,
            "character_count": len(content),
            "line_count": content.count('\n') + 1
        }
    except UnicodeDecodeError:
        logger.warning(f"Unable to read {doc_path} as text, may be binary file")
        return standard_error_response(f"Unable to read {doc_path} as text", "encoding_error")
    except Exception as e:
        logger.error(f"Error reading documentation file: {str(e)}", exc_info=True)
        return standard_error_response(f"Error reading documentation file: {str(e)}", "file_read_error")
