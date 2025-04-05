"""
GitHub Webhook API
=================

API endpoints for handling GitHub webhook events.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Response, HTTPException, Header, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..github.webhook_handler import WebhookHandler
from ..github.webhook_verification import verify_webhook_signature, extract_webhook_metadata
from ..utils.config import get_settings
from ..utils.logging import logger

# -----------------------------------------------------------------------------
# Router and Handler Setup
# -----------------------------------------------------------------------------

# Create an API router
router = APIRouter(prefix="/api/github", tags=["github"])

# Initialize the webhook handler
webhook_handler = WebhookHandler()

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class WebhookResponse(BaseModel):
    """Response model for webhook endpoints"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# -----------------------------------------------------------------------------
# Webhook Endpoints
# -----------------------------------------------------------------------------

@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
    x_hub_timestamp: Optional[str] = Header(None),
) -> JSONResponse:
    """
    Handle GitHub webhook events.
    
    Args:
        request: The FastAPI request object
        x_hub_signature_256: The X-Hub-Signature-256 header (for webhook verification)
        x_github_event: The X-GitHub-Event header (event type)
        x_github_delivery: The X-GitHub-Delivery header (delivery ID)
        x_hub_timestamp: The X-Hub-Timestamp header (optional timestamp)
        
    Returns:
        JSON response with result of webhook processing
    """
    # Read the raw body
    body = await request.body()
    
    # Verify the webhook signature
    is_valid, message = verify_webhook_signature(
        signature_header=x_hub_signature_256 or "",
        body=body,
        request_timestamp=x_hub_timestamp
    )
    
    if not is_valid:
        logger.warning(f"Webhook verification failed: {message}")
        raise HTTPException(status_code=401, detail=f"Webhook verification failed: {message}")
    
    # Parse the JSON payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Extract metadata from request
    metadata = extract_webhook_metadata(
        headers=dict(request.headers),
        query_params=dict(request.query_params)
    )
    
    # Log the webhook event
    logger.info(f"Received GitHub webhook: {x_github_event} (ID: {x_github_delivery})")
    
    # Process different event types
    try:
        # Handle the webhook event
        result = await webhook_handler.handle_webhook(
            event_type=x_github_event or "unknown",
            payload=payload
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Successfully processed {x_github_event} event",
                "metadata": metadata,
                "result": result
            }
        )
    except Exception as e:
        logger.exception(f"Error processing webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error processing webhook: {str(e)}",
                "metadata": metadata
            }
        )

# -----------------------------------------------------------------------------
# Manual Documentation Update
# -----------------------------------------------------------------------------

@router.post("/update-docs", response_model=WebhookResponse)
async def update_docs(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger a documentation update.
    
    Args:
        request: The FastAPI request object
        background_tasks: FastAPI background tasks
        
    Returns:
        WebhookResponse
    """
    # Parse the request body
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Error parsing request payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    # Extract parameters
    repo_url = data.get("repo_url")
    if not repo_url:
        raise HTTPException(status_code=400, detail="Missing repo_url parameter")
        
    base_ref = data.get("base_ref", "HEAD~1")
    target_ref = data.get("target_ref", "HEAD")
    create_pr = data.get("create_pr", True)
    
    # Process the request in the background
    background_tasks.add_task(
        process_manual_update,
        repo_url=repo_url,
        base_ref=base_ref,
        target_ref=target_ref,
        create_pr=create_pr,
    )
    
    return WebhookResponse(
        success=True,
        message="Processing documentation update in the background",
    )

async def process_manual_update(
    repo_url: str,
    base_ref: str,
    target_ref: str,
    create_pr: bool,
) -> None:
    """
    Process a manual documentation update in the background.
    
    Args:
        repo_url: The repository URL
        base_ref: The base reference (e.g., 'HEAD~1')
        target_ref: The target reference (e.g., 'HEAD')
        create_pr: Whether to create a pull request
    """
    try:
        # Clone the repository locally
        # In a real implementation, this would clone the repo and process it
        logger.info(f"Processing manual update for {repo_url} from {base_ref} to {target_ref}")
        
        # Run the documentation update pipeline
        # This is a placeholder - in the real implementation, you would call your pipeline
        # await webhook_handler.pipeline.run_pipeline(
        #     repo_path=repo_path,
        #     base_ref=base_ref,
        #     target_ref=target_ref,
        #     create_pr=create_pr
        # )
        
        logger.info(f"Completed manual update for {repo_url}")
    except Exception as e:
        logger.exception(f"Error processing manual update: {str(e)}")

# -----------------------------------------------------------------------------
# GitHub App Installation and OAuth Callbacks
# -----------------------------------------------------------------------------

@router.get("/callback")
async def github_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    installation_id: Optional[str] = None,
    setup_action: Optional[str] = None,
) -> JSONResponse:
    """
    Handle GitHub App installation and OAuth callbacks.
    
    This endpoint handles:
    - OAuth authorization callbacks (when 'code' is present)
    - App installation callbacks (when 'installation_id' is present)
    - App setup callbacks (when 'setup_action' is present)
    
    Args:
        request: The FastAPI request object
        code: OAuth authorization code
        installation_id: GitHub App installation ID
        setup_action: Setup action (e.g., 'update' or 'delete')
        
    Returns:
        JSON response or redirect
    """
    logger.info(f"Received GitHub callback: code={code}, installation_id={installation_id}, setup_action={setup_action}")
    
    # Handle OAuth callback (when a user authorizes the app)
    if code:
        # In a real implementation, you would exchange this code for an access token
        # and associate it with the user account
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OAuth authorization successful",
                "next_steps": "The authorization code should be exchanged for an access token"
            }
        )
    
    # Handle installation callback (when someone installs the app)
    if installation_id:
        # In a real implementation, you might store the installation ID
        # or trigger an event to handle the new installation
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"App installation successful (ID: {installation_id})",
                "next_steps": "Your repositories are now connected to Docpilot"
            }
        )
    
    # Handle setup callback (after app creation/update)
    if setup_action:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"App setup action: {setup_action}",
                "next_steps": "Setup is complete. You can now install the app."
            }
        )
    
    # Handle unknown callback type
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "Invalid callback parameters"
        }
    ) 