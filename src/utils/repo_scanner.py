"""
Repository Scanner Module
========================

This module contains utilities for scanning repositories and analyzing their structure.
It provides a hierarchical representation of the repository optimized for LLM understanding.
"""

import os
import re
import fnmatch
from typing import List, Dict, Any, Optional, Set
import logging
import pathspec

logger = logging.getLogger(__name__)

class RepoScanner:
    """
    Scans repositories and provides analysis of their structure.
    """
    
    def __init__(
        self,
        repo_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
        use_gitignore: bool = True
    ):
        """
        Initialize the repository scanner.
        
        Args:
            repo_path: Path to the repository
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
            use_gitignore: Whether to use .gitignore patterns
        """
        self.repo_path = repo_path
        self.include_patterns = include_patterns or ["*"]
        
        # Default exclude patterns
        default_exclude_patterns = [
            # Common patterns to exclude
            "**/.git/**", "**/node_modules/**", "**/venv/**", "**/__pycache__/**",
            "**/.pytest_cache/**", "**/.vscode/**", "**/.idea/**", "**/build/**",
            "**/dist/**", "**/out/**", "**/target/**", "**/.DS_Store",
            "**/.env", "**/.env.*", "**/.gitignore", "**/.gitattributes",
            "**/coverage/**", "**/logs/**", "**/*.log", "**/*.pyc", "**/*.pyo",
            "**/yarn.lock", "**/package-lock.json", "**/Pipfile.lock", "**/poetry.lock",
            "**/tmp/**", "**/.cache/**", "**/.docker/**", "**/bin/**", "**/obj/**",
            "**/*.egg-info/**", "**/*~", "**/*.swp", "**/*.swo", "**/Thumbs.db"
        ]
        
        # Use provided exclude patterns or default ones
        self.exclude_patterns = exclude_patterns or default_exclude_patterns
        
        # Setup pathspec for gitignore
        self.gitignore_spec = None
        if use_gitignore:
            self._load_gitignore()
        
    def _load_gitignore(self):
        """Load .gitignore file and create a spec for matching"""
        gitignore_path = os.path.join(self.repo_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                gitignore_content = f.read()
                
            try:
                # Create gitignore spec
                self.gitignore_spec = pathspec.PathSpec.from_lines(
                    pathspec.patterns.GitWildMatchPattern, 
                    gitignore_content.splitlines()
                )
                logger.info(f"Loaded .gitignore file with {len(self.gitignore_spec.patterns)} patterns")
            except Exception as e:
                logger.warning(f"Error loading .gitignore file: {str(e)}")
                self.gitignore_spec = None
        
    def scan_files(self) -> List[str]:
        """
        Get all files in the repository, respecting exclude patterns.
        
        Returns:
            List of file paths relative to the repository root
        """
        all_files = []
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip directories matching gitignore patterns
            if self.gitignore_spec:
                # Get relative paths for directories
                rel_dirs = [os.path.relpath(os.path.join(root, d), self.repo_path) for d in dirs]
                # Filter out directories that match gitignore patterns
                for i, (d, rel_path) in enumerate(zip(dirs[:], rel_dirs)):
                    if self.gitignore_spec.match_file(rel_path) or self.gitignore_spec.match_file(f"{rel_path}/"):
                        dirs.remove(d)
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                rel_path = rel_path.replace('\\', '/')  # Normalize path separators
                
                # Check if file should be excluded
                exclude = False
                for pattern in self.exclude_patterns:
                    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(file, pattern):
                        exclude = True
                        break
                
                if not exclude:
                    all_files.append(rel_path)
        
        return all_files
    
    def detect_frameworks(self) -> Dict[str, Set[str]]:
        """
        Detect frameworks and technologies used in the repository.
        
        Returns:
            Dictionary of technology categories and detected technologies
        """
        # Get all files
        files = self.get_all_files()
        
        # Define patterns for technology detection
        technology_patterns = {
            "frontend": {
                "react": ["react", "jsx", "react-dom", "react-router"],
                "vue": ["vue", "vuex", "vue-router"],
                "angular": ["angular", "@angular", "ng-"],
                "svelte": ["svelte"],
                "nextjs": ["next", "next.js"],
                "nuxt": ["nuxt"],
                "bootstrap": ["bootstrap"],
                "tailwind": ["tailwind"],
                "material-ui": ["material-ui", "@mui"],
                "jquery": ["jquery"],
            },
            "backend": {
                "express": ["express"],
                "django": ["django", "wsgi"],
                "flask": ["flask"],
                "fastapi": ["fastapi"],
                "spring": ["spring", "springframework"],
                "laravel": ["laravel"],
                "rails": ["rails"],
                "aspnet": ["asp.net", "aspnetcore"],
                "nestjs": ["nest", "@nestjs"],
                "graphql": ["graphql", "apollo"],
            },
            "database": {
                "mongodb": ["mongo", "mongodb"],
                "postgresql": ["postgres", "postgresql"],
                "mysql": ["mysql"],
                "sqlite": ["sqlite"],
                "redis": ["redis"],
                "firebase": ["firebase", "firestore"],
                "dynamodb": ["dynamodb"],
                "cassandra": ["cassandra"],
                "elasticsearch": ["elasticsearch"],
                "prisma": ["prisma"],
                "sequelize": ["sequelize"],
                "typeorm": ["typeorm"],
            },
            "testing": {
                "jest": ["jest"],
                "mocha": ["mocha"],
                "pytest": ["pytest"],
                "unittest": ["unittest"],
                "jasmine": ["jasmine"],
                "chai": ["chai"],
                "cypress": ["cypress"],
                "selenium": ["selenium"],
                "junit": ["junit"],
            },
            "devops": {
                "docker": ["docker", "dockerfile"],
                "kubernetes": ["kubernetes", "k8s"],
                "jenkins": ["jenkins", "jenkinsfile"],
                "terraform": ["terraform"],
                "ansible": ["ansible"],
                "github-actions": ["github-actions", "github/workflows"],
                "gitlab-ci": ["gitlab-ci"],
                "ci-cd": ["ci", "cd", "ci/cd"],
                "aws": ["aws", "amazon web services"],
                "azure": ["azure"],
                "gcp": ["gcp", "google cloud"],
            },
            "state-management": {
                "redux": ["redux"],
                "mobx": ["mobx"],
                "vuex": ["vuex"],
                "ngrx": ["ngrx"],
                "zustand": ["zustand"],
                "jotai": ["jotai"],
                "recoil": ["recoil"],
            },
            "languages": {
                "typescript": ["typescript", ".ts"],
                "javascript": [".js", "javascript"],
                "python": [".py", "python"],
                "java": [".java", "java"],
                "go": [".go", "golang"],
                "rust": [".rs", "rust"],
                "c-sharp": [".cs", "c#"],
                "ruby": [".rb", "ruby"],
                "php": [".php", "php"],
                "kotlin": [".kt", "kotlin"],
                "swift": [".swift", "swift"],
            },
        }
        
        # Get file contents for key files to improve detection accuracy
        config_files = []
        for file in files:
            filename = os.path.basename(file)
            if filename in [
                "package.json",
                "requirements.txt",
                "Pipfile",
                "pom.xml",
                "build.gradle",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
                "go.mod",
                "docker-compose.yml",
                "Dockerfile",
                ".travis.yml",
                ".gitlab-ci.yml",
                "webpack.config.js",
                "tsconfig.json"
            ]:
                config_files.append(file)
        
        # Read content of key config files
        config_contents = {}
        for file in config_files:
            try:
                file_path = os.path.join(self.repo_path, file)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    config_contents[file] = f.read()
            except Exception:
                # Ignore errors when reading files
                pass
        
        # Detect technologies
        technologies = defaultdict(set)
        
        # Detect from config contents
        for file_name, content in config_contents.items():
            for category, techs in technology_patterns.items():
                for tech, patterns in techs.items():
                    for pattern in patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            technologies[category].add(tech)
        
        # Detect from file names and extensions
        for file in files:
            file_lower = file.lower()
            for category, techs in technology_patterns.items():
                for tech, patterns in techs.items():
                    for pattern in patterns:
                        if pattern.startswith('.'):
                            if file_lower.endswith(pattern):
                                technologies[category].add(tech)
                        elif re.search(pattern, file_lower, re.IGNORECASE):
                            technologies[category].add(tech)
        
        # Make additional inferences based on detected technologies
        if technologies["frontend"] & {"react", "vue", "angular", "svelte"} and \
           technologies["backend"] & {"express", "django", "flask", "fastapi", "spring", "nestjs"}:
            technologies["architecture"].add("full-stack")
        
        if technologies["database"] and technologies["backend"]:
            technologies["architecture"].add("data-driven")
        
        if {"typescript"} & technologies["languages"]:
            technologies["practices"].add("static-typing")
        
        return technologies
    
    def create_directory_tree(self) -> Dict[str, Any]:
        """
        Create a hierarchical directory tree representation of the repository.
        
        Returns:
            Dictionary representing the repository directory structure
        """
        files = self.get_all_files()
        
        # Create a tree structure
        tree = {}
        
        for file_path in files:
            parts = file_path.split('/')
            current = tree
            
            # Build the tree structure
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # This is a file
                    if "files" not in current:
                        current["files"] = []
                    current["files"].append(part)
                else:  # This is a directory
                    if "dirs" not in current:
                        current["dirs"] = {}
                    if part not in current["dirs"]:
                        current["dirs"][part] = {}
                    current = current["dirs"][part]
        
        # Sort the tree
        return self._sort_tree(tree)
    
    def _sort_tree(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sort the directory tree with directories first, followed by files, both alphabetically.
        
        Args:
            tree: Tree structure to sort
            
        Returns:
            True if the file should be included, False otherwise
        """
        # Convert Windows path separators to Unix style for pattern matching
        file_path = file_path.replace('\\', '/')
        
        # Check if the file matches gitignore patterns
        if self.gitignore_spec and self.gitignore_spec.match_file(file_path):
            return False
        
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
        Group related files based on naming patterns and directory structure.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary of base names and related files
        """
        related_files = defaultdict(list)
        
        # Group by common base name
        for file_path in files:
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            # Handle special cases like index.js, README.md, etc.
            if name.lower() in ["index", "readme", "main", "app"]:
                dir_path = os.path.dirname(file_path)
                base_dir = os.path.basename(dir_path) if dir_path else "root"
                related_files[f"{base_dir}_{name}"].append(file_path)
            else:
                # Handle file pairs like Component.js and Component.test.js
                # Strip .test, .spec, etc., to group related files
                base_name = re.sub(r'\.(test|spec|e2e|unit|integration|mock)$', '', name)
                related_files[base_name].append(file_path)
        
        return dict(related_files)
    
    def identify_modules(self, files: List[str]) -> Dict[str, List[str]]:
        """
        Identify logical modules or components in the repository.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary of module names and their files
        """
        modules = defaultdict(list)
        
        # Common module indicators in path
        module_indicators = [
            "src",
            "lib",
            "app",
            "components",
            "modules",
            "services",
            "controllers",
            "models",
            "views",
            "util",
            "utils",
            "helpers",
            "api"
        ]
        
        for file_path in files:
            parts = file_path.split('/')
            
            # Detect modules based on directory structure
            for i, part in enumerate(parts[:-1]):  # Skip the filename
                if part.lower() in module_indicators:
                    # If this is a module indicator and there's a next part (submodule)
                    if i + 1 < len(parts) - 1:
                        modules[parts[i+1]].append(file_path)
                        break
                    else:
                        # No submodule, so this file belongs directly to the module
                        modules[part].append(file_path)
                        break
            
            # If no module was detected, put in the top-level directory
            if file_path not in [f for module_files in modules.values() for f in module_files]:
                if len(parts) > 1:
                    modules[parts[0]].append(file_path)
                else:
                    modules["root"].append(file_path)
        
        return dict(modules)
    
    def collect_file_samples(self, files: List[str]) -> Dict[str, List[str]]:
        """
        Collect representative file samples from different parts of the repository.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary of sample categories and sample file paths
        """
        samples = {
            "important": [],
            "source_code": [],
            "config": [],
            "documentation": [],
        }
        
        # Important files that should always be included
        important_files = [
            "package.json",
            "requirements.txt",
            "Pipfile",
            "pom.xml",
            "build.gradle",
            "Cargo.toml",
            "Gemfile",
            "composer.json",
            "go.mod",
            "docker-compose.yml",
            "Dockerfile",
            ".travis.yml",
            ".gitlab-ci.yml",
            "webpack.config.js",
            "tsconfig.json",
            "README.md",
            "LICENSE",
            ".env.example",
            "setup.py",
            "pyproject.toml",
            "manage.py",
            "app.py",
            "main.py",
            "index.js",
            "server.js",
        ]
        
        # Find important files
        for file in files:
            filename = os.path.basename(file)
            if filename in important_files:
                samples["important"].append(file)
        
        # Source code files
        source_extensions = [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs", ".c", ".cpp", ".cs", ".php", ".swift", ".kt"
        ]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in source_extensions:
                # Avoid test files
                if not re.search(r'(test|spec|e2e)', file.lower()):
                    samples["source_code"].append(file)
        
        # Limit the number of source code samples to avoid overwhelming
        if len(samples["source_code"]) > 20:
            # Take a diverse sample
            by_ext = defaultdict(list)
            for file in samples["source_code"]:
                _, ext = os.path.splitext(file)
                by_ext[ext].append(file)
            
            # Take up to 5 samples from each extension
            diverse_sample = []
            for ext_files in by_ext.values():
                diverse_sample.extend(ext_files[:5])
            
            # Limit to 20 total
            samples["source_code"] = diverse_sample[:20]
        
        # Config files
        config_extensions = [
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"
        ]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in config_extensions:
                samples["config"].append(file)
        
        # Documentation files
        doc_extensions = [
            ".md", ".rst", ".txt", ".pdf", ".doc", ".docx"
        ]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in doc_extensions:
                samples["documentation"].append(file)
        
        return samples
    
    def analyze_languages(self, files: List[str]) -> Dict[str, int]:
        """
        Analyze programming languages used in the repository.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary of language names and file counts
        """
        extension_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React",
            ".tsx": "React/TypeScript",
            ".java": "Java",
            ".go": "Go",
            ".rb": "Ruby",
            ".rs": "Rust",
            ".c": "C",
            ".cpp": "C++",
            ".cs": "C#",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".sh": "Shell",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "SASS",
            ".less": "LESS",
            ".sql": "SQL",
            ".graphql": "GraphQL",
            ".md": "Markdown",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
        }
        
        language_counts = Counter()
        extension_counts = Counter()
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext:
                ext = ext.lower()
                extension_counts[ext] += 1
                language = extension_map.get(ext, "Other")
                language_counts[language] += 1
        
        return dict(language_counts), dict(extension_counts)
    
    def analyze_repository(self) -> Dict[str, Any]:
        """
        Perform a comprehensive analysis of the repository.
        
        Returns:
            Dictionary containing analysis results
        """
        # Get all files
        files = self.get_all_files()
        
        # Detect frameworks and technologies
        technologies = self.detect_frameworks()
        
        # Create directory tree
        directory_tree = self.create_directory_tree()
        
        # Find related files
        related_files = self.find_related_files(files)
        
        # Identify modules
        modules = self.identify_modules(files)
        
        # Collect file samples
        file_samples = self.collect_file_samples(files)
        
        # Analyze languages
        languages, extension_breakdown = self.analyze_languages(files)
        
        # Return analysis results
        return {
            "file_paths": files,
            "file_count": len(files),
            "technologies": technologies,
            "directory_tree": directory_tree,
            "related_files": related_files,
            "modules": modules,
            "file_samples": file_samples,
            "languages": languages,
            "extension_breakdown": extension_breakdown
        } 