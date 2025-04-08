"""
Documentation Scanner
===================

Utilities for scanning repositories for documentation files and matching
them with code changes to identify documentation that needs updating.
"""

import os
import re
import logging
import fnmatch
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from functools import lru_cache

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

# Cache for expensive operations
_changed_files_cache = {}  # (repo_path, base_ref, target_ref) -> changed_files

def run_git_command(repo_path: str, cmd: List[str], timeout: int = 10, fallback: Any = None, 
                   error_msg: str = "Git command failed") -> Union[str, List[str], Any]:
    """
    Centralized git operation handler with consistent error handling.
    
    Args:
        repo_path: Path to the git repository
        cmd: Git command to run as a list of arguments
        timeout: Timeout in seconds (default: 10)
        fallback: Value to return on error (default: None)
        error_msg: Error message prefix (default: "Git command failed")
        
    Returns:
        Command output or fallback value on error
    """
    try:
        # Check if git is installed
        if not shutil.which("git"):
            logger.error("Git executable not found in PATH")
            return fallback
            
        # Check if repo path is a valid git repo if command needs a repo
        if repo_path and cmd[0] != 'git' and not os.path.exists(os.path.join(repo_path, ".git")):
            logger.error(f"Not a git repository: {repo_path}")
            return fallback
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            # Don't log common errors like 'file not tracked'
            if "not in the git repository" not in result.stderr and "no matches found" not in result.stderr:
                logger.warning(f"{error_msg}: {result.stderr}")
            return fallback
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Git command timed out after {timeout}s: {' '.join(cmd)}")
        return fallback
    except Exception as e:
        logger.error(f"Git error: {str(e)}")
        return fallback

def is_ignored_by_git(repo_path: str, file_path: str) -> bool:
    """
    Check if a file is ignored by git according to .gitignore rules.
    
    Args:
        repo_path: Path to the git repository
        file_path: Path to the file to check (can be absolute or relative)
        
    Returns:
        True if the file is ignored by git, False otherwise
    """
    try:
        # Get relative path if file_path is absolute
        rel_path = os.path.relpath(file_path, repo_path)
        
        # Run git check-ignore to see if the file is ignored
        cmd = ['git', '-C', repo_path, 'check-ignore', '-q', rel_path]
        result = run_git_command(repo_path, cmd, fallback=1)
        
        # If we got an integer result, it's the return code (0 for ignored, 1 for not ignored)
        if isinstance(result, int):
            return result == 0
            
        # If the command was successful, the file is ignored
        return True
    except Exception as e:
        logger.warning(f"Error checking if file is ignored: {str(e)}")
        # Fall back to not ignoring in case of error
        return False

def scan_documentation(repo_path: str, skip_ignored: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Scan a repository for documentation files.
    
    Args:
        repo_path: Path to the git repository
        skip_ignored: Whether to skip files ignored by git (default: True)
        
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
                    # Skip git-ignored files if requested
                    if skip_ignored and is_ignored_by_git(repo_path, str(file_path)):
                        continue
                        
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
                    # Skip git-ignored files if requested
                    if skip_ignored and is_ignored_by_git(repo_path, str(file_path)):
                        continue
                        
                    rel_path = str(file_path.relative_to(repo_root))
                    doc_files[rel_path] = {
                        'path': rel_path,
                        'type': get_doc_type(rel_path),
                        'title': extract_title(str(file_path)),
                        'last_modified': get_last_modified(repo_path, rel_path)
                    }
    
    return doc_files

def get_doc_type(file_path: str) -> str:
    """
    Determine the type of documentation file based on its path.
    
    Args:
        file_path: Path to the documentation file
        
    Returns:
        The documentation type (e.g., 'readme', 'api', 'tutorial')
    """
    file_path = file_path.lower()
    file_name = os.path.basename(file_path)
    
    # Check against known documentation categories
    for doc_type, patterns in DOC_CATEGORIES.items():
        for pattern in patterns:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_name, pattern):
                return doc_type
    
    # Special cases based on directory or filename
    if '/docs/api/' in file_path or '\\docs\\api\\' in file_path:
        return 'api'
    elif '/docs/tutorials/' in file_path or '/docs/guides/' in file_path or '\\docs\\tutorials\\' in file_path or '\\docs\\guides\\' in file_path:
        return 'tutorial'
    elif '/examples/' in file_path or '\\examples\\' in file_path:
        return 'example'
    elif file_name.startswith('readme'):
        return 'readme'
    elif 'changelog' in file_name:
        return 'changelog'
    
    # Default to generic documentation type
    return 'documentation'

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
    # Check cache first
    cache_key = (repo_path, base_ref, target_ref)
    if cache_key in _changed_files_cache:
        return _changed_files_cache[cache_key]
    
    cmd = ['git', '-C', repo_path, 'diff', '--name-only', base_ref, target_ref]
    output = run_git_command(repo_path, cmd, fallback="", error_msg="Failed to get changed files")
    
    if not output:
        return []
        
    changed_files = [f for f in output.split('\n') if f]  # Filter out empty strings
    
    # Cache the result
    _changed_files_cache[cache_key] = changed_files
    return changed_files

def find_related_docs(changed_files: List[str], doc_files: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Find documentation files related to changed code files.
    
    Args:
        changed_files: List of changed file paths
        doc_files: Dictionary of documentation files and their metadata
        
    Returns:
        Dictionary mapping documentation files to lists of related changed files
    """
    related_docs = {}
    
    # Create indexes for faster lookups
    doc_dir_index = {}  # Map directories to doc files
    module_name_index = {}  # Map module names to doc files
    
    # Build indexes
    for doc_path in doc_files:
        # Directory index
        doc_dir = os.path.dirname(doc_path)
        if doc_dir not in doc_dir_index:
            doc_dir_index[doc_dir] = []
        doc_dir_index[doc_dir].append(doc_path)
        
        # Module name index (especially useful for docs/ directory)
        if 'docs' in doc_path:
            module_parts = doc_path.split(os.sep)
            for part in module_parts:
                if part != 'docs' and '.' not in part:
                    if part not in module_name_index:
                        module_name_index[part] = []
                    module_name_index[part].append(doc_path)
                    break
    
    # Group changed files by directory for more efficient lookups
    dir_to_files = {}
    for file_path in changed_files:
        directory = os.path.dirname(file_path)
        if directory not in dir_to_files:
            dir_to_files[directory] = []
        dir_to_files[directory].append(file_path)
    
    # Check if any doc files themselves changed
    for doc_path in doc_files:
        if doc_path in changed_files:
            related_docs[doc_path] = [doc_path]
    
    # Find related documentation files using the indexes
    for doc_path, doc_meta in doc_files.items():
        # Skip if this doc was already added as changed
        if doc_path in related_docs:
            continue
            
        related_files = []
        doc_dir = os.path.dirname(doc_path)
        doc_name = os.path.basename(doc_path)
        
        # Check 1: Look for README files with changes in the same directory
        if doc_name.lower().startswith('readme'):
            # Check directly in this directory
            if doc_dir in dir_to_files:
                related_files.extend(dir_to_files[doc_dir])
            
            # Check subdirectories
            for directory, files in dir_to_files.items():
                if directory.startswith(doc_dir + os.sep):
                    related_files.extend(files)
        
        # Check 2: For docs in 'docs/' directory, check module-specific matches
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
            
            # Check changed files for module name matches
            for file_path in changed_files:
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
    if significant_changes["has_significant_changes"]:
        return True
    
    return False

def check_for_significant_changes(repo_path: str, changed_files: List[str]) -> Dict[str, Any]:
    """
    Check if there are significant changes in the code files that would warrant a documentation update.
    
    Args:
        repo_path: Path to the git repository
        changed_files: List of changed file paths
        
    Returns:
        Dictionary with significant changes found and detailed info
    """
    supported_extensions = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.rb': 'ruby'
    }
    
    # Group files by language
    files_by_language = {}
    for file in changed_files:
        ext = os.path.splitext(file)[1]
        if ext in supported_extensions:
            lang = supported_extensions[ext]
            if lang not in files_by_language:
                files_by_language[lang] = []
            files_by_language[lang].append(file)
    
    if not files_by_language:
        return {"has_significant_changes": False}
    
    # Define patterns for each language
    patterns_by_language = {
        'python': [
            r'def\s+(\w+)\s*\(',  # Function definitions
            r'class\s+(\w+)\s*\(',  # Class definitions
            r'@(app|router)\.(\w+)\(',  # API endpoints
            r'@(api|cli|click)\.command',  # CLI commands
            r'__version__\s*=',  # Version changes
        ],
        'javascript': [
            r'function\s+(\w+)\s*\(',  # Function declarations
            r'class\s+(\w+)\s*{',  # Classes
            r'const\s+(\w+)\s*=\s*\(',  # Arrow functions
            r'export\s+(default\s+)?(function|class)',  # Exports
            r'module\.exports\s*=',  # CommonJS exports
        ],
        'typescript': [
            r'function\s+(\w+)\s*\(',  # Function declarations
            r'class\s+(\w+)\s*{',  # Classes
            r'const\s+(\w+)\s*=\s*\(',  # Arrow functions
            r'interface\s+(\w+)',  # Interfaces
            r'type\s+(\w+)\s*=',  # Type aliases
            r'export\s+(default\s+)?(function|class|interface)',  # Exports
        ],
        'java': [
            r'(public|private|protected)\s+\w+\s+(\w+)\s*\(',  # Methods
            r'class\s+(\w+)',  # Classes
            r'interface\s+(\w+)',  # Interfaces
            r'@RestController',  # Spring REST controllers
            r'@RequestMapping',  # Spring request mappings
        ],
    }
    
    changes_found = {
        "has_significant_changes": False,
        "details": []
    }
    
    try:
        for lang, files in files_by_language.items():
            if lang not in patterns_by_language:
                continue
                
            patterns = patterns_by_language[lang]
            
            for file_path in files:
                abs_path = os.path.join(repo_path, file_path)
                if not os.path.exists(abs_path):
                    continue
                
                # Use git diff to see changed lines (more efficient)
                cmd = ['git', '-C', repo_path, 'diff', 'HEAD~1', '--', file_path]
                diff_output = run_git_command(repo_path, cmd, fallback="", error_msg=f"Failed to get diff for {file_path}")
                
                if not diff_output:
                    # Fallback to scanning the whole file
                    try:
                        with open(abs_path, 'r', encoding='utf-8') as f:
                            for i, line in enumerate(f, 1):
                                for pattern in patterns:
                                    match = re.search(pattern, line)
                                    if match:
                                        changes_found["has_significant_changes"] = True
                                        changes_found["details"].append({
                                            "file": file_path,
                                            "line": i,
                                            "type": "function_or_class",
                                            "name": match.group(1) if match.lastindex >= 1 else "unknown"
                                        })
                    except Exception as e:
                        logger.error(f"Error reading file {abs_path}: {str(e)}")
                    continue
                
                # Process diff output
                for line in diff_output.splitlines():
                    if line.startswith('+') and not line.startswith('+++'):
                        code_line = line[1:]
                        for pattern in patterns:
                            match = re.search(pattern, code_line)
                            if match:
                                changes_found["has_significant_changes"] = True
                                changes_found["details"].append({
                                    "file": file_path,
                                    "type": "function_or_class",
                                    "name": match.group(1) if match.lastindex >= 1 else "unknown",
                                    "change": "added_or_modified"
                                })
        
        return changes_found
    except Exception as e:
        logger.error(f"Error checking for significant changes: {str(e)}")
        return {"has_significant_changes": False, "error": str(e)}

# Apply memoization to expensive file reading operations
@lru_cache(maxsize=128)
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
        return "No title found"
    
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
    cmd = ['git', '-C', repo_path, 'log', '-1', '--format=%cd', '--date=iso', '--', file_path]
    result = run_git_command(repo_path, cmd, fallback="Unknown", error_msg=f"Failed to get last modified date for {file_path}")
    return result