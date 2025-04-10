"""
GitHub Webhook Handler
=====================

Simple handler for GitHub webhooks to test integration with GitHub Apps.
"""

import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ..utils.logging import core_logger

logger = core_logger()

class WebhookHandler:
    """
    Simple handler for GitHub webhooks to test integration.
    
    This handler processes various GitHub webhook events and logs them
    without performing any actual document updates.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the webhook handler"""
        self.config = config or {}
        logger.info("Initialized webhook handler in test mode")
        
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a GitHub webhook event.
        
        Args:
            event_type: The type of event (e.g., "push", "pull_request")
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        logger.info(f"Received GitHub webhook event: {event_type}")
        
        # Log the payload summary
        self._log_payload_summary(event_type, payload)
        
        # Handle different event types
        if event_type == "push":
            return await self.handle_push_event(payload)
        elif event_type == "pull_request":
            return await self.handle_pull_request_event(payload)
        elif event_type == "ping":
            return self.handle_ping_event(payload)
        elif event_type == "installation" or event_type == "installation_repositories":
            return await self.handle_installation_event(payload)
        else:
            logger.info(f"Received unsupported event type: {event_type}")
            return {
                "success": True,
                "message": f"Event type {event_type} acknowledged but not processed",
                "event_type": event_type
            }
    
    def _log_payload_summary(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log a summary of the webhook payload"""
        try:
            # Common information
            repo = payload.get("repository", {}).get("full_name", "N/A")
            sender = payload.get("sender", {}).get("login", "N/A")
            
            # Event-specific information
            if event_type == "push":
                ref = payload.get("ref", "N/A")
                before = payload.get("before", "N/A")[:7]
                after = payload.get("after", "N/A")[:7]
                
                commit_count = len(payload.get("commits", []))
                
                logger.info(f"Push event: {sender} pushed {commit_count} commit(s) to {ref} in {repo} ({before}...{after})")
                
            elif event_type == "pull_request":
                action = payload.get("action", "N/A")
                pr_number = payload.get("number", "N/A")
                pr_title = payload.get("pull_request", {}).get("title", "N/A")
                base = payload.get("pull_request", {}).get("base", {}).get("ref", "N/A")
                head = payload.get("pull_request", {}).get("head", {}).get("ref", "N/A")
                
                logger.info(f"Pull request event: {sender} {action} PR #{pr_number} '{pr_title}' ({head} → {base}) in {repo}")
                
            elif event_type == "ping":
                hook_id = payload.get("hook_id", "N/A")
                hook_url = payload.get("hook", {}).get("config", {}).get("url", "N/A")
                
                logger.info(f"Ping event: Webhook ID {hook_id} configured with URL {hook_url} for {repo}")
                
            elif event_type == "installation" or event_type == "installation_repositories":
                action = payload.get("action", "N/A")
                installation_id = payload.get("installation", {}).get("id", "N/A")
                account = payload.get("installation", {}).get("account", {}).get("login", "N/A")
                
                if event_type == "installation":
                    repos_count = len(payload.get("repositories", []))
                    logger.info(f"Installation event: {account} {action} app (ID: {installation_id}) with {repos_count} repositories")
                else:
                    repos_added = len(payload.get("repositories_added", []))
                    repos_removed = len(payload.get("repositories_removed", []))
                    logger.info(f"Installation repositories event: {account} {action} - added {repos_added}, removed {repos_removed} repositories")
            
            else:
                logger.info(f"Generic {event_type} event from {sender} for {repo}")
                
        except Exception as e:
            logger.error(f"Error logging payload summary: {str(e)}", exc_info=True)
    
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
        
        # Extract push information
        ref = payload.get("ref", "")  # e.g., "refs/heads/main"
        branch = ref.replace("refs/heads/", "")
        
        # Base reference is the previous commit
        before_sha = payload.get("before", "")
        after_sha = payload.get("after", "")
        
        # Commits info
        commits = payload.get("commits", [])
        commit_count = len(commits)
        
        # For testing, just log and return success
        logger.info(f"Push event handled: {commit_count} commit(s) to {branch} in {repo_name}")
        
        return {
            "success": True,
            "message": f"Push to {branch} in {repo_name} successfully received",
            "event_type": "push",
            "repository": repo_name,
            "branch": branch,
            "commits": commit_count
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
        
        # Extract PR information
        pr_info = payload.get("pull_request", {})
        pr_number = pr_info.get("number", 0)
        pr_title = pr_info.get("title", "")
        pr_action = payload.get("action", "")
        
        # Extract branch information
        base_branch = pr_info.get("base", {}).get("ref", "")
        head_branch = pr_info.get("head", {}).get("ref", "")
        
        # Check if this is a PR merge
        is_merged = False
        if pr_action == "closed" and pr_info.get("merged", False):
            is_merged = True
        
        # For testing, just log and return success
        action_text = f"{pr_action} (merged: {is_merged})" if pr_action == "closed" else pr_action
        logger.info(f"PR event handled: {action_text} PR #{pr_number} '{pr_title}' ({head_branch} → {base_branch}) in {repo_name}")
        
        return {
            "success": True,
            "message": f"PR #{pr_number} {action_text} in {repo_name} successfully received",
            "event_type": "pull_request",
            "repository": repo_name,
            "pr_number": pr_number,
            "action": pr_action,
            "is_merged": is_merged,
            "base_branch": base_branch,
            "head_branch": head_branch
        }
    
    def handle_ping_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a ping event.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        hook_id = payload.get("hook_id", "N/A")
        hook_url = payload.get("hook", {}).get("config", {}).get("url", "N/A")
        
        logger.info(f"Ping event handled! Webhook ID: {hook_id}")
        
        return {
            "success": True,
            "message": "Pong! Webhook is configured correctly",
            "event_type": "ping",
            "hook_id": hook_id,
            "zen": payload.get("zen", "")
        }
    
    async def handle_installation_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an installation event.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        action = payload.get("action", "")
        installation_id = payload.get("installation", {}).get("id", "")
        account = payload.get("installation", {}).get("account", {}).get("login", "")
        
        # For testing, just log and return success
        logger.info(f"Installation event handled: {account} {action} (ID: {installation_id})")
        
        return {
            "success": True,
            "message": f"GitHub App {action} by {account}",
            "event_type": payload.get("event_type", "installation"),
            "installation_id": installation_id,
            "account": account,
            "action": action
        } 