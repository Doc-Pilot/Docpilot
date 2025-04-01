import hmac
import hashlib
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from typing import Optional

from utils.config import get_settings, Settings
from github.handlers import (
    handle_push_event,
    handle_pull_request_event,
    handle_issues_event
)

router = APIRouter()
logger = logging.getLogger(__name__)

def verify_webhook_signature(
    request_body: bytes,
    x_hub_signature_256: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings)
):
    """Verify the GitHub webhook signature"""
    if not settings.github_webhook_secret:
        logger.warning("GitHub webhook secret not set. Skipping signature verification.")
        return True
    
    if not x_hub_signature_256:
        raise HTTPException(status_code=403, detail="Missing X-Hub-Signature-256 header")
    
    signature = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        msg=request_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    return True

@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    verified: bool = Depends(verify_webhook_signature)
):
    """
    GitHub webhook endpoint for handling events
    """
    payload = await request.json()
    logger.info(f"Received GitHub event: {x_github_event}")
    
    try:
        if x_github_event == "push":
            return await handle_push_event(payload)
        elif x_github_event == "pull_request":
            return await handle_pull_request_event(payload)
        elif x_github_event == "issues":
            return await handle_issues_event(payload)
        else:
            logger.info(f"Ignoring unsupported event: {x_github_event}")
            return {"status": "ignored", "event": x_github_event}
            
    except Exception as e:
        logger.exception(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}") 