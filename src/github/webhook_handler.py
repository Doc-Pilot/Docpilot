"""
GitHub Webhook Handler
=====================

Handles GitHub webhooks to trigger documentation update pipelines.
"""

import os
import json
import logging
import asyncio
import tempfile
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ..pipelines.doc_update_pipeline import DocumentationUpdatePipeline
from ..utils.logging import logger

class WebhookHandler:
    """
    Handles GitHub webhooks to trigger documentation update pipelines.
    
    This handler processes various GitHub webhook events, such as:
    - push: When code is pushed directly to a branch
    - pull_request: When a PR is opened, updated, or merged
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the webhook handler"""
        self.config = config or {}
        self.pipeline = DocumentationUpdatePipeline()
        
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a GitHub webhook event.
        
        Args:
            event_type: The type of event (e.g., "push", "pull_request")
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        logger.info(f"Handling GitHub webhook event: {event_type}")
        
        if event_type == "push":
            return await self.handle_push_event(payload)
        elif event_type == "pull_request":
            return await self.handle_pull_request_event(payload)
        else:
            logger.info(f"Ignoring unsupported event type: {event_type}")
            return {
                "success": True,
                "message": f"Event type {event_type} is not supported"
            }
    
    async def handle_push_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a push event.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        # Extract repository information
        repo_info = payload.get("repository", {})
        repo_name = repo_info.get("full_name", "")
        repo_url = repo_info.get("clone_url", "")
        
        # Extract push information
        ref = payload.get("ref", "")  # e.g., "refs/heads/main"
        branch = ref.replace("refs/heads/", "")
        
        # Base reference is the previous commit
        before_sha = payload.get("before", "")
        after_sha = payload.get("after", "")
        
        # Check if this is a branch creation or deletion
        if before_sha == "0000000000000000000000000000000000000000":
            logger.info(f"Branch creation detected for {branch}, skipping documentation update")
            return {
                "success": True,
                "message": f"Branch creation for {branch}, no documentation update needed"
            }
            
        if after_sha == "0000000000000000000000000000000000000000":
            logger.info(f"Branch deletion detected for {branch}, skipping documentation update")
            return {
                "success": True,
                "message": f"Branch deletion for {branch}, no documentation update needed"
            }
        
        # Check if it's a protected branch that should trigger documentation updates
        if not self._should_process_branch(branch):
            logger.info(f"Ignoring push to non-protected branch: {branch}")
            return {
                "success": True,
                "message": f"Branch {branch} is not configured for automatic documentation updates"
            }
            
        # Clone the repository to a temporary directory
        repo_dir, success, error = await self._clone_repository(repo_url)
        if not success:
            return {
                "success": False,
                "error": f"Failed to clone repository: {error}"
            }
            
        try:
            # Run the documentation update pipeline
            result = await self.pipeline.run_pipeline(
                repo_path=repo_dir,
                base_ref=before_sha,
                target_ref=after_sha,
                create_pr=True
            )
            
            # Clean up the temporary directory
            self._cleanup_repository(repo_dir)
            
            return result
        except Exception as e:
            logger.error(f"Error processing push event: {str(e)}")
            
            # Clean up the temporary directory
            self._cleanup_repository(repo_dir)
            
            return {
                "success": False,
                "error": f"Failed to process push event: {str(e)}"
            }
    
    async def handle_pull_request_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a pull request event.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        # Extract repository information
        repo_info = payload.get("repository", {})
        repo_name = repo_info.get("full_name", "")
        repo_url = repo_info.get("clone_url", "")
        
        # Extract PR information
        pr_info = payload.get("pull_request", {})
        pr_number = pr_info.get("number", 0)
        pr_action = payload.get("action", "")
        
        # Check if this is a PR merge
        if pr_action != "closed" or not pr_info.get("merged", False):
            logger.info(f"Ignoring PR {pr_number} {pr_action} action, not a merge")
            return {
                "success": True,
                "message": f"PR {pr_number} {pr_action} action, not a merge"
            }
            
        # Extract branch information
        base_branch = pr_info.get("base", {}).get("ref", "")
        head_branch = pr_info.get("head", {}).get("ref", "")
        
        # Check if it's a PR to a protected branch that should trigger documentation updates
        if not self._should_process_branch(base_branch):
            logger.info(f"Ignoring PR merge to non-protected branch: {base_branch}")
            return {
                "success": True,
                "message": f"Branch {base_branch} is not configured for automatic documentation updates"
            }
            
        # Get the merge commit SHA
        merge_commit_sha = pr_info.get("merge_commit_sha", "")
        
        # Clone the repository to a temporary directory
        repo_dir, success, error = await self._clone_repository(repo_url)
        if not success:
            return {
                "success": False,
                "error": f"Failed to clone repository: {error}"
            }
            
        try:
            # Run the documentation update pipeline
            result = await self.pipeline.run_pipeline(
                repo_path=repo_dir,
                base_ref=f"{merge_commit_sha}~1",
                target_ref=merge_commit_sha,
                create_pr=True
            )
            
            # Clean up the temporary directory
            self._cleanup_repository(repo_dir)
            
            return result
        except Exception as e:
            logger.error(f"Error processing PR merge event: {str(e)}")
            
            # Clean up the temporary directory
            self._cleanup_repository(repo_dir)
            
            return {
                "success": False,
                "error": f"Failed to process PR merge event: {str(e)}"
            }
    
    def _should_process_branch(self, branch: str) -> bool:
        """
        Check if a branch should trigger documentation updates.
        
        Args:
            branch: The branch name
            
        Returns:
            True if the branch should be processed, False otherwise
        """
        # List of branches that should trigger documentation updates
        protected_branches = self.config.get("protected_branches", ["main", "master"])
        
        return branch in protected_branches
    
    async def _clone_repository(self, repo_url: str) -> Tuple[str, bool, Optional[str]]:
        """
        Clone a repository to a temporary directory.
        
        Args:
            repo_url: The URL of the repository to clone
            
        Returns:
            Tuple of (repo_dir, success, error)
        """
        # Create a temporary directory
        repo_dir = tempfile.mkdtemp(prefix="docpilot-")
        
        try:
            # Clone the repository
            process = await asyncio.create_subprocess_exec(
                "git", "clone", repo_url, repo_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error = stderr.decode().strip()
                return repo_dir, False, error
                
            return repo_dir, True, None
            
        except Exception as e:
            return repo_dir, False, str(e)
    
    def _cleanup_repository(self, repo_dir: str) -> None:
        """
        Clean up a temporary repository directory.
        
        Args:
            repo_dir: The directory to clean up
        """
        try:
            import shutil
            shutil.rmtree(repo_dir)
        except Exception as e:
            logger.error(f"Error cleaning up repository directory: {str(e)}")
            # Continue anyway 