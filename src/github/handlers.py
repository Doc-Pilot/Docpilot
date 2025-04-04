"""
GitHub Event Handlers
====================

This module contains handler functions for GitHub events.
"""

import json
import logging
from typing import Dict, Any, Optional

from ..utils.logging import logger

async def handle_push_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a push event from GitHub.
    
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
    
    # Commits info
    commits = payload.get("commits", [])
    commit_count = len(commits)
    
    logger.info(f"Push event handled via handlers.py: {commit_count} commit(s) to {branch} in {repo_name}")
    
    return {
        "success": True,
        "message": f"Push to {branch} in {repo_name} successfully processed",
        "repository": repo_name,
        "branch": branch,
        "commits": commit_count
    }

async def handle_pull_request_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a pull request event from GitHub.
    
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
    
    # Is this a PR merge?
    is_merged = False
    if pr_action == "closed" and pr_info.get("merged", False):
        is_merged = True
    
    action_text = f"{pr_action} (merged: {is_merged})" if pr_action == "closed" else pr_action
    logger.info(f"PR event handled via handlers.py: {action_text} PR #{pr_number} '{pr_title}' ({head_branch} → {base_branch}) in {repo_name}")
    
    return {
        "success": True,
        "message": f"PR #{pr_number} {action_text} in {repo_name} successfully processed",
        "repository": repo_name,
        "pr_number": pr_number,
        "action": pr_action,
        "is_merged": is_merged,
        "base_branch": base_branch,
        "head_branch": head_branch
    }

async def handle_issues_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle an issues event from GitHub.
    
    Args:
        payload: The webhook payload from GitHub
        
    Returns:
        Dictionary with handling results
    """
    # Extract repository information
    repo_info = payload.get("repository", {})
    repo_name = repo_info.get("full_name", "")
    
    # Extract issue information
    issue_info = payload.get("issue", {})
    issue_number = issue_info.get("number", 0)
    issue_title = issue_info.get("title", "")
    issue_action = payload.get("action", "")
    
    logger.info(f"Issue event handled via handlers.py: {issue_action} issue #{issue_number} '{issue_title}' in {repo_name}")
    
    return {
        "success": True,
        "message": f"Issue #{issue_number} {issue_action} in {repo_name} successfully processed",
        "repository": repo_name,
        "issue_number": issue_number,
        "action": issue_action
    } 