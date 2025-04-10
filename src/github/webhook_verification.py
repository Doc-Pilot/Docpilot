"""
GitHub Webhook Verification
==========================

Utilities for verifying the authenticity of GitHub webhooks.
"""

import hmac
import hashlib
from typing import Optional, Tuple, Dict, Any
import time

from ..utils.config import get_settings
from ..utils.logging import core_logger

logger = core_logger()

def verify_webhook_signature(
    signature_header: str,
    body: bytes,
    request_timestamp: Optional[str] = None,
    max_age: int = 300,  # 5 minutes
) -> Tuple[bool, str]:
    """
    Verify the GitHub webhook signature to ensure the webhook is authentic.
    
    Args:
        signature_header: The X-Hub-Signature-256 header value
        body: The raw request body as bytes
        request_timestamp: The X-Hub-Timestamp header value, if present
        max_age: Maximum age of the webhook in seconds (default: 5 minutes)
        
    Returns:
        Tuple of (is_valid, message)
    """
    settings = get_settings()
    
    # If webhook secret is not configured, log a warning and return False
    if not settings.github_webhook_secret:
        logger.warning("GitHub webhook secret is not configured!")
        return False, "Webhook secret not configured"
        
    # Check if signature header is present
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False, "Missing signature header"
        
    # Check if signature header has the correct format
    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format")
        return False, "Invalid signature format"
        
    # Check timestamp if provided to prevent replay attacks
    if request_timestamp:
        try:
            webhook_time = int(request_timestamp)
            current_time = int(time.time())
            
            if current_time - webhook_time > max_age:
                logger.warning(f"Webhook is too old: {current_time - webhook_time} seconds")
                return False, "Webhook is too old"
        except ValueError:
            logger.warning("Invalid timestamp format")
            return False, "Invalid timestamp format"
            
    # Verify signature
    try:
        # Extract signature from header
        signature = signature_header.replace("sha256=", "")
        
        # Compute expected signature
        secret = settings.github_webhook_secret.encode('utf-8')
        expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        
        # Debug log the signatures (remove in production)
        logger.debug(f"Received signature: {signature}")
        logger.debug(f"Expected signature: {expected_signature}")
        
        # Use constant-time comparison to prevent timing attacks
        if hmac.compare_digest(signature, expected_signature):
            return True, "Signature verified"
        else:
            logger.warning("Webhook signature verification failed")
            logger.warning(f"Signatures don't match: got {signature[:10]}..., expected {expected_signature[:10]}...")
            return False, "Invalid signature"
    except Exception as e:
        logger.exception(f"Error verifying webhook signature: {str(e)}", exc_info=True)
        return False, f"Verification error: {str(e)}"

def extract_webhook_metadata(
    headers: Dict[str, str],
    query_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract metadata from webhook request headers and query parameters.
    
    Args:
        headers: The request headers
        query_params: The query parameters
        
    Returns:
        Dictionary containing webhook metadata
    """
    return {
        "event_type": headers.get("X-GitHub-Event", "unknown"),
        "delivery_id": headers.get("X-GitHub-Delivery", ""),
        "installation_id": query_params.get("installation_id"),
        "sender": query_params.get("sender"),
        "user_agent": headers.get("User-Agent", ""),
        "content_type": headers.get("Content-Type", ""),
    } 