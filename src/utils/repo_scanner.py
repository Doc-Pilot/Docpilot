"""
Repository Scanner Utility
=========================

This utility provides functions for scanning repository file structures
and identifying patterns.
"""

# Importing Dependencies
import os
import re
import fnmatch
from typing import List, Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)

class RepoScanner:
    """Scans a repository and provides information about its structure"""
    
    def __init__(
        self,
        repo_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ):
        """
        Initialize the repository scanner
        
        Args:
            repo_path: Path to the repository
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
        """
        self.repo_path = repo_path
        self.include_patterns = include_patterns or ["*"]
        self.exclude_patterns = exclude_patterns or [
            # Common patterns to exclude
            "**/.git/**", "**/node_modules/**", "**/venv/**", "**/__pycache__/**",
            "**/.pytest_cache/**", "**/.vscode/**", "**/.idea/**"
        ]
        
    def scan_files(self) -> List[str]:
        """
        Scan the repository and return a list of file paths
        
        Returns:
            List of file paths relative to repo_path
        """
        file_list = []
        
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.repo_path)
                
                # Check if the file should be included
                if self._should_include_file(rel_path):
                    file_list.append(rel_path)
        
        return file_list
    
    def _should_include_file(self, file_path: str) -> bool:
        """
        Check if a file should be included based on include/exclude patterns
        
        Args:
            file_path: File path to check
            
        Returns:
            True if the file should be included, False otherwise
        """
        # Convert Windows path separators to Unix style for pattern matching
        file_path = file_path.replace('\\', '/')
        
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return False
        
        # Then check include patterns
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        
        # If no include pattern matches, exclude the file
        return False
    
    def get_file_extension_breakdown(self, file_list: List[str]) -> Dict[str, int]:
        """
        Get a breakdown of file extensions in the repository
        
        Args:
            file_list: List of file paths
            
        Returns:
            Dictionary mapping extensions to counts
        """
        extension_counts = {}
        
        for file_path in file_list:
            _, ext = os.path.splitext(file_path)
            if ext:
                # Remove the dot and convert to lowercase
                ext = ext[1:].lower()
                extension_counts[ext] = extension_counts.get(ext, 0) + 1
            else:
                # No extension
                extension_counts["(no extension)"] = extension_counts.get("(no extension)", 0) + 1
        
        return extension_counts
    
    def identify_language(self, file_path: str) -> Optional[str]:
        """
        Identify the programming language of a file based on its extension
        
        Args:
            file_path: Path to the file
            
        Returns:
            Identified language or None if unknown
        """
        _, ext = os.path.splitext(file_path)
        if not ext:
            return None
            
        # Remove the dot and convert to lowercase
        ext = ext[1:].lower()
        
        # Map extensions to languages
        extension_to_language = {
            "py": "Python",
            "js": "JavaScript",
            "jsx": "JavaScript (React)",
            "ts": "TypeScript",
            "tsx": "TypeScript (React)",
            "html": "HTML",
            "css": "CSS",
            "scss": "SCSS",
            "sass": "Sass",
            "less": "Less",
            "java": "Java",
            "c": "C",
            "cpp": "C++",
            "cc": "C++",
            "cxx": "C++",
            "h": "C/C++ Header",
            "hpp": "C++ Header",
            "cs": "C#",
            "go": "Go",
            "rb": "Ruby",
            "php": "PHP",
            "swift": "Swift",
            "kt": "Kotlin",
            "kts": "Kotlin Script",
            "rs": "Rust",
            "sh": "Shell",
            "bat": "Batch",
            "ps1": "PowerShell",
            "sql": "SQL",
            "md": "Markdown",
            "json": "JSON",
            "yaml": "YAML",
            "yml": "YAML",
            "toml": "TOML",
            "xml": "XML",
            "csv": "CSV",
            "txt": "Text",
            "gitignore": "GitIgnore",
            "dockerfile": "Dockerfile",
            "lock": "Lockfile",
        }
        
        return extension_to_language.get(ext)
    
    def detect_framework_patterns(self, file_list: List[str]) -> List[str]:
        """
        Detect framework patterns in the repository
        
        Args:
            file_list: List of file paths
            
        Returns:
            List of detected frameworks
        """
        frameworks = set()
        
        # Look for framework-specific files
        framework_patterns = {
            "react": ["package.json"],
            "vue": ["package.json"],
            "angular": ["angular.json", "package.json"],
            "django": ["manage.py", "settings.py"],
            "flask": ["app.py", "wsgi.py"],
            "fastapi": ["main.py", "app.py"],
            "express": ["package.json"],
            "spring": ["pom.xml", "build.gradle"],
            "rails": ["Gemfile", "config/routes.rb"],
            "laravel": ["composer.json", "artisan"],
            "next.js": ["next.config.js", "package.json"],
            "gatsby": ["gatsby-config.js", "package.json"],
            "nuxt.js": ["nuxt.config.js", "package.json"]
        }
        
        # Check for presence of framework-specific files
        for file_path in file_list:
            # Extract just the filename without directory
            filename = os.path.basename(file_path)
            
            for framework, patterns in framework_patterns.items():
                for pattern in patterns:
                    if filename == pattern:
                        # For package.json and similar, we need to check the content
                        if filename == "package.json":
                            # Read the file and check for dependencies
                            try:
                                import json
                                full_path = os.path.join(self.repo_path, file_path)
                                with open(full_path, 'r') as f:
                                    package_data = json.load(f)
                                    
                                # Check dependencies and devDependencies
                                dependencies = package_data.get('dependencies', {})
                                dev_dependencies = package_data.get('devDependencies', {})
                                all_deps = {**dependencies, **dev_dependencies}
                                
                                # Check for specific frameworks
                                if 'react' in all_deps:
                                    frameworks.add('React')
                                if 'vue' in all_deps:
                                    frameworks.add('Vue.js')
                                if '@angular/core' in all_deps:
                                    frameworks.add('Angular')
                                if 'express' in all_deps:
                                    frameworks.add('Express.js')
                                if 'next' in all_deps:
                                    frameworks.add('Next.js')
                                if 'gatsby' in all_deps:
                                    frameworks.add('Gatsby')
                                if 'nuxt' in all_deps:
                                    frameworks.add('Nuxt.js')
                            except:
                                pass
                        else:
                            # For other files, just the presence is enough
                            frameworks.add(framework.capitalize())
        
        # If Django patterns are found in Python files
        django_patterns = [
            r'from django',
            r'import django',
        ]
        
        flask_patterns = [
            r'from flask import',
            r'import flask',
        ]
        
        fastapi_patterns = [
            r'from fastapi import',
            r'import fastapi',
        ]
        
        # Check Python files for these patterns
        for file_path in file_list:
            if file_path.endswith('.py'):
                try:
                    full_path = os.path.join(self.repo_path, file_path)
                    with open(full_path, 'r') as f:
                        content = f.read()
                        
                    for pattern in django_patterns:
                        if re.search(pattern, content):
                            frameworks.add('Django')
                            break
                            
                    for pattern in flask_patterns:
                        if re.search(pattern, content):
                            frameworks.add('Flask')
                            break
                            
                    for pattern in fastapi_patterns:
                        if re.search(pattern, content):
                            frameworks.add('FastAPI')
                            break
                except:
                    pass
        
        return sorted(list(frameworks))
    
    def identify_documentation_files(self, file_list: List[str]) -> List[str]:
        """
        Identify documentation files in the repository
        
        Args:
            file_list: List of file paths
            
        Returns:
            List of documentation file paths
        """
        doc_files = []
        
        # Common documentation file patterns
        doc_patterns = [
            "*.md",
            "*.rst",
            "*.txt",
            "*/docs/*",
            "*/doc/*",
            "*/documentation/*",
            "*/wiki/*",
            "*.pdf",
            "README*",
            "CHANGELOG*",
            "CONTRIBUTING*",
            "LICENSE*",
            "NOTICE*",
            "AUTHORS*"
        ]
        
        for file_path in file_list:
            # Convert Windows path separators to Unix style for pattern matching
            unix_path = file_path.replace('\\', '/')
            
            for pattern in doc_patterns:
                if fnmatch.fnmatch(unix_path, pattern):
                    doc_files.append(file_path)
                    break
        
        return doc_files
    
    def identify_entry_points(self, file_list: List[str]) -> List[str]:
        """
        Identify potential entry points in the repository
        
        Args:
            file_list: List of file paths
            
        Returns:
            List of entry point file paths
        """
        entry_points = []
        
        # Common entry point file patterns
        entry_patterns = {
            "Python": ["main.py", "app.py", "manage.py", "setup.py", "__main__.py"],
            "JavaScript": ["index.js", "main.js", "app.js", "server.js"],
            "TypeScript": ["index.ts", "main.ts", "app.ts", "server.ts"],
            "Java": ["Main.java", "App.java", "Application.java"],
            "Go": ["main.go"],
            "Ruby": ["main.rb", "app.rb", "application.rb"],
            "PHP": ["index.php"],
            "Rust": ["main.rs"],
            "C#": ["Program.cs"],
            "C/C++": ["main.c", "main.cpp"]
        }
        
        for file_path in file_list:
            # Extract filename
            filename = os.path.basename(file_path)
            
            # Check against entry patterns
            for language, patterns in entry_patterns.items():
                if filename in patterns:
                    entry_points.append(file_path)
        
        return entry_points 