"""
API Server
=========

FastAPI server for handling GitHub webhooks and triggering documentation updates.
"""

import os
import json
import hmac
import hashlib
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..github.webhook_handler import WebhookHandler
from ..utils.logging import logger

# Create the FastAPI app
app = FastAPI(
    title="DocPilot API",
    description="API for handling GitHub webhooks and triggering documentation updates",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the webhook handler
webhook_handler = WebhookHandler()

# Models
class WebhookResponse(BaseModel):
    """Response model for webhook endpoints"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


async def verify_github_signature(request: Request, x_hub_signature_256: Optional[str] = Header(None)) -> bool:
    """
    Verify the GitHub webhook signature.
    
    Args:
        request: The FastAPI request
        x_hub_signature_256: The GitHub signature header
        
    Returns:
        True if the signature is valid, False otherwise
    """
    # Get the GitHub webhook secret from environment variables
    github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    
    # If no secret is configured, skip verification in development
    if not github_webhook_secret:
        logger.warning("No GitHub webhook secret configured, skipping signature verification")
        return True
        
    # If no signature is provided, reject the request
    if not x_hub_signature_256:
        return False
        
    # Get the request body
    body = await request.body()
    
    # Calculate the HMAC using the secret
    signature = hmac.new(
        github_webhook_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Compare the signatures
    expected_signature = f"sha256={signature}"
    return hmac.compare_digest(expected_signature, x_hub_signature_256)


@app.post("/api/webhook/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    is_valid: bool = Depends(verify_github_signature)
):
    """
    Handle a GitHub webhook event.
    
    Args:
        request: The FastAPI request
        background_tasks: FastAPI background tasks
        x_github_event: The GitHub event type
        is_valid: Whether the signature is valid
        
    Returns:
        WebhookResponse
    """
    # Check if the signature is valid
    if not is_valid:
        logger.warning("Invalid GitHub webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    # Check if the event type is provided
    if not x_github_event:
        logger.warning("No GitHub event type provided")
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
        
    # Parse the request body
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    # Process the webhook in the background
    background_tasks.add_task(process_github_webhook, x_github_event, payload)
    
    return WebhookResponse(
        success=True,
        message=f"Processing {x_github_event} event in the background",
    )


async def process_github_webhook(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Process a GitHub webhook event in the background.
    
    Args:
        event_type: The GitHub event type
        payload: The webhook payload
    """
    try:
        # Handle the webhook
        result = await webhook_handler.handle_webhook(event_type, payload)
        
        # Log the result
        if result.get("success", False):
            logger.info(f"Successfully processed {event_type} event")
        else:
            logger.error(f"Error processing {event_type} event: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error processing {event_type} event: {str(e)}")


@app.post("/api/update-docs", response_model=WebhookResponse)
async def update_docs(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger a documentation update.
    
    Args:
        request: The FastAPI request
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
        base_ref: The base reference
        target_ref: The target reference
        create_pr: Whether to create a PR
    """
    try:
        # Clone the repository
        repo_dir, success, error = await webhook_handler._clone_repository(repo_url)
        if not success:
            logger.error(f"Error cloning repository: {error}")
            return
            
        try:
            # Run the documentation update pipeline
            result = await webhook_handler.pipeline.run_pipeline(
                repo_path=repo_dir,
                base_ref=base_ref,
                target_ref=target_ref,
                create_pr=create_pr,
            )
            
            # Log the result
            if result.get("success", False):
                logger.info("Successfully processed documentation update")
            else:
                logger.error(f"Error processing documentation update: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing documentation update: {str(e)}")
            
        finally:
            # Clean up the repository
            webhook_handler._cleanup_repository(repo_dir)
            
    except Exception as e:
        logger.error(f"Error processing documentation update: {str(e)}")


if __name__ == "__main__":
    # Get the port from environment variables or use a default
    port = int(os.environ.get("PORT", 8000))
    
    # Run the server
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    ) 