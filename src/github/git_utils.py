"""
Git Repository Utilities
========================

Functions for interacting with Git repositories, such as cloning,
checking out branches, committing, and pushing.
"""

import subprocess
import os
import tempfile
import shutil
from typing import Optional, Tuple

# Assuming logger is available
from src.utils.logging import core_logger
logger = core_logger()


def _run_git_command(command: list[str], cwd: str) -> Tuple[bool, str, str]:
    """Runs a Git command and returns success status, stdout, and stderr."""
    try:
        logger.debug(f"Running git command: 'git {' '.join(command)}' in {cwd}")
        process = subprocess.run(["git"] + command, cwd=cwd, capture_output=True, text=True, check=False) # check=False to handle errors manually
        if process.returncode != 0:
            logger.error(f"Git command failed (ret={process.returncode}): git {' '.join(command)}")
            logger.error(f"Stderr: {process.stderr.strip()}")
            return False, process.stdout.strip(), process.stderr.strip()
        logger.debug(f"Git command successful. Stdout: {process.stdout.strip()[:100]}...") # Log truncated stdout
        return True, process.stdout.strip(), process.stderr.strip()
    except FileNotFoundError:
        logger.error("Git command not found. Ensure Git is installed and in the system PATH.")
        return False, "", "Git command not found."
    except Exception as e:
        logger.exception(f"An unexpected error occurred running git command: git {' '.join(command)}")
        return False, "", str(e)

def clone_repository(repo_url: str, target_dir: str, depth: int = 1, branch: Optional[str] = None) -> bool:
    """Clones a repository into the specified directory."""
    if os.path.exists(target_dir):
        logger.warning(f"Target directory {target_dir} already exists. Removing before cloning.")
        try:
            shutil.rmtree(target_dir)
        except Exception as e:
            logger.error(f"Failed to remove existing directory {target_dir}: {e}")
            return False
    
    os.makedirs(target_dir, exist_ok=True)

    clone_command = ["clone", f"--depth={depth}"]
    if branch:
        clone_command.extend(["--branch", branch])
    clone_command.extend([repo_url, "."]) # Clone into the target_dir itself

    success, _, stderr = _run_git_command(clone_command, cwd=target_dir)
    if not success:
        logger.error(f"Failed to clone repository {repo_url}: {stderr}")
        # Clean up failed clone attempt
        shutil.rmtree(target_dir, ignore_errors=True)
        return False
    
    logger.info(f"Successfully cloned {repo_url} to {target_dir}")
    return True

def checkout_repository(repo_url: str, branch: Optional[str] = None, auth_token: Optional[str] = None) -> Optional[str]:
    """
    Clones a repository into a temporary directory and checks out a specific branch.

    Args:
        repo_url: The HTTPS URL of the repository (potentially including auth).
        branch: The branch to checkout (defaults to repo default if None).
        auth_token: A GitHub token (PAT or Installation Token) for authentication.
                    If provided, it modifies the repo_url for authentication.

    Returns:
        The path to the temporary directory containing the checked-out code,
        or None if checkout fails.
    """
    temp_dir = tempfile.mkdtemp(prefix="docpilot_repo_")
    logger.info(f"Created temporary directory for checkout: {temp_dir}")

    # Modify URL for authentication if token is provided
    if auth_token:
        # Ensure url starts with https://
        if repo_url.startswith("https://github.com/"):
             repo_url = f"https://x-access-token:{auth_token}@github.com/{repo_url[len('https://github.com/'):]}"
        else:
             logger.warning("Auth token provided but URL doesn't look like a standard GitHub HTTPS URL. Attempting clone without modifying URL for auth.")
             # Potentially handle other URL formats or raise an error

    try:
        # Initial shallow clone
        clone_command = ["clone", "--depth=1"]
        if branch:
            clone_command.extend(["--branch", branch])
        clone_command.extend([repo_url, "."]) # Clone into temp_dir
        
        success, _, stderr = _run_git_command(clone_command, cwd=temp_dir)
        
        if not success:
            # Handle cases where the branch might not exist with depth=1
            if branch and ("couldn't find remote ref" in stderr or "does not exist" in stderr):
                logger.warning(f"Initial shallow clone for branch '{branch}' failed. Attempting full clone and checkout...")
                # Clean up failed shallow clone dir before full clone
                shutil.rmtree(temp_dir)
                temp_dir = tempfile.mkdtemp(prefix="docpilot_repo_full_") # New temp dir
                full_clone_cmd = ["clone", repo_url, "."]
                success, _, stderr = _run_git_command(full_clone_cmd, cwd=temp_dir)
                if success:
                    checkout_cmd = ["checkout", branch]
                    success, _, stderr = _run_git_command(checkout_cmd, cwd=temp_dir)
                else:
                     logger.error(f"Full clone also failed: {stderr}")
                     shutil.rmtree(temp_dir, ignore_errors=True)
                     return None
            else:
                logger.error(f"Failed to clone repository {repo_url}: {stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        if not success: # Check success again after potential full clone/checkout
            logger.error(f"Failed to checkout branch '{branch}' in {repo_url}: {stderr}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        logger.info(f"Successfully checked out branch '{branch or 'default'}' of {repo_url} to {temp_dir}")
        return temp_dir

    except Exception as e:
        logger.exception(f"An error occurred during repository checkout: {e}")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return None

def cleanup_repo_dir(dir_path: Optional[str]):
    """Safely removes the temporary repository directory."""
    if dir_path and os.path.exists(dir_path) and dir_path.startswith(tempfile.gettempdir()):
        try:
            shutil.rmtree(dir_path)
            logger.info(f"Successfully cleaned up temporary directory: {dir_path}")
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {dir_path}: {e}")
    elif dir_path:
         logger.warning(f"Attempted to clean up non-temporary directory, skipped: {dir_path}")

def write_doc_file(repo_dir: str, doc_content: str, target_path: str = "DOCPILOT_API.md") -> bool:
    """
    Writes the documentation content to the specified path within the repo directory.

    Args:
        repo_dir: The local path to the checked-out repository.
        doc_content: The string content of the documentation file.
        target_path: The relative path within the repo to write the file.
                     Defaults to "DOCPILOT_API.md".

    Returns:
        True if writing was successful, False otherwise.
    """
    if not os.path.isdir(repo_dir):
        logger.error(f"Repository directory does not exist: {repo_dir}")
        return False

    full_target_path = os.path.join(repo_dir, target_path)
    target_file_dir = os.path.dirname(full_target_path)

    try:
        # Ensure the target directory exists
        if target_file_dir:
            os.makedirs(target_file_dir, exist_ok=True)

        with open(full_target_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        logger.info(f"Successfully wrote documentation to: {full_target_path}")
        return True
    except Exception as e:
        logger.exception(f"Failed to write documentation file to {full_target_path}: {e}")
        return False

# --- Commit and Push Function ---

def commit_and_push(
    repo_dir: str,
    commit_message: str,
    branch: str,
    repo_url: str, # Needed for authenticated push URL
    auth_token: Optional[str] = None,
    remote_name: str = "origin",
    git_user_name: str = "Docpilot Bot",
    git_user_email: str = "bot@docpilot.ai" # Use a generic bot email
) -> Tuple[bool, bool]:
    """
    Stages all changes, commits them, and pushes to the remote repository branch.

    Args:
        repo_dir: The local path to the checked-out repository.
        commit_message: The commit message.
        branch: The branch to push to.
        repo_url: The original HTTPS URL (used to construct auth push URL).
        auth_token: Optional token for authentication.
        remote_name: Name of the remote (usually "origin").
        git_user_name: Git user name for the commit.
        git_user_email: Git user email for the commit.

    Returns:
        Tuple of (commit_success, push_success)
    """
    if not os.path.isdir(repo_dir):
        logger.error(f"Cannot commit/push: Repository directory does not exist: {repo_dir}")
        return False, False

    commit_success = False
    push_success = False

    try:
        # 1. Configure Git user for this operation
        logger.info(f"Configuring git user: {git_user_name} <{git_user_email}> in {repo_dir}")
        config_name_ok, _, err_name = _run_git_command(["config", "user.name", f'"{git_user_name}"' ], cwd=repo_dir)
        config_email_ok, _, err_email = _run_git_command(["config", "user.email", f'"{git_user_email}"' ], cwd=repo_dir)
        if not config_name_ok or not config_email_ok:
            logger.error(f"Failed to configure git user/email: {err_name} {err_email}")
            # Continue if possible, but log error

        # 2. Check for changes
        status_ok, stdout_status, _ = _run_git_command(["status", "--porcelain"], cwd=repo_dir)
        if not status_ok:
            logger.error("Failed to get git status.")
            return False, False
        if not stdout_status.strip():
            logger.info("No changes detected in the repository. Nothing to commit or push.")
            return True, True # No changes means success in this context

        # 3. Stage all changes
        logger.info("Staging changes...")
        add_ok, _, err_add = _run_git_command(["add", "-A"], cwd=repo_dir)
        if not add_ok:
            logger.error(f"Failed to stage changes: {err_add}")
            return False, False

        # 4. Commit changes
        logger.info(f"Committing changes with message: '{commit_message}'")
        commit_ok, _, err_commit = _run_git_command(["commit", "-m", commit_message], cwd=repo_dir)
        if not commit_ok:
            logger.error(f"Failed to commit changes: {err_commit}")
            return False, False
        commit_success = True
        logger.info("Commit successful.")

        # 5. Construct push URL with authentication if token provided
        push_url = repo_url
        if auth_token:
            if repo_url.startswith("https://github.com/"):
                 push_url = f"https://x-access-token:{auth_token}@github.com/{repo_url[len('https://github.com/'):]}"
            else:
                 logger.warning("Cannot construct authenticated push URL from non-standard GitHub HTTPS URL. Push might fail if auth is required.")
        
        # 6. Push changes
        logger.info(f"Pushing changes to {remote_name}/{branch}...")
        # Use --set-upstream if the local branch might not track the remote one yet
        # Force push isn't generally recommended unless specifically needed
        push_ok, _, err_push = _run_git_command(["push", push_url, f"HEAD:{branch}"], cwd=repo_dir)
        
        if not push_ok:
            # Check common push errors (e.g., divergence) - might need more robust handling
            if "rejected" in err_push and "non-fast-forward" in err_push:
                 logger.error(f"Push failed due to non-fast-forward updates. Manual intervention likely needed. Error: {err_push}")
                 # Return commit success = True, push success = False
            else:
                 logger.error(f"Failed to push changes: {err_push}")
            return commit_success, False
        
        push_success = True
        logger.info(f"Successfully pushed changes to {remote_name}/{branch}.")

    except Exception as e:
        logger.exception(f"An error occurred during commit and push: {e}")
        return commit_success, False # Return commit status so far, push failed

    return commit_success, push_success
