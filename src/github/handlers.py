import logging
from typing import Dict, Any, List
import os

from src.agents import (
    DocGenerator, 
    CodeAnalyzer, 
    QualityChecker, 
    DocGeneratorInput, 
    AgentConfig,
    RepoAnalyzer,
    RepoStructureInput,
    APIDocGenerator,
    APIDocInput,
    ReadmeGenerator,
    ReadmeInput
)
from src.utils.repo_scanner import RepoScanner

logger = logging.getLogger(__name__)

async def handle_push_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub push events
    
    When code is pushed, analyze changes and update relevant documentation
    """
    try:
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        ref = payload.get("ref", "")
        commits = payload.get("commits", [])
        
        logger.info(f"Processing push to {repo_name} on {ref} with {len(commits)} commits")
        
        # Skip empty pushes or non-main branch pushes (configurable)
        if not commits or "refs/heads/main" not in ref and "refs/heads/master" not in ref:
            return {"status": "skipped", "reason": "No commits or not on main branch"}
            
        # Get the files that were modified
        modified_files = []
        for commit in commits:
            modified_files.extend(commit.get("added", []))
            modified_files.extend(commit.get("modified", []))
        
        # Remove duplicates
        modified_files = list(set(modified_files))
        
        # Check if we should analyze the entire repository
        should_analyze_repo = any([
            # README changes
            f for f in modified_files if f.lower().endswith('readme.md')
        ]) or len(modified_files) > 10  # Many files changed
        
        results = {}
        
        if should_analyze_repo:
            # Analyze repository structure for better context
            logger.info(f"Analyzing repository structure for {repo_name}")
            results["repo_analysis"] = await analyze_repository_structure(repo_name, ref.replace("refs/heads/", ""))
        
        # Check for API-specific files
        api_files = [f for f in modified_files if _is_api_file(f)]
        if api_files:
            logger.info(f"Processing API files: {api_files}")
            results["api_docs"] = await process_api_files(repo_name, ref.replace("refs/heads/", ""), api_files)
        
        # Generate documentation for modified files
        doc_generator = DocGenerator()
        doc_results = await doc_generator.process_file_changes(
            repo_name=repo_name,
            branch=ref.replace("refs/heads/", ""),
            file_paths=modified_files
        )
        results["documentation_updated"] = doc_results
        
        return {
            "status": "success",
            "repository": repo_name,
            "branch": ref,
            "processed_files": len(modified_files),
            "results": results
        }
    
    except Exception as e:
        logger.exception(f"Error processing push event: {str(e)}")
        return {"status": "error", "message": str(e)}

async def handle_pull_request_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub pull request events
    
    When a PR is opened or updated, analyze changes and suggest 
    documentation updates as comments
    """
    try:
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        
        # Only process opened or synchronized PRs
        if action not in ["opened", "synchronize"]:
            return {"status": "skipped", "reason": f"PR action {action} not relevant"}
            
        repo_name = repo.get("full_name")
        pr_number = pr.get("number")
        head_sha = pr.get("head", {}).get("sha")
        
        logger.info(f"Processing PR #{pr_number} in {repo_name}")
        
        # Analyze PR content to understand the changes better
        changed_files = pr.get("changed_files", 0)
        
        results = {}
        
        # For larger PRs, perform a repository structure analysis
        if changed_files > 5:
            logger.info(f"Large PR detected ({changed_files} files), analyzing repository structure")
            results["repo_analysis"] = await analyze_repository_structure(
                repo_name, 
                pr.get("head", {}).get("ref", "")
            )
        
        # Check if PR includes API changes
        if pr.get("title", "").lower().find("api") >= 0 or pr.get("body", "").lower().find("api") >= 0:
            logger.info("API changes detected in PR, generating API documentation")
            # Get files from PR
            # Note: In a real implementation, you would fetch the PR files using the GitHub API
            api_files = []  # This would be populated with actual files
            results["api_docs"] = await process_api_files(
                repo_name, 
                pr.get("head", {}).get("ref", ""),
                api_files
            )
        
        # Generate documentation suggestions for the PR
        doc_generator = DocGenerator()
        suggestions = await doc_generator.process_pull_request(
            repo_name=repo_name,
            pr_number=pr_number,
            head_sha=head_sha
        )
        results["documentation_suggestions"] = suggestions
        
        return {
            "status": "success",
            "repository": repo_name,
            "pr_number": pr_number,
            "results": results
        }
    
    except Exception as e:
        logger.exception(f"Error processing PR event: {str(e)}")
        return {"status": "error", "message": str(e)}

async def handle_issues_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub issues events
    
    When issues related to documentation are created or modified,
    suggest documentation improvements
    """
    try:
        action = payload.get("action")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        
        # Only process newly opened issues or ones with the "documentation" label
        labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
        if action != "opened" and "documentation" not in labels:
            return {"status": "skipped", "reason": "Not a documentation issue"}
            
        repo_name = repo.get("full_name")
        issue_number = issue.get("number")
        
        logger.info(f"Processing documentation issue #{issue_number} in {repo_name}")
        
        results = {}
        
        # For documentation-related issues, analyze repo structure
        if "documentation" in labels or issue.get("title", "").lower().find("doc") >= 0:
            logger.info("Documentation issue detected, analyzing repository structure")
            results["repo_analysis"] = await analyze_repository_structure(repo_name, "main")
            
            # Check if issue is specifically about README
            if issue.get("title", "").lower().find("readme") >= 0 or issue.get("body", "").lower().find("readme") >= 0:
                logger.info("README issue detected, generating improved README")
                results["readme"] = await generate_readme(repo_name, results["repo_analysis"])
            
            # Check if issue is about API documentation
            if issue.get("title", "").lower().find("api") >= 0 or issue.get("body", "").lower().find("api doc") >= 0:
                logger.info("API documentation issue detected")
                # In a real implementation, you would identify API files here
                api_files = []  # This would be populated with actual files
                results["api_docs"] = await process_api_files(repo_name, "main", api_files)
        
        # Process documentation issue
        doc_generator = DocGenerator()
        response = await doc_generator.process_documentation_issue(
            repo_name=repo_name,
            issue_number=issue_number,
            issue_title=issue.get("title", ""),
            issue_body=issue.get("body", "")
        )
        results["response"] = response
        
        return {
            "status": "success",
            "repository": repo_name,
            "issue_number": issue_number,
            "results": results
        }
    
    except Exception as e:
        logger.exception(f"Error processing issue event: {str(e)}")
        return {"status": "error", "message": str(e)}

async def analyze_repository_structure(repo_name: str, branch: str) -> Dict[str, Any]:
    """
    Analyze repository structure to provide context for documentation
    
    Args:
        repo_name: Full repository name
        branch: Branch name
        
    Returns:
        Analysis results
    """
    logger.info(f"Analyzing repository structure for {repo_name} on {branch}")
    
    try:
        # In a real implementation, you would clone the repository or use GitHub API
        # to get the files. For this example, we'll simulate it.
        
        # Initialize repo scanner and agents
        # Note: In a real implementation, this would use a temporary directory with cloned repo
        repo_scanner = RepoScanner("/tmp/repo")
        file_list = repo_scanner.scan_files()
        
        # Initialize repository analyzer
        repo_analyzer = RepoAnalyzer()
        
        # Analyze repository structure
        result = await repo_analyzer.analyze_repo_structure(
            RepoStructureInput(
                repo_path=repo_name,
                files=file_list
            )
        )
        
        # Generate markdown summary
        markdown_summary = await repo_analyzer.generate_markdown_summary(result)
        
        # Identify documentation needs
        doc_needs = await repo_analyzer.identify_documentation_needs(result)
        
        return {
            "summary": result.summary,
            "technologies": result.technologies,
            "architecture": result.architecture_pattern,
            "components": [
                {"name": comp.name, "description": comp.description}
                for comp in result.components
            ],
            "documentation_needs": doc_needs,
            "markdown_summary": markdown_summary.content
        }
    
    except Exception as e:
        logger.exception(f"Error analyzing repository structure: {str(e)}")
        return {"error": str(e)}

async def process_api_files(repo_name: str, branch: str, file_paths: List[str]) -> Dict[str, Any]:
    """
    Process API files to generate API documentation
    
    Args:
        repo_name: Full repository name
        branch: Branch name
        file_paths: List of files to process
        
    Returns:
        API documentation results
    """
    logger.info(f"Processing API files for {repo_name} on {branch}: {file_paths}")
    
    try:
        results = {}
        api_doc_generator = APIDocGenerator()
        
        if not file_paths:
            return {"status": "skipped", "reason": "No API files provided"}
            
        # In a real implementation, you would get actual file content from GitHub
        # For this example, we'll use a simplified approach
        api_file_contents = []
        for file_path in file_paths:
            # Simulate getting file content
            file_content = "# Placeholder API content"
            api_file_contents.append((file_path, file_content))
        
        # Determine the language and framework based on first file extension
        language, framework = _detect_language_and_framework(file_paths[0])
        
        # Get repository description as a placeholder
        repo_description = f"API documentation for {repo_name}"
        
        api_doc_result = await api_doc_generator.generate_api_docs(
            APIDocInput(
                code=api_file_contents[0][1],  # Use first file content as main code
                api_name=f"{repo_name} API",
                language=language,
                framework=framework,
                api_files=api_file_contents,
                project_description=repo_description
            )
        )
        
        results = {
            "title": api_doc_result.title,
            "version": api_doc_result.version,
            "description": api_doc_result.description,
            "endpoints": len(api_doc_result.endpoints),
            "markdown": api_doc_result.markdown
        }
            
        return results
    
    except Exception as e:
        logger.exception(f"Error processing API files: {str(e)}")
        return {"error": str(e)}

async def generate_readme(repo_name: str, repo_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate or update README based on repository analysis
    
    Args:
        repo_name: Full repository name
        repo_analysis: Repository analysis results
        
    Returns:
        README generation results
    """
    logger.info(f"Generating README for {repo_name}")
    
    try:
        # Initialize README generator
        readme_generator = ReadmeGenerator()
        
        # Convert repo_analysis dict to RepoStructureResult
        # In a real implementation, you would use a proper RepoStructureResult object
        
        # Check if README already exists
        # In a real implementation, you would check if README exists in the repository
        existing_readme = None
        
        if existing_readme:
            # Update existing README
            result = await readme_generator.update_readme(
                ReadmeInput(
                    repo_name=repo_name,
                    repo_description=repo_analysis.get("summary", ""),
                    # repo_structure would be a proper RepoStructureResult in real implementation
                    existing_readme=existing_readme
                )
            )
            action = "updated"
        else:
            # Generate new README
            result = await readme_generator.generate_readme(
                ReadmeInput(
                    repo_name=repo_name,
                    repo_description=repo_analysis.get("summary", "")
                    # repo_structure would be a proper RepoStructureResult in real implementation
                )
            )
            action = "created"
        
        return {
            "action": action,
            "title": result.title,
            "sections": len(result.sections),
            "markdown": result.markdown
        }
    
    except Exception as e:
        logger.exception(f"Error generating README: {str(e)}")
        return {"error": str(e)}

def _is_api_file(file_path: str) -> bool:
    """
    Check if a file is likely to contain API definitions
    
    Args:
        file_path: File path
        
    Returns:
        True if the file is likely an API file, False otherwise
    """
    # Common API file patterns
    api_patterns = [
        "api", "controller", "route", "endpoint", "rest", "http",
        "service", "resource", "graphql", "swagger", "openapi"
    ]
    
    file_path_lower = file_path.lower()
    
    # Check extension first - common API file extensions
    _, ext = os.path.splitext(file_path_lower)
    if ext in ['.py', '.js', '.ts', '.go', '.java', '.rb', '.php']:
        # Check if filename contains API-related terms
        filename = os.path.basename(file_path_lower)
        return any(pattern in filename for pattern in api_patterns)
    
    # Check for OpenAPI/Swagger files
    if ext in ['.json', '.yaml', '.yml'] and (
        'swagger' in file_path_lower or 
        'openapi' in file_path_lower or
        'api' in file_path_lower
    ):
        return True
        
    return False

def _detect_language_and_framework(file_path: str) -> tuple:
    """
    Detect language and framework based on file path
    
    Args:
        file_path: File path
        
    Returns:
        Tuple of (language, framework)
    """
    ext_to_language = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.go': 'go',
        '.java': 'java',
        '.rb': 'ruby',
        '.php': 'php',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
    }
    
    path_to_framework = {
        'flask': 'Flask',
        'django': 'Django',
        'fastapi': 'FastAPI',
        'express': 'Express',
        'spring': 'Spring',
        'rails': 'Rails',
        'laravel': 'Laravel',
        'swagger': 'OpenAPI',
        'openapi': 'OpenAPI',
    }
    
    _, ext = os.path.splitext(file_path.lower())
    language = ext_to_language.get(ext, 'unknown')
    
    framework = None
    for fw_name, fw in path_to_framework.items():
        if fw_name in file_path.lower():
            framework = fw
            break
    
    return language, framework 