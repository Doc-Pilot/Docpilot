"""
Repository Scanner Module
========================

Core utilities for scanning repositories and analyzing their structure.
Provides hierarchical representations optimized for documentation generation.
"""

# Importing Dependencies
import os
import re
import json
import fnmatch
import logging
from collections import defaultdict, Counter
from typing import List, Dict, Any, Set, Tuple

# Setting up logging
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
        # Normalize repository path to handle Windows paths correctly
        self.repo_path = os.path.abspath(repo_path)
        self.include_patterns = include_patterns or ["*"]
        
        # Core exclude patterns focused on documentation relevance
        # Make sure .git is always excluded regardless of gitignore
        default_exclude_patterns = [
            "**/.git/**", 
            ".git/**", 
            "**/node_modules/**", 
            "**/venv/**", 
            "**/__pycache__/**",
            "**/.pytest_cache/**", 
            "**/build/**", 
            "**/dist/**",
            "**/coverage/**", 
            "**/logs/**", 
            "**/*.log", 
            "**/*.pyc",
            "**/tmp/**", 
            "**/.cache/**", 
            "**/*.egg-info/**"
        ]
        
        self.exclude_patterns = exclude_patterns or default_exclude_patterns
        self.gitignore_spec = None
        self.gitignore_patterns = []
        if use_gitignore:
            self._load_gitignore()
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path separators for consistent handling across platforms.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized path with forward slashes
        """
        # Convert backslashes to forward slashes and remove any double slashes
        return path.replace('\\', '/').replace('//', '/')
    
    def _load_gitignore(self):
        """Load .gitignore file and create a spec for matching"""
        gitignore_path = os.path.join(self.repo_path, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    gitignore_content = f.read()
                    
                # Try to use pathspec if available, otherwise use a simple fallback
                try:
                    import pathspec
                    self.gitignore_spec = pathspec.PathSpec.from_lines(
                        pathspec.patterns.GitWildMatchPattern, 
                        gitignore_content.splitlines()
                    )
                except ImportError:
                    # Simple fallback implementation
                    logger.warning("pathspec module not available, using simple gitignore parsing")
                    self.gitignore_patterns = []
                    for line in gitignore_content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Convert glob pattern to regex pattern
                            pattern = line.replace('.', '\\.')
                            pattern = pattern.replace('*', '.*')
                            pattern = pattern.replace('?', '.')
                            if not pattern.startswith('/'):
                                pattern = f".*{pattern}"
                            self.gitignore_patterns.append(pattern)
                
                logger.debug(f"Loaded gitignore from {gitignore_path}")
            except Exception as e:
                logger.warning(f"Failed to parse .gitignore: {str(e)}")
                self.gitignore_spec = None
                self.gitignore_patterns = []
    
    def scan_files(self) -> List[str]:
        """
        Get all relevant files in the repository.
        
        Returns:
            List of file paths relative to the repository root
        """
        all_files = []
        
        try:
            for root, dirs, files in os.walk(self.repo_path):
                # Get relative paths for current directory
                rel_root = os.path.relpath(root, self.repo_path)
                rel_root = self._normalize_path(rel_root)
                
                # Explicitly skip .git directories
                if '.git' in dirs:
                    dirs.remove('.git')
                
                # Handle the root directory case
                if rel_root == '.':
                    rel_root = ''
                
                # Filter directories in-place to avoid traversing excluded paths
                dirs[:] = [
                    d for d in dirs 
                    if self._should_include_file(
                        self._normalize_path(os.path.join(rel_root, d) + '/')
                    )
                ]
                
                # Filter and add files
                for file in files:
                    rel_path = self._normalize_path(os.path.join(rel_root, file))
                    if self._should_include_file(rel_path):
                        all_files.append(rel_path)
                        
            logger.debug(f"Found {len(all_files)} files in repository")
            return all_files
            
        except Exception as e:
            logger.error(f"Error scanning repository: {str(e)}")
            return []
    
    def _should_include_file(self, file_path: str) -> bool:
        """
        Check if a file should be included based on patterns and gitignore rules.
        
        Args:
            file_path: Path to check relative to repo root
            
        Returns:
            True if file should be included
        """
        # Normalize path separators
        file_path = self._normalize_path(file_path)
        
        # Always exclude .git files and directories
        if file_path.startswith('.git/') or file_path == '.git':
            return False
        
        # Check exclude patterns first (they take precedence)
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return False
        
        # Check gitignore patterns
        if hasattr(self, 'gitignore_spec') and self.gitignore_spec:
            # Use pathspec for matching
            # Check file path
            if self.gitignore_spec.match_file(file_path):
                return False
            
            # Check directory path for directories
            if file_path.endswith('/'):
                if self.gitignore_spec.match_file(file_path):
                    return False
            # Check parent directory for files
            else:
                dir_path = os.path.dirname(file_path)
                if dir_path and self.gitignore_spec.match_file(f"{dir_path}/"):
                    return False
        elif hasattr(self, 'gitignore_patterns'):
            # Use our simple fallback implementation
            import re
            for pattern in self.gitignore_patterns:
                if re.match(pattern, file_path):
                    return False
        
        # Check include patterns
        return any(fnmatch.fnmatch(file_path, p) for p in self.include_patterns)
    
    def detect_frameworks(self) -> Dict[str, Set[str]]:
        """
        Detect frameworks and technologies used in the repository.
        
        Returns:
            Dictionary of technology categories and detected technologies
        """
        # Get all files
        files = self.scan_files()
        
        # Get language statistics to verify technologies
        language_counts, _ = self.analyze_languages(files)
        languages_present = set(language_counts.keys())
        
        # Define patterns for technology detection
        technology_patterns = {
            "frontend": {
                "react": ["react", "jsx", "react-dom", "react-router"],
                "vue": ["vue", "vuex", "vue-router"],
                "angular": ["angular", "@angular", "ng-"],
                "svelte": ["svelte"],
                "nextjs": ["next", "next.js"],
                "tailwind": ["tailwind", "tailwindcss"],
                "bootstrap": ["bootstrap"],
                "material-ui": ["@mui", "material-ui"],
            },
            "backend": {
                "express": ["express"],
                "django": ["django", "wsgi"],
                "flask": ["flask"],
                "fastapi": ["fastapi"],
                "spring": ["spring", "springframework"],
                "nestjs": ["@nestjs", "nest"],
                "graphql": ["graphql", "apollo"],
                "rails": ["rails", "activerecord"],
            },
            "database": {
                "mongodb": ["mongo", "mongodb"],
                "postgresql": ["postgres", "postgresql", "psycopg2", "pg"],
                "mysql": ["mysql"],
                "sqlite": ["sqlite"],
                "redis": ["redis"],
                "prisma": ["prisma"],
                "typeorm": ["typeorm"],
                "sequelize": ["sequelize"],
            },
            "testing": {
                "jest": ["jest"],
                "mocha": ["mocha"],
                "pytest": ["pytest"],
                "unittest": ["unittest"],
                "jasmine": ["jasmine"],
                "cypress": ["cypress"],
                "selenium": ["selenium"],
            },
            "devops": {
                "docker": ["docker", "dockerfile"],
                "kubernetes": ["kubernetes", "k8s"],
                "ci-cd": ["ci", "cd", "ci/cd", "github/workflows", "github-actions"],
                "aws": ["aws", "amazon web services", "boto3", "aws-sdk"],
                "azure": ["azure", "@azure"],
                "terraform": ["terraform", ".tf"],
            },
        }
        
        # Initialize technologies with confidence scores (internal)
        tech_confidence = defaultdict(lambda: defaultdict(float))
        
        # Add detected languages with high confidence
        for lang in languages_present:
            if lang != "Other":
                norm_lang = lang.lower()
                if norm_lang in ["python", "javascript", "typescript", "ruby", "go", "rust", "java", "c#", "c++", "php"]:
                    tech_confidence["languages"][norm_lang] = 1.0
        
        # Find and analyze dependency files for more accurate detection
        dependency_files = []
        
        # Key dependency files by language/ecosystem
        python_deps = ["requirements.txt", "setup.py", "Pipfile", "pyproject.toml"]
        js_deps = ["package.json", "package-lock.json", "yarn.lock"]
        ruby_deps = ["Gemfile", "Gemfile.lock"]
        java_deps = ["pom.xml", "build.gradle"]
        rust_deps = ["Cargo.toml"]
        go_deps = ["go.mod", "go.sum"]
        
        # Infrastructure files
        infra_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".github/workflows/"]
        
        for file in files:
            filename = os.path.basename(file)
            if filename in python_deps + js_deps + ruby_deps + java_deps + rust_deps + go_deps + infra_files:
                dependency_files.append(file)
                
            # Check for GitHub workflows directory
            if '.github/workflows' in file and (file.endswith('.yml') or file.endswith('.yaml')):
                tech_confidence['devops']['ci-cd'] = 1.0
        
        # Analyze dependency files (most reliable signal)
        for dep_file in dependency_files:
            try:
                file_path = os.path.join(self.repo_path, dep_file)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Python dependencies
                    if dep_file.endswith('requirements.txt'):
                        self._analyze_python_requirements(content, tech_confidence)
                    elif dep_file.endswith('setup.py'):
                        self._analyze_setup_py(content, tech_confidence)
                    elif dep_file.endswith('Pipfile') or dep_file.endswith('pyproject.toml'):
                        self._analyze_python_deps(content, tech_confidence)
                    
                    # JavaScript/TypeScript dependencies
                    elif dep_file.endswith('package.json'):
                        self._analyze_package_json(content, tech_confidence)
                    
                    # Infrastructure
                    elif dep_file.endswith('Dockerfile'):
                        tech_confidence['devops']['docker'] = 1.0
                    elif dep_file.endswith('docker-compose.yml') or dep_file.endswith('docker-compose.yaml'):
                        tech_confidence['devops']['docker'] = 1.0
                        self._analyze_docker_compose(content, tech_confidence)
                    
            except Exception as e:
                logger.debug(f"Error analyzing {dep_file}: {str(e)}")
        
        # Fallback to pattern matching for files with lower confidence
        for file in files:
            file_lower = file.lower()
            
            for category, techs in technology_patterns.items():
                for tech, patterns in techs.items():
                    for pattern in patterns:
                        if pattern in file_lower or f"/{pattern}/" in file_lower:
                            # Set confidence to 0.7 (lower than dependency files)
                            tech_confidence[category][tech] = max(tech_confidence[category][tech], 0.7)
        
        # Specific technology validations based on languages
        if tech_confidence["languages"]["python"] > 0.5:
            # Look for pytest.ini
            if any(file.endswith('pytest.ini') for file in files):
                tech_confidence["testing"]["pytest"] = 1.0
            
            # FastAPI detection
            if tech_confidence["backend"]["fastapi"] < 0.5:
                # Check main Python files for FastAPI imports
                for file in files:
                    if file.endswith('.py'):
                        try:
                            with open(os.path.join(self.repo_path, file), 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(1024)  # Read first KB to check imports
                                if 'import fastapi' in content or 'from fastapi import' in content:
                                    tech_confidence["backend"]["fastapi"] = 0.95
                                    break
                        except:
                            pass
        
        # Make additional inferences based on detected technologies
        if any(v > 0.5 for v in tech_confidence["frontend"].values()) and any(v > 0.5 for v in tech_confidence["backend"].values()):
            tech_confidence["architecture"]["full-stack"] = 0.9
        
        if any(v > 0.5 for v in tech_confidence["database"].values()) and any(v > 0.5 for v in tech_confidence["backend"].values()):
            tech_confidence["architecture"]["data-driven"] = 0.8
        
        if tech_confidence["languages"]["typescript"] > 0.5:
            tech_confidence["practices"]["static-typing"] = 0.9
        
        # Convert confidence scores to final result (threshold > 0.5)
        technologies = defaultdict(set)
        for category, techs in tech_confidence.items():
            for tech, confidence in techs.items():
                if confidence > 0.5:  # Only include high confidence detections
                    technologies[category].add(tech)
                    
        return technologies
        
    def _analyze_python_requirements(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        """Analyze Python requirements.txt file for dependencies"""
        # Map from dependency name to technology and category
        dep_to_tech = {
            # Backend frameworks
            "flask": ("flask", "backend", 1.0),
            "fastapi": ("fastapi", "backend", 1.0),
            "django": ("django", "backend", 1.0),
            "starlette": ("fastapi", "backend", 0.8),  # FastAPI is built on Starlette
            
            # Databases
            "psycopg2": ("postgresql", "database", 1.0),
            "psycopg2-binary": ("postgresql", "database", 1.0),
            "pymongo": ("mongodb", "database", 1.0),
            "sqlalchemy": ("sql", "database", 0.8),
            "redis": ("redis", "database", 1.0),
            
            # Testing
            "pytest": ("pytest", "testing", 1.0),
            "selenium": ("selenium", "testing", 1.0),
            
            # AWS
            "boto3": ("aws", "devops", 1.0),
            "aws-sdk": ("aws", "devops", 1.0),
        }
        
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (handles various formats like ==, >=, etc.)
                package = line.split('==')[0].split('>=')[0].split('<=')[0].split('<')[0].split('>')[0].strip()
                package = package.lower()
                
                # Check against known packages
                if package in dep_to_tech:
                    tech, category, confidence = dep_to_tech[package]
                    tech_confidence[category][tech] = max(tech_confidence[category][tech], confidence)
    
    def _analyze_setup_py(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        """Analyze Python setup.py file for dependencies"""
        # Look for install_requires section
        if "install_requires" in content:
            # Extract dependencies from install_requires
            matches = re.findall(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if matches:
                deps_str = matches[0]
                # Extract quoted strings
                deps = re.findall(r'[\'\"](.*?)[\'\"]', deps_str)
                
                # Process as if it were a requirements.txt file
                self._analyze_python_requirements("\n".join(deps), tech_confidence)
    
    def _analyze_python_deps(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        """Analyze Python dependency files like Pipfile or pyproject.toml"""
        # Extract potential package names
        packages = re.findall(r'[\'"]([a-zA-Z0-9_-]+)[\'"]', content)
        packages.extend(re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=', content, re.MULTILINE))
        
        # Process as if it were a requirements.txt file
        self._analyze_python_requirements("\n".join(packages), tech_confidence)
    
    def _analyze_package_json(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        """Analyze Node.js package.json file for dependencies"""
        try:
            data = json.loads(content)
            
            # Map from dependency name to technology and category
            dep_to_tech = {
                # Frontend
                "react": ("react", "frontend", 1.0),
                "vue": ("vue", "frontend", 1.0),
                "next": ("nextjs", "frontend", 1.0),
                "angular": ("angular", "frontend", 1.0),
                "@angular/core": ("angular", "frontend", 1.0),
                "svelte": ("svelte", "frontend", 1.0),
                "tailwindcss": ("tailwind", "frontend", 1.0),
                "bootstrap": ("bootstrap", "frontend", 1.0),
                
                # Backend
                "express": ("express", "backend", 1.0),
                "fastify": ("fastify", "backend", 1.0),
                "koa": ("koa", "backend", 1.0),
                "nest": ("nestjs", "backend", 1.0),
                "@nestjs/core": ("nestjs", "backend", 1.0),
                
                # Databases
                "mongodb": ("mongodb", "database", 1.0),
                "mongoose": ("mongodb", "database", 0.9),
                "pg": ("postgresql", "database", 1.0),
                "mysql": ("mysql", "database", 1.0),
                "mysql2": ("mysql", "database", 1.0),
                "redis": ("redis", "database", 1.0),
                "sqlite3": ("sqlite", "database", 1.0),
                
                # Testing
                "jest": ("jest", "testing", 1.0),
                "mocha": ("mocha", "testing", 1.0),
                "chai": ("chai", "testing", 0.9),
                "cypress": ("cypress", "testing", 1.0),
                
                # TypeScript
                "typescript": ("typescript", "languages", 1.0),
                
                # AWS
                "aws-sdk": ("aws", "devops", 1.0),
            }
            
            # Check for TypeScript
            if "typescript" in data.get("devDependencies", {}) or "typescript" in data.get("dependencies", {}):
                tech_confidence["languages"]["typescript"] = 1.0
                tech_confidence["practices"]["static-typing"] = 0.9
            
            # Process dependencies
            for section in ["dependencies", "devDependencies"]:
                if section in data:
                    for package in data[section].keys():
                        # Check for exact matches
                        if package in dep_to_tech:
                            tech, category, confidence = dep_to_tech[package]
                            tech_confidence[category][tech] = max(tech_confidence[category][tech], confidence)
                        
                        # Check for partial matches (like @angular/*)
                        for prefix, (tech, category, confidence) in dep_to_tech.items():
                            if prefix.endswith('/') and package.startswith(prefix):
                                tech_confidence[category][tech] = max(tech_confidence[category][tech], confidence)
        except:
            # If JSON parsing fails, fall back to regex-based detection
            for dep, (tech, category, confidence) in dep_to_tech.items():
                if f'"{dep}"' in content or f"'{dep}'" in content:
                    tech_confidence[category][tech] = max(tech_confidence[category][tech], confidence * 0.8)
    
    def _analyze_docker_compose(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        """Analyze docker-compose.yml for service technologies"""
        service_tech_map = {
            "postgres": ("postgresql", "database", 0.9),
            "mysql": ("mysql", "database", 0.9),
            "redis": ("redis", "database", 0.9),
            "mongo": ("mongodb", "database", 0.9),
            "elasticsearch": ("elasticsearch", "database", 0.8),
        }
        
        # Check for services
        for service, (tech, category, confidence) in service_tech_map.items():
            if f"image: {service}" in content:
                tech_confidence[category][tech] = max(tech_confidence[category][tech], confidence)
    
    def create_directory_tree(self) -> Dict[str, Any]:
        """
        Create a hierarchical directory tree representation of the repository.
        
        Returns:
            Dictionary representing the repository directory structure
        """
        files = self.scan_files()
        
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
    
    def create_markdown_tree(self) -> str:
        """
        Create a Markdown-formatted directory tree representation.
        
        Returns:
            String containing the Markdown representation of the directory tree
        """
        files = self.scan_files()
        
        # Sort files to ensure consistent output
        files.sort()
        
        # Build a tree structure
        tree = {}
        for file_path in files:
            parts = file_path.split('/')
            current = tree
            for part in parts[:-1]:  # Process directories
                if part not in current:
                    current[part] = {}
                current = current[part]
                
            # Add the file to the current directory
            if "__files__" not in current:
                current["__files__"] = []
            current["__files__"].append(parts[-1])
        
        # Generate markdown
        markdown_lines = ["# Repository Structure", ""]
        
        def traverse_tree(node, prefix="", depth=0):
            # First process directories
            dirs = sorted([k for k in node.keys() if k != "__files__"])
            for i, dir_name in enumerate(dirs):
                is_last = i == len(dirs) - 1 and "__files__" not in node
                
                if depth == 0:
                    # Root level directories with simple formatting (no ## headers)
                    markdown_lines.append(f"{dir_name}/")
                    markdown_lines.append("") # Add empty line after root directory
                    traverse_tree(node[dir_name], "", depth + 1)
                    if i < len(dirs) - 1:
                        markdown_lines.append("") # Add separator between root directories
                else:
                    # Print the directory with the appropriate prefix
                    connector = "└── " if is_last else "├── "
                    dir_line = f"{prefix}{connector}{dir_name}/"
                    markdown_lines.append(dir_line)
                    
                    # Prepare the prefix for children
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    traverse_tree(node[dir_name], new_prefix, depth + 1)
            
            # Then process files
            if "__files__" in node:
                files = sorted(node["__files__"])
                for i, file_name in enumerate(files):
                    is_last = i == len(files) - 1
                    connector = "└── " if is_last else "├── "
                    file_line = f"{prefix}{connector}{file_name}"
                    markdown_lines.append(file_line)
        
        traverse_tree(tree)
        
        return "\n".join(markdown_lines)
    
    def create_tree(self) -> str:
        """
        Create a simple text-based directory tree representation with indentation.
        
        Returns:
            String containing the text representation of the directory tree
        """
        files = self.scan_files()
        
        # Sort files to ensure consistent output
        files.sort()
        
        # Build a tree structure
        tree = {}
        for file_path in files:
            parts = file_path.split('/')
            current = tree
            for part in parts[:-1]:  # Process directories
                if part not in current:
                    current[part] = {}
                current = current[part]
                
            # Add the file to the current directory
            if "__files__" not in current:
                current["__files__"] = []
            current["__files__"].append(parts[-1])
        
        # Get repository name (basename of repo_path)
        repo_name = os.path.basename(os.path.abspath(self.repo_path))
        
        # Generate text representation
        lines = [f"📁 {repo_name}"]
        
        def traverse_tree(node, prefix="", is_last=True, indent_level=0):
            # Process directories first
            dirs = sorted([k for k in node.keys() if k != "__files__"])
            
            # Process files next
            files = []
            if "__files__" in node:
                files = sorted(node["__files__"])
            
            # Process all items
            total_items = len(dirs) + len(files)
            processed = 0
            
            # First process directories
            for dir_name in dirs:
                processed += 1
                is_last_item = (processed == total_items)
                
                # Choose the correct prefix based on whether this is the last item
                if is_last_item:
                    conn = "└─→ "
                    next_prefix = prefix + "    "
                else:
                    conn = "├─→ "
                    next_prefix = prefix + "│   "
                
                # Add directory with proper formatting
                lines.append(f"{prefix}{conn}📁 {dir_name}/")
                
                # Process children with appropriate indentation
                traverse_tree(node[dir_name], next_prefix, is_last_item)
            
            # Then process files
            for i, file_name in enumerate(files):
                is_last_item = (processed + i + 1 == total_items)
                
                # Choose connector based on position
                conn = "└─→ " if is_last_item else "├─→ "
                
                # Add file with proper indentation and icon
                ext = os.path.splitext(file_name)[1].lower()
                
                # Choose icon based on file extension
                if ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb']:
                    icon = "📜"  # Code file
                elif ext in ['.md', '.txt', '.rst', '.adoc']:
                    icon = "📄"  # Documentation
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg']:
                    icon = "⚙️"   # Config file
                elif ext in ['.jpg', '.png', '.gif', '.svg', '.bmp']:
                    icon = "🖼️"   # Image
                elif ext in ['.html', '.css', '.scss', '.sass']:
                    icon = "🌐"   # Web file
                else:
                    icon = "📋"   # Generic file
                
                lines.append(f"{prefix}{conn}{icon} {file_name}")
        
        # Start traversal from root with no prefix
        traverse_tree(tree)
        
        return "\n".join(lines)
    
    def _sort_tree(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sort the directory tree with directories first, followed by files, both alphabetically.
        
        Args:
            tree: Tree structure to sort
            
        Returns:
            Sorted tree structure
        """
        result = {}
        
        # Sort and add directories
        if "dirs" in tree:
            result["dirs"] = {}
            for name in sorted(tree["dirs"].keys()):
                result["dirs"][name] = self._sort_tree(tree["dirs"][name])
        
        # Sort and add files
        if "files" in tree:
            result["files"] = sorted(tree["files"])
        
        return result
    
    def get_file_extension_breakdown(self, file_list: List[str]) -> Dict[str, List[str]]:
        """
        Group related files based on naming patterns and directory structure.
        
        Args:
            file_list: List of file paths
            
        Returns:
            Dictionary of base names and related files
        """
        related_files = defaultdict(list)
        
        # Group by common base name
        for file_path in file_list:
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
    
    def analyze_languages(self, files: List[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Analyze programming languages used in the repository.
        
        Args:
            files: List of file paths
            
        Returns:
            Tuple of (language counts, extension counts)
        """
        extension_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React/JavaScript",
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
        Analyze repository structure focused on documentation needs.
        
        Returns:
            Dictionary containing analysis results
        """
        files = self.scan_files()
        
        if not files:
            logger.warning(f"No files found in repository scan for {self.repo_path}")
            
        # Perform analysis
        technologies = self.detect_frameworks()
        structure = self.create_directory_tree()
        modules = self.identify_modules(files)
        languages, extensions = self.analyze_languages(files)
        
        # Convert defaultdict to regular dict for JSON serialization
        tech_dict = {}
        for category, techs in technologies.items():
            tech_dict[category] = list(techs)
            
        return {
            "files": files,
            "technologies": tech_dict,
            "structure": structure,
            "modules": modules,
            "languages": languages,
            "extensions": extensions
        } 