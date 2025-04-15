"""
GitHub Authentication Utilities
=============================

Handles JWT generation and installation access token retrieval for GitHub Apps.
"""

import time
import jwt
import requests
from datetime import datetime, timedelta

from ..utils.config import get_settings
from ..utils.logging import core_logger

logger = core_logger()
settings = get_settings()

# Configuration (Load securely from settings/environment variables)
GITHUB_APP_ID = settings.github_app_id
GITHUB_PRIVATE_KEY_PATH = settings.github_private_key_path

def _load_private_key() -> str | None:
    """Loads the GitHub App private key from the path specified in settings."""
    if not GITHUB_PRIVATE_KEY_PATH:
        logger.error("GitHub Private Key path (GITHUB_PRIVATE_KEY_PATH) is not configured.")
        return None
    try:
        with open(GITHUB_PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()
            logger.info(f"Successfully loaded GitHub private key from {GITHUB_PRIVATE_KEY_PATH}")
            return private_key
    except FileNotFoundError:
        logger.error(f"GitHub Private Key file not found at path: {GITHUB_PRIVATE_KEY_PATH}")
        return None
    except Exception as e:
        logger.exception(f"Error reading GitHub private key from {GITHUB_PRIVATE_KEY_PATH}: {str(e)}")
        return None

# Load the key once on module load
_GITHUB_PRIVATE_KEY_CONTENT = _load_private_key()

# Constants
GITHUB_API_BASE_URL = "https://api.github.com"
JWT_EXPIRATION_SECONDS = 600  # 10 minutes, max allowed by GitHub
TOKEN_EXPIRATION_BUFFER_SECONDS = 120 # Refresh token 2 minutes before it expires

def generate_github_jwt() -> str | None:
    """
    Generates a JWT for authenticating as the GitHub App.
    
    Returns:
        The generated JWT string, or None if configuration is missing or invalid.
    """
    private_key = _GITHUB_PRIVATE_KEY_CONTENT # Use the loaded key content
    if not GITHUB_APP_ID or not private_key:
        logger.error("GitHub App ID is missing or Private Key could not be loaded.")
        return None

    try:
        # Timestamps
        now = int(time.time())
        expiration = now + JWT_EXPIRATION_SECONDS

        # Payload
        payload = {
            "iat": now,              # Issued at time
            "exp": expiration,       # JWT expiration time (10 minute maximum)
            "iss": GITHUB_APP_ID     # GitHub App's identifier
        }

        # Generate JWT
        jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
        logger.info(f"Successfully generated JWT for GitHub App ID {GITHUB_APP_ID}")
        return jwt_token

    except Exception as e:
        logger.exception(f"Error generating JWT for GitHub App ID {GITHUB_APP_ID}: {str(e)}")
        return None

def get_installation_access_token(installation_id: int) -> tuple[str | None, datetime | None]:
    """
    Obtains an installation access token for a specific installation.

    Args:
        installation_id: The GitHub ID of the installation.

    Returns:
        A tuple containing: 
            - The access token string (or None on failure).
            - The expiration datetime object (or None on failure).
    """
    jwt_token = generate_github_jwt()
    if not jwt_token:
        return None, None

    token_url = f"{GITHUB_API_BASE_URL}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {jwt_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        logger.info(f"Requesting installation access token for installation ID {installation_id}")
        response = requests.post(token_url, headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        token_data = response.json()
        access_token = token_data.get("token")
        expires_at_str = token_data.get("expires_at") # Example: "2016-07-11T22:14:10Z"

        if not access_token or not expires_at_str:
            logger.error(f"Installation token response missing 'token' or 'expires_at' for installation ID {installation_id}")
            return None, None

        # Parse expiration time (strip 'Z' and parse as UTC)
        try:
            # Handle different possible datetime formats from GitHub API
            if expires_at_str.endswith('Z'):
                 expires_at = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%SZ")
            else:
                 expires_at = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%S")
            # Consider adding timezone info if necessary, though comparisons usually work
            # expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError as dt_error:
            logger.error(f"Could not parse token expiration datetime string '{expires_at_str}': {dt_error}")
            return None, None

        logger.info(f"Successfully obtained installation access token for ID {installation_id}, expires at {expires_at_str}")
        return access_token, expires_at

    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network error getting installation token for ID {installation_id}: {req_err}")
        return None, None
    except Exception as e:
        logger.exception(f"Error getting installation token for ID {installation_id}: {str(e)}")
        # Log response body if available and useful for debugging (careful with sensitive data)
        if 'response' in locals() and response is not None:
             logger.error(f"Response status: {response.status_code}, Body: {response.text[:500]}") # Log first 500 chars
        return None, None

def is_token_expiring_soon(expires_at: datetime | None) -> bool:
    """
    Checks if a token's expiration time is within the buffer period.

    Args:
        expires_at: The token's expiration datetime.

    Returns:
        True if the token is None or expiring soon, False otherwise.
    """
    if not expires_at:
        return True # Treat missing expiration as needing refresh
    
    # Compare naive datetimes (assuming both are UTC or comparable)
    return datetime.utcnow() > (expires_at - timedelta(seconds=TOKEN_EXPIRATION_BUFFER_SECONDS)) 