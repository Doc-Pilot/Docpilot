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
from collections import defaultdict, Counter
from typing import List, Dict, Any, Set, Tuple

from .logging import core_logger  # Import core_logger

# Setting up logging
logger = core_logger()

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
                logger.warning(f"Failed to parse .gitignore: {str(e)}", exc_info=True)
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
            logger.error(f"Error scanning repository: {str(e)}", exc_info=True)
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
    
    def detect_frameworks(self) -> Tuple[Dict[str, Set[str]], Set[str]]:
        """
        Detect frameworks and technologies, focusing on identifying API frameworks.
        
        Returns:
            Tuple[Dict[str, Set[str]], Set[str]]: 
                - Dictionary of general technology categories and detected technologies.
                - Set of specifically identified API frameworks (lowercase).
        """
        files = self.scan_files()
        language_counts, _ = self.analyze_languages(files)
        languages_present = set(language_counts.keys())
        
        technology_patterns = {
            # General categories
            "frontend": {
                "React": ["react", "jsx", "react-dom", "react-router"],
                "Vue": ["vue", "vuex", "vue-router"],
                "Angular": ["angular", "@angular", "ng-"],
                "Svelte": ["svelte"],
                "Next.js": ["next", "next.js"],
                "Tailwind CSS": ["tailwind", "tailwindcss"],
                "Bootstrap": ["bootstrap"],
                "Material UI": ["@mui", "material-ui"],
            },
            "backend": {
                "Node.js": ["node"], # Generic, will be refined by specific frameworks
                "Python": ["python"], # Generic
                "Java": ["java", "jvm"],
                "Ruby": ["ruby"],
                "Go": ["golang", "go"],
                "PHP": ["php"]
            },
            "database": {
                "PostgreSQL": ["postgresql", "postgres", "psycopg2"],
                "MySQL": ["mysql", "mysqlclient"],
                "SQLite": ["sqlite"],
                "MongoDB": ["mongodb", "pymongo"],
                "Redis": ["redis", "pyredis"],
                "SQLAlchemy": ["sqlalchemy"],
                "Prisma": ["prisma"],
            },
            "testing": {
                "Pytest": ["pytest"],
                "Jest": ["jest"],
                "Mocha": ["mocha"],
                "JUnit": ["junit"],
                "Selenium": ["selenium"],
            },
            "devops": {
                "Docker": ["docker", "Dockerfile", "docker-compose"],
                "Kubernetes": ["kubernetes", "kubectl"],
                "Terraform": ["terraform", ".tf"],
                "AWS": ["aws", "boto3"],
                "GCP": ["gcp", "google-cloud"],
                "Azure": ["azure"],
            },
            # Specific API Framework patterns - used for direct identification
            "api_frameworks": {
                "FastAPI": ["fastapi"],
                "Flask": ["flask"],
                "Django REST framework": ["djangorestframework", "drf"],
                "Express": ["express"],
                "NestJS": ["@nestjs", "nest"],
                "Spring Boot": ["spring-boot", "@SpringBootApplication"],
                "Ruby on Rails": ["rails", "activerecord"], # Rails often implies API
            }
        }

        tech_confidence = defaultdict(lambda: defaultdict(float))
        all_detected_tech = defaultdict(set)
        detected_api_frameworks = set()

        # 1. Scan specific configuration/dependency files
        for file_path in files:
            filename = os.path.basename(file_path).lower()
            full_path = os.path.join(self.repo_path, file_path)
            
            try:
                content = ""
                # Python
                if filename == "requirements.txt":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_python_requirements(content, tech_confidence)
                elif filename == "pyproject.toml":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_pyproject_toml(content, tech_confidence)
                elif filename == "setup.py" or filename == "setup.cfg":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_setup_py(content, tech_confidence)
                # JavaScript
                elif filename == "package.json":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_package_json(content, tech_confidence)
                # Java
                elif filename == "pom.xml":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_pom_xml(content, tech_confidence)
                elif filename.endswith("build.gradle") or filename.endswith("build.gradle.kts"): 
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_gradle(content, tech_confidence)
                # Ruby
                elif filename == "gemfile":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_gemfile(content, tech_confidence)
                # PHP
                elif filename == "composer.json":
                     with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                     self._analyze_composer_json(content, tech_confidence)
                # Go
                elif filename == "go.mod":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_go_mod(content, tech_confidence)
                # DevOps
                elif filename == "dockerfile":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self._analyze_dockerfile(content, tech_confidence)
                elif filename == "docker-compose.yml" or filename == "docker-compose.yaml":
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        self._analyze_docker_compose(content, tech_confidence)
            except Exception as e:
                logger.warning(f"Failed to read or analyze file {file_path}: {str(e)}")

        # 2. Scan file contents for specific framework patterns (more expensive)
        for file_path in files:
            full_path = os.path.join(self.repo_path, file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Only scan relevant file types
            scan_content = False
            if file_ext in [".py", ".js", ".ts", ".java", ".rb", ".go", ".php"]:
                scan_content = True
                
            if scan_content:
                try:
                    # Limit reading large files
                    if os.path.getsize(full_path) > 1 * 1024 * 1024: # 1MB limit
                        continue 
                        
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Read only first N lines for performance
                        content_sample = "".join(f.readline() for _ in range(200))
                        
                    # Apply content-based patterns
                    for category, patterns in technology_patterns.items():
                        for tech, keywords in patterns.items():
                            if any(keyword.lower() in content_sample.lower() for keyword in keywords):
                                tech_confidence[category][tech] += 0.1 # Lower confidence for content match

                except Exception as e:
                     logger.debug(f"Could not read file {file_path} for content analysis: {str(e)}")


        # 3. Consolidate results based on confidence thresholds
        confidence_threshold = 0.3 # Heuristic threshold
        
        for category, techs in tech_confidence.items():
            for tech, confidence in techs.items():
                if confidence >= confidence_threshold:
                    all_detected_tech[category].add(tech)
                    # Specifically track identified API frameworks
                    if category == "api_frameworks":
                        detected_api_frameworks.add(tech.lower().replace(" ", "_").replace("rest_framework", "")) # Normalize name
                        # Also add to general backend category if relevant
                        if tech == "FastAPI": all_detected_tech["backend"].add("FastAPI")
                        if tech == "Flask": all_detected_tech["backend"].add("Flask")
                        if tech == "Django REST framework": all_detected_tech["backend"].add("Django")
                        if tech == "Express": all_detected_tech["backend"].add("Express")
                        if tech == "NestJS": all_detected_tech["backend"].add("NestJS")
                        if tech == "Spring Boot": all_detected_tech["backend"].add("Spring Boot")
                        if tech == "Ruby on Rails": all_detected_tech["backend"].add("Ruby on Rails")
                            
        # Remove the specific api_frameworks category from the general results
        if "api_frameworks" in all_detected_tech:
            del all_detected_tech["api_frameworks"]
            
        # Basic language check consistency (e.g., don't report Flask if no Python files)
        if "Flask" in all_detected_tech.get("backend", set()) and "Python" not in languages_present:
            all_detected_tech["backend"].discard("Flask")
            detected_api_frameworks.discard("flask")
        if "Express" in all_detected_tech.get("backend", set()) and not ("JavaScript" in languages_present or "TypeScript" in languages_present):
             all_detected_tech["backend"].discard("Express")
             detected_api_frameworks.discard("express")
        # Add more checks as needed...
            
        logger.info(f"Detected technologies: {dict(all_detected_tech)}")
        logger.info(f"Detected API Frameworks: {detected_api_frameworks}")
        return dict(all_detected_tech), detected_api_frameworks

    # Helper methods for analyzing specific dependency files
    def _analyze_python_requirements(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        lines = content.splitlines()
        for line in lines:
            line = line.strip().split('#')[0] # Remove comments
            if not line: continue
            match = re.match(r"^([a-zA-Z0-9\-_]+)", line)
            if match:
                package = match.group(1).lower()
                self._check_package_against_patterns(package, tech_confidence)

    def _analyze_pyproject_toml(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        try:
            import toml
            data = toml.loads(content)
            dependencies = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
            dev_dependencies = data.get('tool', {}).get('poetry', {}).get('dev-dependencies', {})
            optional_dependencies = data.get('tool', {}).get('poetry', {}).get('extras', {})
            
            all_deps = {**dependencies, **dev_dependencies}
            for group in optional_dependencies.values():
                 if isinstance(group, list): 
                     for item in group: all_deps[item] = '*' # Add extras packages
            
            # Also check [project] section for standard dependencies
            project_deps = data.get('project', {}).get('dependencies', [])
            project_optional_deps = data.get('project', {}).get('optional-dependencies', {})
            
            for dep in project_deps:
                 match = re.match(r"^([a-zA-Z0-9\-_]+)", dep)
                 if match: all_deps[match.group(1)] = '*'
            
            for group in project_optional_deps.values():
                for dep in group:
                     match = re.match(r"^([a-zA-Z0-9\-_]+)", dep)
                     if match: all_deps[match.group(1)] = '*'
            
            for package in all_deps.keys():
                self._check_package_against_patterns(package.lower(), tech_confidence)
        except ImportError:
            logger.warning("toml package not installed, skipping pyproject.toml analysis.")
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")
    
    def _analyze_setup_py(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        # Basic regex parsing, less reliable than AST but avoids execution
        matches = re.findall(r"install_requires\s*=\s*\[([^\]]*)\]", content, re.MULTILINE) # Regex 1
        deps = []
        for match in matches:
            deps.extend(re.findall(r"[\'\"]([a-zA-Z0-9\-_]+)[\'\"]", match)) # Regex 2

        matches_extras = re.findall(r"extras_require\s*=\s*{[^}]*}", content, re.DOTALL) # Regex 3
        for match in matches_extras:
             deps.extend(re.findall(r"[\'\"]([a-zA-Z0-9\-_]+)[\'\"]", match)) # Regex 4 (same as 2)

        for package in deps:
             self._check_package_against_patterns(package.lower(), tech_confidence)
    
    def _analyze_package_json(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        try:
            data = json.loads(content)
            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            all_deps = {**dependencies, **dev_dependencies}
            for package in all_deps.keys():
                self._check_package_against_patterns(package.lower(), tech_confidence)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse package.json: {e}")
            
    def _analyze_pom_xml(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        # Basic regex, misses versions and scopes but finds artifacts
        matches = re.findall(r"<artifactId>([^<]+)</artifactId>", content)
        for artifact in matches:
             self._check_package_against_patterns(artifact.lower(), tech_confidence)
             
    def _analyze_gradle(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        # Very basic regex for common dependency declarations
        # Corrected regex:
        matches = re.findall(r"(?:implementation|compile|api)\s*[\(\'\"]\s*([a-zA-Z0-9._\-]+:[a-zA-Z0-9._\-]+)(?::[^\s\'\"\)]+)?\s*[\'\"\)]", content)
        matches += re.findall(r"implementation\(libs\.([a-zA-Z0-9\-_\.]+)\)", content) # For version catalogs
        for dep in matches:
            artifact = dep.split(':')[1] if ':' in dep else dep
            artifact = artifact.replace('.', '-') # Normalize catalog names
            self._check_package_against_patterns(artifact.lower(), tech_confidence)
            
    def _analyze_gemfile(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        matches = re.findall(r"gem\s+['\"]([a-zA-Z0-9\-_]+)['\"]", content)
        for gem in matches:
            self._check_package_against_patterns(gem.lower(), tech_confidence)
    def _analyze_composer_json(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        try:
            data = json.loads(content)
            dependencies = data.get("require", {})
            dev_dependencies = data.get("require-dev", {})
            all_deps = {**dependencies, **dev_dependencies}
            for package in all_deps.keys():
                package_name = package.split('/')[-1] # Get name after vendor
                self._check_package_against_patterns(package_name.lower(), tech_confidence)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse composer.json: {e}")

    def _analyze_go_mod(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        matches = re.findall(r"require\s+(?:\(|([^\s\n]+))", content)
        deps = []
        if matches:
            if '(' in matches[0]: # Multi-line require block
                block_content = re.search(r"require\s+\((.*?)\)", content, re.DOTALL)
                if block_content:
                    deps = re.findall(r"^\s*([^\s]+)", block_content.group(1), re.MULTILINE)
            else: # Single line require
                 deps = [matches[0]]
                 
        for dep in deps:
            package_name = dep.split('/')[-1] # Heuristic to get package name
            self._check_package_against_patterns(package_name.lower(), tech_confidence)

    def _analyze_dockerfile(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        tech_confidence["devops"]["Docker"] += 0.5
        if "python" in content.lower(): tech_confidence["backend"]["Python"] += 0.1
        if "node" in content.lower(): tech_confidence["backend"]["Node.js"] += 0.1
        if "java" in content.lower(): tech_confidence["backend"]["Java"] += 0.1
        # Add more language/base image checks

    def _analyze_docker_compose(self, content: str, tech_confidence: Dict[str, Dict[str, float]]) -> None:
        tech_confidence["devops"]["Docker"] += 0.5
        # Check service images for tech clues
        if "postgres" in content.lower(): tech_confidence["database"]["PostgreSQL"] += 0.3
        if "mysql" in content.lower(): tech_confidence["database"]["MySQL"] += 0.3
        if "redis" in content.lower(): tech_confidence["database"]["Redis"] += 0.3
        if "mongo" in content.lower(): tech_confidence["database"]["MongoDB"] += 0.3
        if "python" in content.lower(): tech_confidence["backend"]["Python"] += 0.1
        if "node" in content.lower(): tech_confidence["backend"]["Node.js"] += 0.1

    def _check_package_against_patterns(self, package_name: str, tech_confidence: Dict[str, Dict[str, float]]):
        """Helper to check a package name against defined technology patterns."""
        package_name = package_name.lower().replace('_', '-') # Normalize
        
        technology_patterns = {
            "frontend": {
                "React": ["react", "react-dom"],
                "Vue": ["vue", "vuex", "vue-router"],
                "Angular": ["@angular/core", "@angular/common"],
                "Svelte": ["svelte"],
                "Next.js": ["next"],
                "Tailwind CSS": ["tailwindcss"],
                "Bootstrap": ["bootstrap", "react-bootstrap", "ng-bootstrap"],
                "Material UI": ["@mui/material", "material-ui"],
            },
            "api_frameworks": {
                "FastAPI": ["fastapi"],
                "Flask": ["flask"],
                "Django REST framework": ["djangorestframework"],
                "Express": ["express"],
                "NestJS": ["@nestjs/core", "@nestjs/common"],
                "Spring Boot": ["spring-boot-starter"],
                "Ruby on Rails": ["rails"],
            },
            "database": {
                "SQLAlchemy": ["sqlalchemy"],
                "Prisma": ["prisma"],
                "PostgreSQL": ["psycopg2", "pg", "node-postgres"],
                "MySQL": ["mysqlclient", "mysql2", "pymysql"],
                "SQLite": ["sqlite3"],
                "MongoDB": ["pymongo", "mongoose"],
                "Redis": ["redis", "ioredis"],
            },
             "testing": {
                "Pytest": ["pytest"],
                "Jest": ["jest"],
                "Mocha": ["mocha"],
                "JUnit": ["junit"],
                "Selenium": ["selenium"],
            },
            "devops": {
                "AWS": ["boto3", "aws-sdk"],
                "GCP": ["google-cloud"],
                "Azure": ["azure"],
                "Terraform": ["terraform"], # Less likely in deps, more file-based
            }
        }
        
        for category, patterns in technology_patterns.items():
            for tech, keywords in patterns.items():
                # Check for exact match or if package name starts with a keyword + hyphen
                if package_name in keywords or any(package_name.startswith(kw + '-') for kw in keywords):
                    tech_confidence[category][tech] += 1.0 # High confidence for dependency match
                    break # Move to next category once matched
    
    def create_directory_tree(self) -> Dict[str, Any]:
        """
        Create a hierarchical dictionary representing the directory structure.
        
        Returns:
            Nested dictionary representing the directory tree
        """
        files = self.scan_files()
        tree = {}
        
        for file_path in files:
            parts = file_path.split('/')
            node = tree
            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                if is_last:
                    # File node
                    node[part] = None 
                else:
                    # Directory node
                    if part not in node:
                        node[part] = {}
                    # Ensure we don't overwrite a file with a directory if paths conflict
                    if node[part] is None: 
                        node[part] = {} 
                    node = node[part]
        
        # Sort the tree alphabetically
        return self._sort_tree(tree)
            
    def create_markdown_tree(self, max_depth: int = 5) -> str:
        """
        Generate a Markdown representation of the directory tree.
        
        Args:
            max_depth: Maximum depth to traverse.
        
        Returns:
            Markdown formatted string of the directory tree
        """
        tree_dict = self.create_directory_tree()
        markdown_lines = [f"**{os.path.basename(self.repo_path)}/**"]

        def traverse_tree(node, prefix="", depth=0):
            if depth >= max_depth:
                markdown_lines.append(f"{prefix}- ... (max depth reached)")
                return
                
            # Sort items: directories first, then files
            items = sorted(node.items(), key=lambda item: (isinstance(item[1], dict), item[0]))
            
            for i, (name, value) in enumerate(items):
                connector = "    " * depth + "- "
                new_prefix = prefix + "    " 
                
                if isinstance(value, dict):
                    # Directory
                    markdown_lines.append(f"{connector}**{name}/**")
                    traverse_tree(value, new_prefix, depth + 1)
                else:
                    # File
                    markdown_lines.append(f"{connector}{name}")
                    
        traverse_tree(tree_dict)
        return "\n".join(markdown_lines)
    
    def create_tree(self, max_depth: int = 5) -> str:
        """
        Generate a visually enhanced text tree representation.
        
        Args:
            max_depth: Maximum depth to traverse.
        
        Returns:
            String containing the text tree representation
        """
        tree_dict = self.create_directory_tree()
        lines = [f"📁 {os.path.basename(self.repo_path)}/"]
        
        def traverse_tree(node, prefix="", is_last=True, indent_level=0):
            if indent_level >= max_depth:
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}... (max depth reached)")
                return
                
            # Sort items: directories first, then files
            items = sorted(node.items(), key=lambda item: (isinstance(item[1], dict), item[0]))
            
            count = len(items)
            for i, (name, value) in enumerate(items):
                current_is_last = i == count - 1
                connector = "└── " if current_is_last else "├── "
                line_prefix = prefix + connector
                new_prefix = prefix + ("    " if current_is_last else "│   ")

                if isinstance(value, dict):
                    # Directory: Use folder icon
                    lines.append(f"{line_prefix}📁 {name}/")
                    traverse_tree(value, new_prefix, current_is_last, indent_level + 1)
                else:
                    # File: Use document icon
                    lines.append(f"{line_prefix}📄 {name}")

        traverse_tree(tree_dict)
        return "\n".join(lines)
    
    def _sort_tree(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sort the directory tree dictionary.
        Directories come before files, then alphabetically.
        
        Args:
            tree: The directory tree dictionary
            
        Returns:
            Sorted directory tree dictionary
        """
        sorted_items = sorted(
            tree.items(), 
            key=lambda item: (isinstance(item[1], dict), item[0]) # Sort by type (dict first), then name
        )
        
        sorted_tree = {}
        for key, value in sorted_items:
            if isinstance(value, dict):
                sorted_tree[key] = self._sort_tree(value) # Recursively sort subdirectories
            else:
                sorted_tree[key] = value # Files remain as None
                
        return sorted_tree
    
    def get_file_extension_breakdown(self, file_list: List[str]) -> Dict[str, List[str]]:
        """
        Group files by their extensions.
        
        Args:
            file_list: List of file paths
            
        Returns:
            Dictionary where keys are extensions and values are lists of files
        """
        extension_map = defaultdict(list)
        for file_path in file_list:
            _, ext = os.path.splitext(file_path)
            if ext:
                extension_map[ext.lower()].append(file_path)
            else:
                # Handle files with no extension
                extension_map["no_extension"].append(file_path)
        
        # Sort files within each extension category
        for ext in extension_map:
            extension_map[ext].sort()
            
        return dict(sorted(extension_map.items()))
    
    def identify_modules(self, files: List[str]) -> Dict[str, List[str]]:
        """
        Identify potential code modules based on directory structure.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary where keys are potential module paths and values are lists of files
        """
        modules = defaultdict(list)
        
        # Identify potential module roots (directories containing __init__.py or package.json)
        module_roots = set()
        for file_path in files:
            dirname = os.path.dirname(file_path)
            filename = os.path.basename(file_path).lower()
            
            if filename == "__init__.py" or filename == "package.json":
                # Consider the directory containing these files as a module root
                module_roots.add(dirname)
            elif filename == "setup.py" or filename == "pyproject.toml":
                 # Consider the directory containing setup files as a potential root for the main package
                 module_roots.add(dirname if dirname else '.') # Use '.' for root
        
        # Group files by the identified module roots
        for file_path in files:
            found_module = False
            # Check from longest path to shortest to find the most specific module root
            sorted_roots = sorted(list(module_roots), key=len, reverse=True)
            
            for root in sorted_roots:
                # Handle root case '.' correctly
                check_path = root + '/' if root else ''
                if file_path.startswith(check_path) or root == '.':
                    module_key = root if root else "<root>"
                    modules[module_key].append(file_path)
                    found_module = True
                    break
            
            # If file doesn't belong to any identified module, add to a general category
            if not found_module:
                # Try to group by top-level directory for non-module files
                top_level_dir = file_path.split('/')[0] if '/' in file_path else "<root>"
                if top_level_dir != "<root>" and top_level_dir not in module_roots:
                     modules[f"<other>/{top_level_dir}"].append(file_path)
                else:
                     modules["<other>"].append(file_path)

        # Sort files within each module
        for key in modules:
            modules[key].sort()
            
        return dict(sorted(modules.items()))

    def analyze_languages(self, files: List[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Analyze language distribution based on file extensions.
        
        Args:
            files: List of file paths
            
        Returns:
            Tuple[Dict[str, int], Dict[str, int]]: 
                - Dictionary mapping language to file count
                - Dictionary mapping file extension to file count
        """
        extension_map = {
            # Code Languages
            ".py": "Python", ".pyw": "Python",
            ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript",
            ".java": "Java", ".jar": "Java",
            ".cs": "C#",
            ".cpp": "C++", ".cxx": "C++", ".cc": "C++", ".hpp": "C++", ".hxx": "C++", ".h": "C/C++ Header",
            ".c": "C",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin", ".kts": "Kotlin",
            ".go": "Go",
            ".rs": "Rust",
            ".scala": "Scala",
            ".pl": "Perl", ".pm": "Perl",
            ".lua": "Lua",
            ".r": "R",
            ".sh": "Shell Script", ".bash": "Shell Script", ".zsh": "Shell Script",
            ".ps1": "PowerShell",
            ".dart": "Dart",
            ".ex": "Elixir", ".exs": "Elixir",
            ".erl": "Erlang", ".hrl": "Erlang",
            ".hs": "Haskell", ".lhs": "Haskell",
            ".clj": "Clojure", ".cljs": "Clojure", ".cljc": "Clojure",
            ".groovy": "Groovy",
            ".vb": "Visual Basic",
            ".fs": "F#", ".fsx": "F#", ".fsi": "F#",
            # Markup & Data
            ".html": "HTML", ".htm": "HTML",
            ".css": "CSS",
            ".scss": "SCSS", ".sass": "SASS",
            ".less": "LESS",
            ".json": "JSON",
            ".xml": "XML",
            ".yaml": "YAML", ".yml": "YAML",
            ".toml": "TOML",
            ".md": "Markdown", ".markdown": "Markdown",
            ".rst": "reStructuredText",
            ".sql": "SQL",
            ".csv": "CSV",
            ".tsv": "TSV",
            # Config & Build
            ".ini": "INI Config",
            ".conf": "Config",
            ".cfg": "Config",
            ".properties": "Properties Config",
            "dockerfile": "Dockerfile",
            "docker-compose.yml": "Docker Compose", "docker-compose.yaml": "Docker Compose",
            ".tf": "Terraform", ".tfvars": "Terraform",
            "makefile": "Makefile",
            "cmakelists.txt": "CMake",
            "pom.xml": "Maven POM",
            "build.gradle": "Gradle Build", "build.gradle.kts": "Gradle Build",
            "package.json": "NPM Config",
            "composer.json": "Composer Config",
            "gemfile": "Gemfile",
            "requirements.txt": "Python Requirements",
            "pyproject.toml": "Python Project Config",
            "go.mod": "Go Modules", "go.sum": "Go Modules",
            ".csproj": "C# Project", ".vbproj": "VB Project", ".fsproj": "F# Project", ".sln": "VS Solution",
            # Other
            ".ipynb": "Jupyter Notebook",
            ".txt": "Text",
            ".log": "Log",
            ".pdf": "PDF",
            ".png": "Image", ".jpg": "Image", ".jpeg": "Image", ".gif": "Image", ".svg": "Image", ".ico": "Image",
            ".ttf": "Font", ".otf": "Font", ".woff": "Font", ".woff2": "Font",
            ".zip": "Archive", ".gz": "Archive", ".tar": "Archive", ".rar": "Archive",
            ".gitignore": "Git Ignore",
            ".gitattributes": "Git Attributes",
            "license": "License",
        }
        
        language_counts = Counter()
        extension_counts = Counter()
        
        for file_path in files:
            filename = os.path.basename(file_path).lower()
            _, ext = os.path.splitext(filename)

            # Handle specific filenames first
            if filename in extension_map:
                language = extension_map[filename]
                language_counts[language] += 1
                extension_counts[filename] += 1 # Use filename as extension key
            elif ext in extension_map:
                language = extension_map[ext]
                language_counts[language] += 1
                extension_counts[ext] += 1
            elif ext:
                language_counts["Other"] += 1
                extension_counts[ext] += 1
            else:
                 # Files with no extension
                 language_counts["Other"] += 1
                 extension_counts["no_extension"] += 1
                 
        # Sort by count descending
        sorted_languages = dict(sorted(language_counts.items(), key=lambda item: item[1], reverse=True))
        sorted_extensions = dict(sorted(extension_counts.items(), key=lambda item: item[1], reverse=True))
        
        return sorted_languages, sorted_extensions
    
    def analyze_repository(self) -> Dict[str, Any]:
        """
        Perform a comprehensive analysis of the repository.
        
        Returns:
            Dictionary containing files, languages, technologies, and structure
        """
        logger.info(f"Starting repository analysis for {self.repo_path}")
        files = self.scan_files()
        if not files:
            logger.warning("No files found to analyze.")
            return {
                "files": [],
                "languages": {},
                "technologies": {},
                "structure": {},
                "modules": {},
                "file_count": 0,
                "message": "No relevant files found in the repository."
            }
            
        languages, extensions = self.analyze_languages(files)
        technologies, api_frameworks = self.detect_frameworks()
        structure = self.create_directory_tree()
        modules = self.identify_modules(files)
        
        analysis = {
            "files": files,
            "languages": languages,
            "extensions": extensions,
            "technologies": technologies,
            "api_frameworks": sorted(list(api_frameworks)), # Add identified API frameworks
            "structure": structure,
            "modules": modules,
            "file_count": len(files),
            "message": f"Analysis complete. Found {len(files)} files."
        }
        logger.info(f"Repository analysis complete. Found {len(files)} files.")
        return analysis 

    def identify_api_components(self) -> Dict[str, List[str]]:
        """
        Identify API components (entry points, routers, handlers, schemas) 
        using framework-specific patterns and conventions.
        
        Returns:
            Dictionary with categorized API component file paths.
        """
        files = self.scan_files()
        _, detected_api_frameworks = self.detect_frameworks()
        
        # If multiple frameworks are detected, prioritize (e.g., based on common setups)
        # For MVP, we might focus on the first detected or a specific one like FastAPI
        primary_framework = None
        if detected_api_frameworks:
            preferred_order = ["fastapi", "flask", "django_rest_framework", "express", "nestjs", "spring_boot"]
            for fw in preferred_order:
                if fw in detected_api_frameworks:
                    primary_framework = fw
                    break
            if not primary_framework:
                primary_framework = list(detected_api_frameworks)[0] # Fallback
        
        logger.info(f"Identifying API components, primary framework detected: {primary_framework}")

        # Define patterns (can be expanded significantly)
        common_patterns = {
            "entry_points": ["app.py", "main.py", "server.py", "api.py", "application.py", "index.js", "server.js", "main.ts", "Application.java"],
            "routers": ["route", "router", "urls.py", "endpoint", "controller", "resource", "view"], # Keywords in path or filename
            "schemas": ["schema", "model", "dto", "type", "interface", "entity"], # Keywords in path or filename
            "handlers": ["handler", "service", "manager"], # Keywords in path or filename
            "config": ["config", "setting", "env", "constant"],
            "tests": ["test", "spec", "e2e"],
        }

        framework_specific_patterns = {
            "fastapi": {
                "routers": ["APIRouter", "@router.", "@app."], # Content patterns
                "schemas": ["BaseModel", "pydantic"], # Content patterns
            },
            "flask": {
                "routers": ["Blueprint", "@app.route", "@blueprint.route"],
            },
            "django_rest_framework": {
                "routers": ["APIView", "ViewSet", "urls.py", "path(", "re_path("],
                "schemas": ["Serializer"],
            },
            "express": {
                "routers": ["express.Router()", "app.get(", "app.post(", "router.get(", "router.use("],
            },
            "nestjs": {
                "routers": ["@Controller", "@Get", "@Post"],
                "schemas": ["@InputType", "@ObjectType", "interface", "class "], # Less specific, relies on path
                "handlers": ["@Injectable", "Service"] 
            },
            "spring_boot": {
                "entry_points": ["@SpringBootApplication"],
                "routers": ["@RestController", "@RequestMapping", "@GetMapping", "@PostMapping"],
                "schemas": ["@Entity", "@Data", "DTO"], # Check filenames/paths more heavily
                "handlers": ["@Service"],
            },
            # Add more frameworks as needed
        }

        api_components = defaultdict(list)
        processed_files = set() # Avoid double-categorizing

        # 1. Identify Entry Points (more reliable with content checks)
        for file_path in files:
            filename = os.path.basename(file_path).lower()
            if filename in common_patterns["entry_points"]:
                 api_components["entry_points"].append(file_path)
                 processed_files.add(file_path)
                 continue # Often entry points also match router patterns
            
            # Framework specific content check for entry points
            if primary_framework in framework_specific_patterns:
                 patterns = framework_specific_patterns[primary_framework]
                 if "entry_points" in patterns:
                     try:
                         full_path = os.path.join(self.repo_path, file_path)
                         if os.path.getsize(full_path) < 50 * 1024: # Limit size
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                 content_sample = f.read(5000) # Read start of file
                            if any(p.lower() in content_sample.lower() for p in patterns["entry_points"]):
                                 api_components["entry_points"].append(file_path)
                                 processed_files.add(file_path)
                                 continue
                     except Exception:
                         pass # Ignore read errors

        # 2. Identify Routers/Controllers/Views (highest priority after entry points)
        for file_path in files:
            if file_path in processed_files: continue
            
            matched = False
            # Check common path/filename patterns
            if any(p in file_path.lower() for p in common_patterns["routers"]):
                 api_components["routers"].append(file_path)
                 processed_files.add(file_path)
                 matched = True
                 continue
            
            # Check framework-specific content patterns
            if primary_framework in framework_specific_patterns:
                 patterns = framework_specific_patterns[primary_framework]
                 if "routers" in patterns:
                     try:
                         full_path = os.path.join(self.repo_path, file_path)
                         # Only read content if file type is relevant
                         if os.path.splitext(file_path)[1].lower() in [".py", ".js", ".ts", ".java"]:
                            if os.path.getsize(full_path) < 100 * 1024: # Limit size
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content_sample = f.read(10000) # Read start of file
                                if any(p.lower() in content_sample.lower() for p in patterns["routers"]):
                                    api_components["routers"].append(file_path)
                                    processed_files.add(file_path)
                                    matched = True
                                    continue
                     except Exception:
                         pass 

        # 3. Identify Schemas/Models/DTOs
        for file_path in files:
            if file_path in processed_files: continue
            matched = False
            # Check common path/filename patterns
            if any(p in file_path.lower() for p in common_patterns["schemas"]):
                 api_components["schemas"].append(file_path)
                 processed_files.add(file_path)
                 matched = True
                 continue
            
            # Check framework-specific content patterns (less reliable for schemas, often just classes)
            if primary_framework in framework_specific_patterns:
                 patterns = framework_specific_patterns[primary_framework]
                 if "schemas" in patterns:
                     try:
                         full_path = os.path.join(self.repo_path, file_path)
                         if os.path.splitext(file_path)[1].lower() in [".py", ".js", ".ts", ".java"]:
                             if os.path.getsize(full_path) < 50 * 1024:
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content_sample = f.read(5000) 
                                if any(p.lower() in content_sample.lower() for p in patterns["schemas"]):
                                    api_components["schemas"].append(file_path)
                                    processed_files.add(file_path)
                                    matched = True
                                    continue
                     except Exception:
                         pass

        # 4. Identify Handlers/Services (often business logic called by routers)
        for file_path in files:
            if file_path in processed_files: continue
            matched = False
            if any(p in file_path.lower() for p in common_patterns["handlers"]):
                 api_components["handlers"].append(file_path)
                 processed_files.add(file_path)
                 matched = True
                 continue
             # Optional: Add framework-specific content checks if useful
            if primary_framework in framework_specific_patterns:
                 patterns = framework_specific_patterns[primary_framework]
                 if "handlers" in patterns:
                    try:
                         full_path = os.path.join(self.repo_path, file_path)
                         if os.path.splitext(file_path)[1].lower() in [".py", ".js", ".ts", ".java"]:
                             if os.path.getsize(full_path) < 100 * 1024:
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content_sample = f.read(10000) 
                                if any(p.lower() in content_sample.lower() for p in patterns["handlers"]):
                                    api_components["handlers"].append(file_path)
                                    processed_files.add(file_path)
                                    matched = True
                                    continue
                    except Exception:
                         pass

        # 5. Identify Config files (potentially relevant for base URLs, auth)
        for file_path in files:
            if file_path in processed_files: continue
            if any(p in file_path.lower() for p in common_patterns["config"]):
                 api_components["config"].append(file_path)
                 processed_files.add(file_path)
                 continue
                
        # 6. Identify Test files (useful for understanding usage)
        for file_path in files:
            if file_path in processed_files: continue
            if any(p in file_path.lower() for p in common_patterns["tests"]):
                 api_components["tests"].append(file_path)
                 processed_files.add(file_path)
                 continue

        # Sort results
        for key in api_components:
            api_components[key].sort()
            
        logger.info(f"Identified API components: { {k: len(v) for k, v in api_components.items()} }")
        return dict(api_components) 