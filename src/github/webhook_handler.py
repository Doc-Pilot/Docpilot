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
from .auth import get_installation_access_token, is_token_expiring_soon

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
        Handle a push event, focusing on the default branch for active installations.
        Retrieves/refreshes installation token if needed.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        repo_data = payload.get("repository", {})
        repo_github_id = repo_data.get("id")
        repo_full_name = repo_data.get("full_name", "N/A")
        ref = payload.get("ref", "") # e.g., "refs/heads/main"
        after_sha = payload.get("after", "N/A") # SHA of the latest commit pushed
        
        if not repo_github_id or not ref:
            logger.warning("Push event payload missing repository ID or ref.")
            return {"success": False, "message": "Missing repository ID or ref in push payload"}
            
        # Check if it's a branch push (ignore tag pushes etc.)
        if not ref.startswith("refs/heads/"):
            logger.info(f"Ignoring push event for non-branch ref: {ref} in {repo_full_name}")
            return {"success": True, "message": "Ignored non-branch push event"}
            
        branch = ref.replace("refs/heads/", "")
        
        try:
            with get_session() as session:
                # Find the repository by its GitHub ID
                repository = session.query(Repository).filter_by(github_id=repo_github_id).first()
                
                if not repository:
                    logger.warning(f"Received push event for untracked repository ID {repo_github_id} ({repo_full_name}). App may need install/config update.")
                    return {"success": False, "message": "Repository not found in database"}
                
                # Check if push is to the default branch
                if branch != repository.default_branch:
                    logger.info(f"Ignoring push event to non-default branch '{branch}' for {repo_full_name} (default: {repository.default_branch})")
                    return {"success": True, "message": f"Ignored push to non-default branch '{branch}'"}
                    
                # Get the installation
                installation = repository.installation 
                if not installation:
                    logger.error(f"Repository {repo_full_name} (ID: {repo_github_id}) is not linked to an installation.")
                    return {"success": False, "message": "Repository not linked to an installation"}
                    
                # Check if installation is active
                if not installation.is_active:
                    logger.info(f"Ignoring push event for inactive installation ID {installation.github_id} ({installation.account_login}) linked to repo {repo_full_name}")
                    return {"success": True, "message": "Installation is inactive"}
                    
                # --- Get / Refresh Authentication Token --- 
                access_token = installation.access_token
                expires_at = installation.token_expires_at
                token_valid = False

                if access_token and expires_at and not is_token_expiring_soon(expires_at):
                    logger.info(f"Using existing valid token for installation {installation.github_id}")
                    token_valid = True
                else:
                    logger.info(f"Token is missing, invalid, or expiring soon for installation {installation.github_id}. Refreshing...")
                    # Refresh token - reusing helper from Task 1.2 integration
                    new_token, new_expires_at = await self._get_and_store_token(session, installation)
                    if new_token:
                        access_token = new_token # Use the new token for this request
                        token_valid = True
                        logger.info(f"Successfully refreshed and stored token for installation {installation.github_id}")
                    else:
                        logger.error(f"Failed to refresh token for installation {installation.github_id}. Cannot process push event.")
                        # Mark as not valid, proceed to return failure
                        token_valid = False 
                # -------------------------------------------

                if not token_valid:
                     return {"success": False, "message": f"Failed to obtain valid installation token for push event on {repo_full_name}"}

                # --- Placeholder for Triggering Documentation Pipeline --- 
                logger.info(f"Processing push to default branch '{branch}' for repo {repo_full_name} (Installation: {installation.github_id}) - Commit: {after_sha}")
                logger.info("[MVP Placeholder] Documentation generation would be triggered here using the obtained token.")
                # Example: await trigger_doc_pipeline(installation_id=installation.id, repo_id=repository.id, commit_sha=after_sha, auth_token=access_token)
                # ---------------------------------------------------------

            # If we reached here, processing was successful (or ignored intentionally)
            return {
                "success": True,
                "message": f"Push to default branch '{branch}' in {repo_full_name} processed.",
                "event_type": "push",
                "repository": repo_full_name,
                "branch": branch,
                "commit_sha": after_sha
            }

        except Exception as e:
            logger.exception(f"Error processing push event for repo {repo_full_name}: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing push event: {str(e)}",
                "event_type": "push",
                "repository": repo_full_name
            }
    
    async def handle_pull_request_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a pull request event, specifically merged PRs for active installations.
        Retrieves/refreshes installation token if needed.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            Dictionary with handling results
        """
        pr_action = payload.get("action", "")
        pr_info = payload.get("pull_request", {})
        is_merged = pr_info.get("merged", False)
        
        # --- Filter for merged PRs only --- 
        if not (pr_action == "closed" and is_merged):
            logger.info(f"Ignoring PR event with action '{pr_action}' (merged: {is_merged})")
            return {"success": True, "message": f"Ignored PR event (action: {pr_action}, merged: {is_merged})"}
        # -------------------------------------
            
        repo_data = payload.get("repository", {})
        repo_github_id = repo_data.get("id")
        repo_full_name = repo_data.get("full_name", "N/A")
        pr_number = payload.get("number", "N/A") # PR number
        merge_commit_sha = pr_info.get("merge_commit_sha", "N/A")
        base_branch = pr_info.get("base", {}).get("ref", "N/A")
        head_branch = pr_info.get("head", {}).get("ref", "N/A")
        pr_title = pr_info.get("title", "N/A")

        if not repo_github_id:
            logger.warning("Pull request event payload missing repository ID.")
            return {"success": False, "message": "Missing repository ID in pull request payload"}

        try:
            with get_session() as session:
                # Find the repository by its GitHub ID
                repository = session.query(Repository).filter_by(github_id=repo_github_id).first()
                
                if not repository:
                    logger.warning(f"Received PR event for untracked repository ID {repo_github_id} ({repo_full_name}). App may need install/config update.")
                    return {"success": False, "message": "Repository not found in database"}
                
                # Get the installation
                installation = repository.installation 
                if not installation:
                    logger.error(f"Repository {repo_full_name} (ID: {repo_github_id}) is not linked to an installation.")
                    return {"success": False, "message": "Repository not linked to an installation"}
                    
                # Check if installation is active
                if not installation.is_active:
                    logger.info(f"Ignoring PR event for inactive installation ID {installation.github_id} ({installation.account_login}) linked to repo {repo_full_name}")
                    return {"success": True, "message": "Installation is inactive"}
                    
                # --- Get / Refresh Authentication Token --- 
                access_token = installation.access_token
                expires_at = installation.token_expires_at
                token_valid = False

                if access_token and expires_at and not is_token_expiring_soon(expires_at):
                    logger.info(f"Using existing valid token for installation {installation.github_id} for PR merge.")
                    token_valid = True
                else:
                    logger.info(f"Token is missing, invalid, or expiring soon for installation {installation.github_id} for PR merge. Refreshing...")
                    new_token, new_expires_at = await self._get_and_store_token(session, installation)
                    if new_token:
                        access_token = new_token
                        token_valid = True
                        logger.info(f"Successfully refreshed and stored token for installation {installation.github_id} for PR merge.")
                    else:
                        logger.error(f"Failed to refresh token for installation {installation.github_id}. Cannot process PR merge event.")
                        token_valid = False 
                # -------------------------------------------

                if not token_valid:
                     return {"success": False, "message": f"Failed to obtain valid installation token for PR merge event on {repo_full_name}"}

                # --- Placeholder for Triggering Documentation Pipeline --- 
                logger.info(f"Processing PR Merge for repo {repo_full_name} (Installation: {installation.github_id}) - PR #{pr_number} '{pr_title}', Merge SHA: {merge_commit_sha}")
                logger.info("[MVP Placeholder] Documentation generation would be triggered here using the obtained token.")
                # Example: await trigger_doc_pipeline_for_pr(installation_id=installation.id, repo_id=repository.id, pr_number=pr_number, merge_commit_sha=merge_commit_sha, auth_token=access_token)
                # ---------------------------------------------------------

            # If we reached here, processing was successful
            return {
                "success": True,
                "message": f"Merged PR #{pr_number} in {repo_full_name} processed.",
                "event_type": "pull_request",
                "repository": repo_full_name,
                "pr_number": pr_number,
                "action": pr_action,
                "is_merged": is_merged,
                "merge_commit_sha": merge_commit_sha
            }

        except Exception as e:
            logger.exception(f"Error processing PR event for repo {repo_full_name}, PR #{pr_number}: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing pull_request event: {str(e)}",
                "event_type": "pull_request",
                "repository": repo_full_name,
                "pr_number": pr_number
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
                    
                    # --- Get and store initial access token ---    
                    if installation:
                        token, expires_at = await self._get_and_store_token(session, installation)
                        if not token:
                            logger.error(f"Failed to obtain initial installation token for {github_id}. Installation record created/updated but unusable.")
                            # Decide on error handling: raise exception? return error response? For now, log it.
                        else:
                            logger.info(f"Successfully obtained and stored initial token for installation {github_id}")
                            # Ensure the changes are flushed before commit if needed, though get_session handles commit.
                    # -------------------------------------------

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
                        # If we created it here, we'd need to get a token too.
                        
                    # --- Get and store access token on unsuspend --- 
                    if installation and installation.is_active:
                        token, expires_at = await self._get_and_store_token(session, installation)
                        if not token:
                            logger.error(f"Failed to obtain token for unsuspended installation {github_id}. Installation is active but may be unusable without a token.")
                        else:
                            logger.info(f"Successfully obtained and stored token for unsuspended installation {github_id}")
                    # -------------------------------------------

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

    async def _get_and_store_token(self, session, installation: Installation) -> tuple[str | None, datetime | None]:
        """
        Helper function to get an installation token and store it in the database.

        Args:
            session: The SQLAlchemy session.
            installation: The Installation object to update.

        Returns:
            A tuple of (token, expires_at) or (None, None) on failure.
        """
        logger.info(f"Attempting to retrieve and store token for installation ID {installation.github_id}")
        # Note: get_installation_access_token is synchronous, but we keep the handler async
        # In a high-concurrency scenario, consider running sync code in a thread pool
        # or using an async HTTP client library (e.g., httpx) in auth.py
        access_token, expires_at = get_installation_access_token(installation.github_id)

        if access_token and expires_at:
            installation.access_token = access_token
            installation.token_expires_at = expires_at
            # The session commit is handled by the get_session context manager
            # session.add(installation) # Not needed if installation is already managed by session
            logger.info(f"Successfully stored token for installation {installation.github_id}")
            return access_token, expires_at
        else:
            logger.error(f"Failed to retrieve token for installation {installation.github_id}")
            # Optionally clear existing token fields if retrieval fails?
            # installation.access_token = None
            # installation.token_expires_at = None
            return None, None

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