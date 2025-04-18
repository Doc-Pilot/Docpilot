import os
import base64
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import requests
import github
from github import Github, GithubIntegration
from github.GithubException import GithubException

from ..utils.config import get_settings
from ..utils.logging import core_logger
from .installation_store import InstallationStore

logger = core_logger()

class GitHubClient:
    """
    Client for interacting with GitHub API
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.installation_store = InstallationStore()
        self._init_github_client()
        
    def _init_github_client(self):
        """Initialize GitHub client based on available credentials"""
        try:
            # If GitHub App credentials are available, use GitHub App authentication
            if self.settings.github_app_id and self.settings.github_private_key_path:
                with open(self.settings.github_private_key_path, 'r') as key_file:
                    private_key = key_file.read()
                    
                integration = GithubIntegration(
                    self.settings.github_app_id,
                    private_key
                )
                self.github_app = integration
                self.github = None  # Will be initialized per-repo
                logger.info(f"Initialized GitHub App client with App ID: {self.settings.github_app_id}")
            else:
                # Fallback to personal access token if available in environment
                github_token = self.settings.github_token or os.getenv("GITHUB_TOKEN")
                if not github_token:
                    raise ValueError("No GitHub authentication credentials available")
                    
                self.github = Github(github_token)
                self.github_app = None
                logger.info("Initialized GitHub client with personal access token")
                
        except Exception as e:
            logger.exception(f"Error initializing GitHub client: {str(e)}", exc_info=True)
            raise
    
    async def get_github_client_for_repo(self, repo_name: str) -> Github:
        """
        Get GitHub client for a specific repository
        
        When using GitHub App authentication, we need to get an installation token
        for the specific repository.
        
        Args:
            repo_name: Full repository name (owner/repo)
            
        Returns:
            Github client instance
        """
        if self.github:
            # Already have a client with Personal Access Token
            return self.github
            
        if not self.github_app:
            logger.error("No GitHub authentication available")
            raise ValueError("No GitHub authentication available")
            
        try:
            # Extract owner and repo name
            owner, repo = repo_name.split('/')
            
            # Try to find an existing installation with valid token
            installation = await self.installation_store.find_installation_for_repo(owner, repo)
            
            if installation:
                # Check if we have a valid token for this installation
                installation_id = installation["installation_id"]
                token = await self.installation_store.get_valid_token(installation_id)
                
                if token:
                    logger.debug(f"Using cached token for installation {installation_id}")
                    return Github(token)
            
            # No valid token found, need to get a new one
            logger.debug(f"Getting fresh installation token for {repo_name}")
            
            # Get the GitHub App installation for this repository
            try:
                installation_id = self.github_app.get_installation(owner, repo).id
            except Exception as e:
                logger.exception(f"Error getting installation for {repo_name}: {str(e)}", exc_info=True)
                raise ValueError(f"No GitHub App installation found for {repo_name}")
            
            # Create an access token for this installation
            token_data = self.github_app.get_access_token(installation_id)
            access_token = token_data.token
            
            # Parse expiration time
            # The token usually expires in 1 hour
            expires_at = datetime.now() + timedelta(seconds=3600)
            
            # Store the token in our installation store
            await self.installation_store.update_token(
                installation_id=str(installation_id),
                access_token=access_token,
                expires_at=expires_at
            )
            
            # Create a Github instance with this token
            return Github(access_token)
        except Exception as e:
            logger.exception(f"Error getting GitHub client for {repo_name}: {str(e)}", exc_info=True)
            raise
    
    async def refresh_installation_repositories(self, installation_id: str) -> List[str]:
        """
        Refresh the list of repositories for an installation
        
        Args:
            installation_id: Installation ID
            
        Returns:
            List of repository full names
        """
        if not self.github_app:
            logger.error("GitHub App authentication not configured")
            raise ValueError("GitHub App authentication not configured")
            
        try:
            # Get installation info from GitHub
            token_data = self.github_app.get_access_token(int(installation_id))
            gh_client = Github(token_data.token)
            
            # Get installation
            installation = gh_client.get_app_installation(int(installation_id))
            
            # Get account info
            account = installation.account
            account_name = account.login
            account_type = account.type
            
            # Get repositories
            repositories = []
            for repo in installation.get_repos():
                repositories.append(repo.full_name)
                
            # Update installation data
            await self.installation_store.add_installation(
                installation_id=installation_id,
                account_name=account_name,
                account_type=account_type,
                repositories=repositories,
                access_token=token_data.token,
                token_expires_at=datetime.now() + timedelta(seconds=3600)
            )
            
            return repositories
        except Exception as e:
            logger.exception(f"Error refreshing repositories for installation {installation_id}: {str(e)}", exc_info=True)
            raise
    
    async def get_file_content(
        self,
        repo_name: str,
        file_path: str,
        branch: str = "main"
    ) -> Optional[str]:
        """
        Get content of a file from GitHub repository
        
        Args:
            repo_name: Full repository name (owner/repo)
            file_path: Path to the file
            branch: Branch name
            
        Returns:
            File content as string or None if file not found
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            
            # Get file content
            file_content = repo.get_contents(file_path, ref=branch)
            
            # Handle single file or directory
            if isinstance(file_content, list):
                logger.warning(f"{file_path} is a directory, not a file")
                return None
                
            # Decode content from base64
            content = base64.b64decode(file_content.content).decode('utf-8')
            return content
            
        except GithubException as e:
            if e.status == 404:
                logger.info(f"File {file_path} not found in {repo_name}")
            else:
                logger.exception(f"GitHub error getting {file_path} from {repo_name}: {str(e)}", exc_info=True)
            return None
            
        except Exception as e:
            logger.exception(f"Error getting file content: {str(e)}", exc_info=True)
            return None
    
    async def update_documentation(
        self,
        repo_name: str,
        branch: str,
        doc_location: str,
        documentation: str,
        source_file: str
    ) -> Dict[str, Any]:
        """
        Update documentation in repository
        
        Handles both:
        - Updating inline documentation in source code
        - Creating/updating standalone documentation files
        
        Args:
            repo_name: Full repository name (owner/repo)
            branch: Branch name
            doc_location: Path where documentation should be stored
            documentation: Documentation content
            source_file: Source file that documentation is for
            
        Returns:
            Result of update operation
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            
            # Check if doc_location is same as source_file (inline documentation)
            if doc_location == source_file:
                return await self._update_inline_documentation(
                    repo, branch, source_file, documentation
                )
            else:
                return await self._update_standalone_documentation(
                    repo, branch, doc_location, documentation, source_file
                )
                
        except Exception as e:
            logger.exception(f"Error preparing documentation update: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error preparing documentation update: {str(e)}"}
    
    async def _update_inline_documentation(
        self,
        repo: github.Repository.Repository,
        branch: str,
        file_path: str,
        documentation: str
    ) -> Dict[str, Any]:
        """
        Update inline documentation in source code
        
        Args:
            repo: GitHub repository object
            branch: Branch name
            file_path: Path to the source file
            documentation: Documentation content
            
        Returns:
            Result of update operation
        """
        try:
            # Get current file content
            file_content = repo.get_contents(file_path, ref=branch)
            current_content = base64.b64decode(file_content.content).decode('utf-8')
            
            # This would require a more sophisticated algorithm to merge documentation
            # into the existing code. For demonstration, we're just appending it.
            # In a real implementation, you would parse the code and insert documentation
            # at appropriate locations.
            
            # For now, we'll create a pull request with the suggested documentation
            # rather than directly modifying the file
            
            # Create a new branch for the documentation update
            new_branch = f"docpilot/update-{file_path.replace('/', '-')}"
            
            try:
                # Get the reference to the base branch
                base_ref = repo.get_git_ref(f"heads/{branch}")
                base_sha = base_ref.object.sha
                
                # Create new branch
                repo.create_git_ref(f"refs/heads/{new_branch}", base_sha)
            except GithubException as e:
                if e.status == 422:  # Branch already exists
                    logger.info(f"Branch {new_branch} already exists")
                else:
                    raise
            
            # Create commit message
            commit_message = f"📝 Add documentation for {file_path}"
            
            # Create file update content - for demo, we're adding suggested documentation as a comment
            # In a real implementation, you would properly integrate it into the code
            updated_content = f"""
# Documentation suggestions from DocPilot:
{documentation}

{current_content}
"""
            
            # Update file in the new branch
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=updated_content,
                sha=file_content.sha,
                branch=new_branch
            )
            
            # Create pull request
            pr = repo.create_pull(
                title=f"📝 Update documentation for {file_path}",
                body=f"""
# 📝 Documentation Update

This PR adds documentation for `{file_path}` generated by DocPilot.

Please review these documentation updates and adjust as needed.

## Documentation Generated

```
{documentation}
```
                """,
                head=new_branch,
                base=branch
            )
            
            return {
                "status": "success",
                "type": "pull_request",
                "pr_number": pr.number,
                "pr_url": pr.html_url
            }
            
        except GithubException as e:
            logger.exception(f"GitHub error updating inline docs: {str(e)}", exc_info=True)
            return {"success": False, "error": f"GitHub error: {str(e)}"}
        except Exception as e:
            logger.exception(f"Error updating inline documentation: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    async def _update_standalone_documentation(
        self,
        repo: github.Repository.Repository,
        branch: str,
        doc_location: str,
        documentation: str,
        source_file: str
    ) -> Dict[str, Any]:
        """
        Update standalone documentation file
        
        Args:
            repo: GitHub repository object
            branch: Branch name
            doc_location: Path to the documentation file
            documentation: Documentation content
            source_file: Source file that documentation is for
            
        Returns:
            Result of update operation
        """
        try:
            # Check if documentation file exists
            try:
                file_content = repo.get_contents(doc_location, ref=branch)
                exists = True
                current_content = base64.b64decode(file_content.content).decode('utf-8')
                file_sha = file_content.sha
            except GithubException as e:
                if e.status == 404:
                    exists = False
                    current_content = ""
                    file_sha = None
                else:
                    raise
            
            # Create a new branch for the documentation update
            new_branch = f"docpilot/docs-{doc_location.replace('/', '-')}"
            
            try:
                # Get the reference to the base branch
                base_ref = repo.get_git_ref(f"heads/{branch}")
                base_sha = base_ref.object.sha
                
                # Create new branch
                repo.create_git_ref(f"refs/heads/{new_branch}", base_sha)
            except GithubException as e:
                if e.status == 422:  # Branch already exists
                    logger.info(f"Branch {new_branch} already exists")
                else:
                    raise
            
            # Create or update the documentation file
            if exists:
                # If file exists, ensure directory exists and update it
                commit_message = f"📝 Update documentation for {source_file}"
                result = repo.update_file(
                    path=doc_location,
                    message=commit_message,
                    content=documentation,
                    sha=file_sha,
                    branch=new_branch
                )
            else:
                # If file doesn't exist, create it (and possibly the directory)
                # First, ensure the directory exists
                directory = os.path.dirname(doc_location)
                if directory:
                    try:
                        repo.get_contents(directory, ref=branch)
                    except GithubException as e:
                        if e.status == 404:
                            # Create all parent directories
                            self._create_directory_structure(repo, directory, new_branch)
                        else:
                            raise
                
                # Now create the file
                commit_message = f"📝 Add documentation for {source_file}"
                result = repo.create_file(
                    path=doc_location,
                    message=commit_message,
                    content=documentation,
                    branch=new_branch
                )
            
            # Create pull request
            pr = repo.create_pull(
                title=f"📝 Update documentation for {source_file}",
                body=f"""
# 📝 Documentation Update

This PR adds/updates documentation for `{source_file}` in `{doc_location}` generated by DocPilot.

Please review these documentation updates and adjust as needed.
                """,
                head=new_branch,
                base=branch
            )
            
            return {
                "status": "success",
                "type": "pull_request",
                "pr_number": pr.number,
                "pr_url": pr.html_url
            }
            
        except GithubException as e:
            logger.exception(f"GitHub error updating standalone docs: {str(e)}", exc_info=True)
            return {"success": False, "error": f"GitHub error: {str(e)}"}
        except Exception as e:
            logger.exception(f"Error updating standalone documentation: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    def _create_directory_structure(
        self,
        repo: github.Repository.Repository,
        directory: str,
        branch: str
    ):
        """
        Create directory structure in repository
        
        Args:
            repo: GitHub repository object
            directory: Directory path to create
            branch: Branch name
        """
        # Split the path into components
        parts = directory.split('/')
        current_path = ""
        
        for part in parts:
            if not part:
                continue
                
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                repo.get_contents(current_path, ref=branch)
            except GithubException as e:
                if e.status == 404:
                    # Create empty file as a placeholder to create the directory
                    repo.create_file(
                        path=f"{current_path}/.gitkeep",
                        message=f"📁 Create directory {current_path}",
                        content="",
                        branch=branch
                    )
                else:
                    raise
        logger.info(f"Ensuring directory structure exists for {directory}")
    
    async def get_pr_changes(self, repo_name: str, pr_number: int) -> List[str]:
        """
        Get list of files changed in a pull request
        
        Args:
            repo_name: Full repository name (owner/repo)
            pr_number: Pull request number
            
        Returns:
            List of file paths changed in the PR
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            files = pr.get_files()
            return [file.filename for file in files]
            
        except Exception as e:
            logger.exception(f"Error getting PR changes: {str(e)}", exc_info=True)
            return []
    
    async def get_file_diff(
        self,
        repo_name: str,
        file_path: str,
        pr_number: int
    ) -> Optional[str]:
        """
        Get diff for a specific file in a pull request
        
        Args:
            repo_name: Full repository name (owner/repo)
            file_path: Path to the file
            pr_number: Pull request number
            
        Returns:
            File diff as string or None if not found
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            files = pr.get_files()
            for file in files:
                if file.filename == file_path:
                    return file.patch
                    
            return None
            
        except Exception as e:
            logger.exception(f"Error getting file diff: {str(e)}", exc_info=True)
            return None
    
    async def add_pr_comment(
        self,
        repo_name: str,
        pr_number: int,
        body: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add comment to a pull request
        
        Args:
            repo_name: Full repository name (owner/repo)
            pr_number: Pull request number
            body: Comment body
            file_path: Path to the file (for file-specific comments)
            
        Returns:
            Result of comment operation
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            if file_path:
                # For file-specific comments, prefix with file path
                prefix = f"## Documentation Suggestions for `{file_path}`\n\n"
                body = prefix + body
                
            comment = pr.create_issue_comment(body)
            
            return {
                "status": "success",
                "comment_id": comment.id,
                "comment_url": comment.html_url
            }
            
        except Exception as e:
            logger.exception(f"Error adding PR comment: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error adding PR comment: {str(e)}"}
    
    async def add_issue_comment(
        self,
        repo_name: str,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """
        Add comment to an issue
        
        Args:
            repo_name: Full repository name (owner/repo)
            issue_number: Issue number
            body: Comment body
            
        Returns:
            Result of comment operation
        """
        try:
            github_client = await self.get_github_client_for_repo(repo_name)
            repo = github_client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            comment = issue.create_comment(body)
            
            return {
                "status": "success",
                "comment_id": comment.id,
                "comment_url": comment.html_url
            }
            
        except Exception as e:
            logger.exception(f"Error adding issue comment: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error adding issue comment: {str(e)}"}
    
    async def suggest_documentation_update(
        self,
        repo_name: str,
        issue_number: int,
        doc_location: str,
        documentation: str,
        source_file: str
    ) -> Dict[str, Any]:
        """
        Suggest documentation update in response to an issue
        
        Args:
            repo_name: Full repository name (owner/repo)
            issue_number: Issue number
            doc_location: Path where documentation should be stored
            documentation: Documentation content
            source_file: Source file that documentation is for
            
        Returns:
            Result of suggestion operation
        """
        try:
            # For issue responses, just post a comment with the suggested documentation
            body = f"""
## 📝 Documentation Suggestion for `{source_file}`

Based on this issue, DocPilot has generated documentation for `{source_file}`.

### Suggested Documentation
```
{documentation}
```

### Implementation
To implement this documentation, it should be placed in `{doc_location}`.

Would you like DocPilot to create a pull request with this documentation update?
Reply with "👍" or "Yes, create PR" to proceed.
"""
            
            comment_result = await self.add_issue_comment(
                repo_name=repo_name,
                issue_number=issue_number,
                body=body
            )
            
            return {
                "status": "success",
                "suggestion_provided": True,
                "comment": comment_result
            }
            
        except Exception as e:
            logger.exception(f"Error suggesting documentation update: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error suggesting documentation update: {str(e)}"} 