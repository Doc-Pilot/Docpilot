"""
Documentation Scanner
===================

Utilities for scanning repositories for documentation files and matching
them with code changes to identify documentation that needs updating.
"""

import os
import re
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Documentation file patterns
DOC_PATTERNS = [
    "*.md",                 # Markdown files
    "README*",              # READMEs
    "SUMMARY.md",           # Summary documentation
    "docs/**/*",            # Documentation directories
    "examples/**/*.md",     # Examples documentation
    "*/api/**/*.md",        # API documentation
    "*.rst",                # ReStructuredText files
    "wiki/**/*"             # Wiki content
]

# Documentation file categories
DOC_CATEGORIES = {
    "readme": ["README.md", "README.rst"],
    "api": ["api.md", "reference.md", "*/api/**/*.md"],
    "howto": ["howto.md", "tutorial.md", "docs/guides/*.md", "docs/tutorials/*.md"],
    "examples": ["examples/**/*.md", "examples/**/*.py"],
    "changelog": ["CHANGELOG.md", "CHANGES.md", "HISTORY.md"],
    "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.rst"]
}

def scan_documentation(repo_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Scan a repository for documentation files.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        Dictionary mapping documentation file paths to their metadata
    """
    doc_files = {}
    repo_root = Path(repo_path)
    
    # Scan for documentation files
    for pattern in DOC_PATTERNS:
        # Handle directory paths vs glob patterns
        if '**' in pattern:
            parts = pattern.split('/')
            base_dir = repo_root
            for part in parts[:-1]:
                if '**' in part:
                    break
                base_dir = base_dir / part
                
            if not base_dir.exists():
                continue
                
            # Use Path.glob for recursive pattern matching
            glob_pattern = '/'.join(parts[parts.index(base_dir.name) + 1:])
            for file_path in base_dir.glob(glob_pattern):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(repo_root))
                    doc_files[rel_path] = {
                        'path': rel_path,
                        'type': get_doc_type(rel_path),
                        'title': extract_title(str(file_path)),
                        'last_modified': get_last_modified(repo_path, rel_path)
                    }
        else:
            # Simple glob pattern
            for file_path in repo_root.glob(pattern):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(repo_root))
                    doc_files[rel_path] = {
                        'path': rel_path,
                        'type': get_doc_type(rel_path),
                        'title': extract_title(str(file_path)),
                        'last_modified': get_last_modified(repo_path, rel_path)
                    }
    
    logger.info(f"Found {len(doc_files)} documentation files in {repo_path}")
    return doc_files

def get_doc_type(file_path: str) -> str:
    """
    Determine the type of documentation file.
    
    Args:
        file_path: Path to the documentation file
        
    Returns:
        Type of documentation file (readme, api, howto, examples, etc.)
    """
    file_path = file_path.lower()
    base_name = os.path.basename(file_path)
    
    for category, patterns in DOC_CATEGORIES.items():
        for pattern in patterns:
            if _matches_pattern(file_path, pattern):
                return category
                
    # Check for common documentation types based on path components
    if 'docs' in file_path:
        return 'documentation'
    elif 'examples' in file_path:
        return 'example'
    elif 'tutorial' in file_path:
        return 'tutorial'
    elif 'api' in file_path:
        return 'api'
    
    # Default to general documentation
    return 'documentation'

def _matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a glob-like pattern"""
    if pattern.startswith('**/'):
        return file_path.endswith(pattern[3:])
    elif pattern.endswith('/**/*'):
        dir_part = pattern[:-5]
        return dir_part in file_path
    elif '*' in pattern:
        # Convert glob pattern to regex pattern
        regex_pattern = '^' + pattern.replace('.', '\\.').replace('*', '.*') + '$'
        return bool(re.match(regex_pattern, os.path.basename(file_path)))
    else:
        return pattern in file_path or os.path.basename(file_path) == pattern

def extract_title(file_path: str) -> str:
    """
    Extract the title from a documentation file.
    
    Args:
        file_path: Path to the documentation file
        
    Returns:
        Title of the documentation file
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if first_line.startswith('# '):
                # Markdown title
                return first_line[2:]
            elif first_line.startswith('=='):
                # RST title (title on second line)
                f.seek(0)
                lines = f.readlines()
                if len(lines) > 1:
                    return lines[0].strip()
            else:
                # Try to find a markdown title in the first few lines
                f.seek(0)
                for i, line in enumerate(f):
                    if i > 5:  # Only check first 5 lines
                        break
                    if line.startswith('# '):
                        return line[2:].strip()
    except Exception as e:
        logger.warning(f"Error extracting title from {file_path}: {str(e)}")
    
    # If no title found, use the filename
    return os.path.splitext(os.path.basename(file_path))[0]

def get_last_modified(repo_path: str, file_path: str) -> str:
    """
    Get the date when a file was last modified in git.
    
    Args:
        repo_path: Path to the git repository
        file_path: Path to the file, relative to repo_path
        
    Returns:
        Date of last modification as a string
    """
    try:
        cmd = ['git', '-C', repo_path, 'log', '-1', '--format=%cd', '--date=iso', '--', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Error getting last modified date for {file_path}: {str(e)}")
        return ""

def get_changed_files(repo_path: str, base_ref: str, target_ref: str) -> List[str]:
    """
    Get a list of files changed between two git references.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base git reference (e.g., 'HEAD~1')
        target_ref: Target git reference (e.g., 'HEAD')
        
    Returns:
        List of changed file paths
    """
    try:
        cmd = ['git', '-C', repo_path, 'diff', '--name-only', base_ref, target_ref]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        changed_files = result.stdout.strip().split('\n')
        return [f for f in changed_files if f]  # Filter out empty strings
    except Exception as e:
        logger.error(f"Error getting changed files: {str(e)}")
        return []

def find_related_docs(changed_files: List[str], doc_files: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Find documentation files related to changed code files.
    
    Args:
        repo_path: Path to the git repository
        changed_files: List of changed file paths
        doc_files: Dictionary of documentation files and their metadata
        
    Returns:
        Dictionary mapping documentation files to lists of related changed files
    """
    related_docs = {}
    
    # Group changed files by directory
    dir_to_files = {}
    for file_path in changed_files:
        directory = os.path.dirname(file_path)
        if directory not in dir_to_files:
            dir_to_files[directory] = []
        dir_to_files[directory].append(file_path)
    
    # Find related documentation files
    for doc_path, doc_meta in doc_files.items():
        doc_dir = os.path.dirname(doc_path)
        doc_name = os.path.basename(doc_path)
        
        # First check: Is the doc file itself changed?
        if doc_path in changed_files:
            related_docs[doc_path] = [doc_path]
            continue
            
        # Second check: Find docs in the same directory as changed files
        related_files = []
        for directory, files in dir_to_files.items():
            # If a README is in the same directory as changed files
            if doc_dir == directory and doc_name.lower().startswith('readme'):
                related_files.extend(files)
            
            # If changed files are in a subdirectory of the doc file
            if directory.startswith(doc_dir + os.sep) and doc_name.lower().startswith('readme'):
                related_files.extend(files)
                
            # If doc is in docs/ directory, check for module-specific documentation
            if 'docs' in doc_dir:
                # Extract module name from docs path or filename
                module_parts = doc_path.split(os.sep)
                module_name = None
                for part in module_parts:
                    if part != 'docs' and '.' not in part:
                        module_name = part
                        break
                
                if not module_name:
                    module_name = os.path.splitext(doc_name)[0]
                
                # Check if changed files are in module with the same name
                for file_path in files:
                    file_parts = file_path.split(os.sep)
                    if module_name in file_parts or any(module_name in part for part in file_parts):
                        related_files.append(file_path)
        
        if related_files:
            related_docs[doc_path] = related_files
    
    return related_docs

def should_update_documentation(repo_path: str, doc_path: str, related_files: List[str]) -> bool:
    """
    Determine if a documentation file should be updated based on related changed files.
    
    Args:
        repo_path: Path to the git repository
        doc_path: Path to the documentation file
        related_files: List of related changed files
        
    Returns:
        True if the documentation should be updated, False otherwise
    """
    # Always update if the doc itself has changed
    if doc_path in related_files:
        return True
    
    # Check for significant code changes that would warrant a doc update
    significant_changes = check_for_significant_changes(repo_path, related_files)
    if significant_changes:
        return True
    
    return False

def check_for_significant_changes(repo_path: str, changed_files: List[str]) -> bool:
    """
    Check if there are significant changes in the code files that would warrant a documentation update.
    
    Args:
        repo_path: Path to the git repository
        changed_files: List of changed file paths
        
    Returns:
        True if there are significant changes, False otherwise
    """
    # Look for Python files only
    python_files = [f for f in changed_files if f.endswith('.py')]
    if not python_files:
        return False
    
    try:
        significant_patterns = [
            r'def\s+\w+\s*\(',  # Function definitions
            r'class\s+\w+\s*\(',  # Class definitions
            r'@(app|router)\.(\w+)\(',  # API endpoints (for web frameworks)
            r'@(api|cli|click)\.command',  # CLI commands
            r'__version__\s*=',  # Version changes
        ]
        
        for file_path in python_files:
            abs_path = os.path.join(repo_path, file_path)
            if not os.path.exists(abs_path):
                continue
                
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in significant_patterns:
                if re.search(pattern, content):
                    return True
    except Exception as e:
        logger.warning(f"Error checking for significant changes: {str(e)}")
    
    return False

def generate_update_plan(repo_path: str, base_ref: str, target_ref: str) -> Dict[str, Any]:
    """
    Generate a plan for updating documentation based on code changes.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base git reference (e.g., 'HEAD~1')
        target_ref: Target git reference (e.g., 'HEAD')
        
    Returns:
        Dictionary with the documentation update plan
    """
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
    related_docs = find_related_docs(repo_path, changed_files, doc_files)
    
    # Determine which docs need updates
    docs_to_update = []
    for doc_path, related_files in related_docs.items():
        if should_update_documentation(repo_path, doc_path, related_files):
            doc_meta = doc_files.get(doc_path, {})
            docs_to_update.append({
                "path": doc_path,
                "type": doc_meta.get("type", "documentation"),
                "title": doc_meta.get("title", os.path.basename(doc_path)),
                "related_files": related_files
            })
    
    return {
        "success": True,
        "message": f"Found {len(docs_to_update)} documentation files that need updating",
        "docs_to_update": docs_to_update,
        "changed_files": changed_files,
        "all_docs": list(doc_files.keys())
    } 