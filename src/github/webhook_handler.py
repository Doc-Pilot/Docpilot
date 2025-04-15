"""
GitHub Webhook Handler
=====================

Simple handler for GitHub webhooks to test integration with GitHub Apps.
"""

import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ..utils.logging import core_logger
from ..database import get_session
from ..models.installation import Installation
from ..models.repository import Repository

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
        logger.info("Initialized webhook handler")
        
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
        Handle an installation or installation_repositories event and update the database.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        action = payload.get("action", "")
        event_type = payload.get("event_type", "installation") # Determine if 'installation' or 'installation_repositories'
        installation_data = payload.get("installation")
        
        if not installation_data:
            logger.warning("Installation event payload missing 'installation' data.")
            return {
                "success": False, 
                "message": "Missing installation data in payload",
                "event_type": event_type # Use determined event type
            }
            
        github_id = installation_data.get("id")
        account_data = installation_data.get("account", {})
        account_id = account_data.get("id")
        account_login = account_data.get("login")
        account_type = account_data.get("type") # 'Organization' or 'User'
        account_name = account_data.get("name") or account_login # Use login if name is null

        if not github_id or not account_id or not account_login or not account_type:
            logger.warning("Installation event payload missing required fields (github_id, account_id, account_login, account_type).")
            return {
                "success": False, 
                "message": "Missing required fields in installation payload",
                "event_type": event_type # Use determined event type
            }

        try:
            with get_session() as session:
                # Find existing installation by GitHub ID
                installation = session.query(Installation).filter_by(github_id=github_id).first()
                
                # --- Installation Lifecycle Actions --- 
                if action == "created":
                    if installation:
                        # Update existing (potentially re-installed after deletion)
                        installation.is_active = True
                        installation.suspended_reason = None
                        installation.account_id = account_id
                        installation.account_type = account_type
                        installation.account_login = account_login
                        installation.account_name = account_name
                        logger.info(f"Re-activated installation ID {github_id} for {account_login}")
                    else:
                        # Create new installation
                        installation = Installation(
                            github_id=github_id,
                            account_id=account_id,
                            account_type=account_type,
                            account_login=account_login,
                            account_name=account_name,
                            is_active=True,
                        )
                        session.add(installation)
                        logger.info(f"Created new installation ID {github_id} for {account_login}")
                    
                    # Process repositories included in the 'created' payload
                    repositories_added = payload.get("repositories", []) # Note: 'repositories' key here
                    if installation and repositories_added:
                        self._update_repositories(session, installation, repositories_added, [])

                elif action == "deleted":
                    if installation:
                        installation.is_active = False
                        installation.access_token = None # Clear token on deletion
                        installation.token_expires_at = None
                        logger.info(f"Deactivated installation ID {github_id} for {account_login}")

                        # Optionally: Mark associated repositories as inactive or delete them?
                        # For now, we leave Repository records but the Installation is inactive.
                        logger.info(f"Deactivated installation ID {github_id} for {account_login}. Repositories remain linked but inactive.")
                    else:
                        logger.warning(f"Received 'deleted' event for unknown installation ID {github_id}")
                        # Optionally create an inactive record? Or just ignore.

                elif action == "suspend":
                    if installation:
                        installation.is_active = False
                        installation.suspended_reason = payload.get("reason", "Suspended by GitHub")
                        installation.access_token = None # Clear token on suspension
                        installation.token_expires_at = None
                        logger.info(f"Suspended installation ID {github_id} for {account_login}")
                    else:
                        logger.warning(f"Received 'suspend' event for unknown installation ID {github_id}")
                
                elif action == "unsuspend":
                    if installation:
                        installation.is_active = True
                        installation.suspended_reason = None
                        logger.info(f"Unsuspended installation ID {github_id} for {account_login}")
                    else:
                        logger.warning(f"Received 'unsuspend' event for unknown installation ID {github_id}")
                        # Might need to create it if it was deleted previously? Or assume it exists.

                # --- Repository Management Actions (from 'installation_repositories' event) --- 
                elif event_type == "installation_repositories" and action in ["added", "removed"]:
                    if not installation:
                        logger.warning(f"Received '{action}' repo event for unknown/inactive installation ID {github_id}. Ignoring.")
                    elif not installation.is_active:
                        logger.warning(f"Received '{action}' repo event for inactive installation ID {github_id}. Ignoring.")
                    else:
                        # Get lists of repos added/removed from this specific event payload
                        repositories_added = payload.get("repositories_added", [])
                        repositories_removed = payload.get("repositories_removed", [])
                        self._update_repositories(session, installation, repositories_added, repositories_removed)

                else:
                    # Log other actions if needed
                    logger.info(f"Handling installation action '{action}' for event type '{event_type}' on ID {github_id}")

                # get_session handles commit/rollback automatically

            # Return success response
            return {
                "success": True,
                "message": f"GitHub App action '{action}' (event: {event_type}) processed for {account_login}",
                "event_type": event_type,
                "installation_id": github_id,
                "account": account_login,
                "action": action
            }

        except Exception as e:
            logger.exception(f"Error processing installation event for ID {github_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing installation event: {str(e)}",
                "event_type": event_type,
                "installation_id": github_id,
                "action": action
            }

    def _update_repositories(self, session, installation: Installation, repos_added: List[Dict[str, Any]], repos_removed: List[Dict[str, Any]]):
        """
        Helper to add/remove repositories associated with an installation.

        Args:
            session: The SQLAlchemy session object.
            installation: The Installation ORM object.
            repos_added: List of repository dicts to add from the webhook payload.
            repos_removed: List of repository dicts to remove from the webhook payload.
        """
        # Add repositories
        for repo_data in repos_added:
            github_repo_id = repo_data.get("id")
            name = repo_data.get("name")
            full_name = repo_data.get("full_name")
            is_private = repo_data.get("private", False)
            clone_url = repo_data.get("clone_url")
            default_branch = repo_data.get("default_branch", "main") # Add default branch

            if not github_repo_id or not name or not full_name:
                logger.warning(f"Skipping added repo due to missing data: {repo_data}")
                continue

            # Check if repository already exists (by GitHub ID)
            existing_repo = session.query(Repository).filter_by(github_id=github_repo_id).first()

            if existing_repo:
                # If it exists, ensure it's linked to the *current* installation
                # (A repo could theoretically be moved between installations, though unlikely)
                if existing_repo.installation_id != installation.id:
                    logger.info(f"Updating installation link for existing repository {full_name} (ID: {github_repo_id}) to installation {installation.id}")
                    existing_repo.installation_id = installation.id
                else:
                    logger.info(f"Repository {full_name} (ID: {github_repo_id}) already exists and is linked.")
            else:
                # Create new repository
                logger.info(f"Adding repository {full_name} (ID: {github_repo_id}) to installation {installation.id}")
                new_repo = Repository(
                    installation_id=installation.id,
                    github_id=github_repo_id,
                    name=name,
                    full_name=full_name,
                    is_private=is_private,
                    clone_url=clone_url,
                    default_branch=default_branch,
                    # user_id can be set later if needed
                )
                session.add(new_repo)
        
        # Remove repositories (by marking as inactive or deleting? Let's delete for now)
        # We identify them by github_id from the payload
        repo_ids_to_remove = {repo_data.get("id") for repo_data in repos_removed if repo_data.get("id")}

        if repo_ids_to_remove:
            # Find repositories linked to *this* installation that match the IDs to remove
            repos_to_delete = session.query(Repository).filter(
                Repository.installation_id == installation.id,
                Repository.github_id.in_(repo_ids_to_remove)
            ).all()

            for repo in repos_to_delete:
                logger.info(f"Deleting repository {repo.full_name} (ID: {repo.github_id}) from installation {installation.id}")
                session.delete(repo)
            
            if len(repos_to_delete) != len(repo_ids_to_remove):
                 logger.warning(f"Mismatch removing repos: Payload listed {len(repo_ids_to_remove)}, found and deleted {len(repos_to_delete)} linked to installation {installation.id}") 