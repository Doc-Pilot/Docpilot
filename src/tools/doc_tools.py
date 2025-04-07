"""
Documentation Analysis Tools
=======================

This module provides functions for scanning and analyzing documentation within repositories.
These functions are optimized for tool calling by LLMs with standardized input parameters and return formats.
"""

import os
import re
import subprocess
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from ..utils.doc_scanner import (
    scan_documentation,
    get_doc_type,
    extract_title,
    get_last_modified,
    get_changed_files,
    find_related_docs,
    should_update_documentation,
    check_for_significant_changes
)

def scan_docs(repo_path: str) -> Dict[str, Any]:
    """
    Scan a repository for documentation files.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        Dictionary with documentation files and their metadata
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return {"success": False, "error": f"Not a git repository: {repo_path}"}
    
    try:
        doc_files = scan_documentation(repo_path)
        
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
        return {"success": False, "error": f"Error scanning documentation: {str(e)}"}

def get_doc_by_type(repo_path: str, doc_type: str) -> Dict[str, Any]:
    """
    Get documentation files of a specific type.
    
    Args:
        repo_path: Path to the git repository
        doc_type: Type of documentation (readme, api, howto, examples, etc.)
        
    Returns:
        Dictionary with documentation files of the specified type
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    scan_results = scan_docs(repo_path)
    if not scan_results.get("success", False):
        return scan_results
    
    # Filter docs by type
    type_docs = []
    for doc in scan_results.get("doc_files", []):
        if doc.get("type", "").lower() == doc_type.lower():
            type_docs.append(doc)
    
    return {
        "success": True,
        "message": f"Found {len(type_docs)} documentation files of type '{doc_type}'",
        "doc_files": type_docs,
        "file_count": len(type_docs),
        "doc_type": doc_type
    }

def get_doc_content(file_path: str) -> Dict[str, Any]:
    """
    Get the content of a documentation file.
    
    Args:
        file_path: Path to the documentation file
        
    Returns:
        Dictionary with the documentation content and metadata
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title = extract_title(file_path)
        doc_type = get_doc_type(os.path.relpath(file_path))
        
        return {
            "success": True,
            "file_path": file_path,
            "title": title,
            "type": doc_type,
            "content": content,
            "content_length": len(content),
            "is_markdown": file_path.lower().endswith('.md')
        }
    except Exception as e:
        return {"success": False, "error": f"Error reading documentation file: {str(e)}"}

def find_docs_to_update(repo_path: str, base_ref: str = "HEAD~1", target_ref: str = "HEAD") -> Dict[str, Any]:
    """
    Find documentation that needs updating based on code changes.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base git reference (e.g., 'HEAD~1', a commit hash, or branch name)
        target_ref: Target git reference (e.g., 'HEAD', a commit hash, or branch name)
        
    Returns:
        Dictionary with documentation files that need updating
    """
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return {"success": False, "error": f"Not a git repository: {repo_path}"}
    
    try:
        # Get changes between the git references
        changed_files = get_changed_files(repo_path, base_ref, target_ref)
        if not changed_files:
            return {
                "success": True,
                "message": "No changes detected between references",
                "docs_to_update": [],
                "changed_files": []
            }
        
        # Scan for documentation files
        doc_files = scan_documentation(repo_path)
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
    except Exception as e:
        return {"success": False, "error": f"Error finding docs to update: {str(e)}"}

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
    if not os.path.exists(repo_path):
        return {"success": False, "error": f"Repository path not found: {repo_path}"}
    
    doc_abs_path = os.path.join(repo_path, doc_path)
    if not os.path.exists(doc_abs_path):
        return {"success": False, "error": f"Documentation file not found: {doc_path}"}
    
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
        with open(doc_abs_path, 'r', encoding='utf-8') as f:
            doc_content = f.read()
        
        # Get significant changes
        has_significant_changes = check_for_significant_changes(repo_path, related_files)
        
        # Read related files to provide context
        related_file_content = {}
        for file in related_files[:5]:  # Limit to prevent overwhelming response
            file_path = os.path.join(repo_path, file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        related_file_content[file] = f.read()
                except Exception:
                    # Skip files we can't read
                    pass
        
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
            "has_significant_changes": has_significant_changes,
            "suggestions": suggestions,
            "update_needed": has_significant_changes or len(suggestions) > 0
        }
    except Exception as e:
        return {"success": False, "error": f"Error generating update suggestions: {str(e)}"}

def get_doc_categories() -> Dict[str, Any]:
    """
    Get the list of documentation categories that can be detected.
    
    Returns:
        Dictionary with documentation categories and their patterns
    """
    from ..utils.doc_scanner import DOC_CATEGORIES
    
    categories = {}
    for category, patterns in DOC_CATEGORIES.items():
        categories[category] = patterns
    
    return {
        "success": True,
        "categories": categories,
        "count": len(categories)
    }

def extract_doc_section(doc_path: str, section_title: str) -> Dict[str, Any]:
    """
    Extract a specific section from a documentation file.
    
    Args:
        doc_path: Path to the documentation file
        section_title: Title of the section to extract (heading content)
        
    Returns:
        Dictionary with the extracted section content
    """
    if not os.path.exists(doc_path):
        return {"success": False, "error": f"Documentation file not found: {doc_path}"}
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Determine if it's markdown or RST
        is_markdown = doc_path.lower().endswith('.md')
        
        if is_markdown:
            # Find markdown headings that match the section title
            # This pattern matches all headline levels from # to ######
            heading_pattern = r'(^|\n)#+\s*' + re.escape(section_title) + r'\s*(\n|$)'
            match = re.search(heading_pattern, content, re.IGNORECASE)
            
            if not match:
                return {
                    "success": False,
                    "error": f"Section '{section_title}' not found in {doc_path}"
                }
            
            # Find the start of the section
            section_start = match.start()
            
            # Find the start of the next section (if any)
            next_heading = re.search(r'(^|\n)#+\s+', content[section_start + 1:])
            if next_heading:
                section_end = section_start + 1 + next_heading.start()
            else:
                section_end = len(content)
            
            # Extract the section content
            section_content = content[section_start:section_end].strip()
            
            return {
                "success": True,
                "doc_path": doc_path,
                "section_title": section_title,
                "content": section_content,
                "content_length": len(section_content),
                "is_markdown": True
            }
        else:
            # For non-markdown files, do a simple string search
            if section_title not in content:
                return {
                    "success": False,
                    "error": f"Section '{section_title}' not found in {doc_path}"
                }
            
            # Get a rough approximation of the section
            parts = content.split(section_title)
            if len(parts) > 1:
                section_content = section_title + parts[1].split('\n\n')[0]
                
                return {
                    "success": True,
                    "doc_path": doc_path,
                    "section_title": section_title,
                    "content": section_content,
                    "content_length": len(section_content),
                    "is_markdown": False
                }
            else:
                return {
                    "success": False,
                    "error": f"Could not extract section '{section_title}'"
                }
    except Exception as e:
        return {"success": False, "error": f"Error extracting section: {str(e)}"}

def validate_doc_links(doc_path: str) -> Dict[str, Any]:
    """
    Validate links in a documentation file.
    
    Args:
        doc_path: Path to the documentation file
        
    Returns:
        Dictionary with validation results
    """
    if not os.path.exists(doc_path):
        return {"success": False, "error": f"Documentation file not found: {doc_path}"}
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's a markdown file
        is_markdown = doc_path.lower().endswith('.md')
        
        if not is_markdown:
            return {
                "success": False,
                "error": f"Link validation only supported for Markdown files"
            }
        
        # Extract links from markdown
        # This regex captures both [text](url) and bare <url> formats
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)|<(https?://[^>]+)>'
        links = re.findall(link_pattern, content)
        
        # Process links
        validated_links = []
        
        for link_match in links:
            link_text = link_match[0] if link_match[0] else None
            link_url = link_match[1] if link_match[1] else link_match[2]
            
            # Check if it's a relative or absolute link
            is_relative = not (link_url.startswith('http://') or link_url.startswith('https://'))
            
            # For relative links, check if the file exists
            if is_relative:
                # Remove anchor fragments
                file_part = link_url.split('#')[0]
                # Get absolute path
                if file_part:
                    target_path = os.path.normpath(os.path.join(os.path.dirname(doc_path), file_part))
                    exists = os.path.exists(target_path)
                else:
                    # It's just an anchor
                    exists = True
            else:
                # For external links, we can't validate without making HTTP requests
                # Just mark them as needing online validation
                exists = None
            
            validated_links.append({
                "text": link_text,
                "url": link_url,
                "is_relative": is_relative,
                "exists": exists,
                "needs_online_validation": not is_relative
            })
        
        return {
            "success": True,
            "doc_path": doc_path,
            "link_count": len(validated_links),
            "links": validated_links,
            "broken_links": [link for link in validated_links if link["exists"] is False]
        }
    except Exception as e:
        return {"success": False, "error": f"Error validating links: {str(e)}"}

def extract_doc_structure(doc_path: str) -> Dict[str, Any]:
    """
    Extract the structure of a documentation file, including headers and sections.
    
    Args:
        doc_path: Path to the documentation file
        
    Returns:
        Dictionary with the documentation structure
    """
    if not os.path.exists(doc_path):
        return {"success": False, "error": f"Documentation file not found: {doc_path}"}
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's a markdown file
        is_markdown = doc_path.lower().endswith('.md')
        
        if not is_markdown:
            return {
                "success": False,
                "error": f"Structure extraction only supported for Markdown files"
            }
        
        # Extract markdown headings
        # This regex captures headings of all levels
        heading_pattern = r'^(#{1,6})\s+(.+?)(?:\s+#{1,6})?$'
        headings = []
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = re.match(heading_pattern, line)
            if match:
                level = len(match.group(1))
                heading_text = match.group(2).strip()
                headings.append({
                    "level": level,
                    "text": heading_text,
                    "line": line_num
                })
        
        # Create a hierarchical structure
        toc = []
        stack = [{"level": 0, "children": toc}]
        
        for heading in headings:
            # Find the parent for this heading
            while stack[-1]["level"] >= heading["level"]:
                stack.pop()
            
            # Create new entry
            entry = {
                "text": heading["text"],
                "level": heading["level"],
                "line": heading["line"],
                "children": []
            }
            
            # Add to parent
            stack[-1]["children"].append(entry)
            
            # Push to stack
            stack.append(entry)
        
        return {
            "success": True,
            "doc_path": doc_path,
            "title": extract_title(doc_path),
            "headings": headings,
            "toc": toc,
            "heading_count": len(headings)
        }
    except Exception as e:
        return {"success": False, "error": f"Error extracting structure: {str(e)}"} 