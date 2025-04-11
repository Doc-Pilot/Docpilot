"""
GitHub Webhook API
=================

API endpoints for handling GitHub webhook events.
"""

import json
import os
import asyncio

from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..github.webhook_handler import WebhookHandler
from ..github.webhook_verification import verify_webhook_signature, extract_webhook_metadata
from ..utils.config import get_settings
from ..utils.logging import core_logger

# Initialize logger and settings
logger = core_logger()
settings = get_settings()

# -----------------------------------------------------------------------------
# Router and Handler Setup
# -----------------------------------------------------------------------------

# Create an API router
router = APIRouter(prefix="/api/github", tags=["github"])

# Initialize the webhook handler (to be potentially called by background tasks)
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
# Background Task Definition
# -----------------------------------------------------------------------------

async def process_doc_update_job(repo_info: dict, event_details: dict):
    """
    Background task to process the documentation update job.
    This function will eventually trigger the ApiDocAgent.
    """
    logger.info(f"Starting background job for repo: {repo_info.get('full_name')}, event: {event_details.get('event_type')}")
    
    # Placeholder for the actual documentation generation pipeline
    # This is where you would:
    # 1. Clone/checkout the repository
    # 2. Initialize ApiDocDependency with repo_path, changed_files, etc.
    # 3. Instantiate and run the ApiDocAgent
    # 4. Handle the ApiDocumentation result (e.g., commit changes)
    
    try:
        # Simulate processing
        logger.info(f"Simulating doc generation for {repo_info.get('full_name')}")
        # In a real scenario, replace this with actual agent execution:
        # agent = ApiDocAgent(...)
        # deps = ApiDocDependency(repo_path=..., changed_files=event_details['changed_files'], ...)
        # result = await agent.run("Generate API documentation based on recent changes.", deps=deps)
        # handle_agent_result(result) # Function to commit/PR changes
        
        # Simulate success for now
        await asyncio.sleep(5) # Simulate work
        logger.info(f"Successfully processed background job for repo: {repo_info.get('full_name')}")

    except Exception as e:
        logger.exception(f"Error processing background job for {repo_info.get('full_name')}: {str(e)}")
        # Add error handling/reporting logic here (e.g., update job status in DB)

# -----------------------------------------------------------------------------
# Webhook Endpoint
# -----------------------------------------------------------------------------

@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
    x_hub_timestamp: Optional[str] = Header(None), # Deprecated by GitHub but might exist
) -> JSONResponse:
    """
    Handle GitHub webhook events, verify signature, filter events, and enqueue background jobs.
    
    Args:
        request: The FastAPI request object
        background_tasks: FastAPI background tasks manager
        x_hub_signature_256: The X-Hub-Signature-256 header (for webhook verification)
        x_github_event: The X-GitHub-Event header (event type)
        x_github_delivery: The X-GitHub-Delivery header (delivery ID)
        x_hub_timestamp: Deprecated timestamp header
        
    Returns:
        JSON response indicating acceptance or error
    """
    # --- 1. Signature Verification ---
    body = await request.body()
    # The verify_webhook_signature function will load the secret from settings
    
    # Check if signature header is present (as verification function expects it)
    if not x_hub_signature_256:
        logger.warning(f"Missing X-Hub-Signature-256 header for delivery {x_github_delivery}. Denying webhook.")
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256 header.")

    is_valid, message = verify_webhook_signature(
        signature_header=x_hub_signature_256, # Pass the validated header
        body=body,
        request_timestamp=x_hub_timestamp # Pass timestamp if available
    )
    
    if not is_valid:
        logger.warning(f"Webhook verification failed for delivery {x_github_delivery}: {message}")
        raise HTTPException(status_code=401, detail=f"Webhook signature verification failed: {message}")

    logger.info(f"Webhook signature verified successfully for delivery {x_github_delivery}")
    # --- 2. Payload Parsing ---
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload for delivery {x_github_delivery}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Received valid GitHub webhook: {x_github_event} (ID: {x_github_delivery})")

    # --- 3. Event Filtering (Focus on 'push' to target branches for MVP) ---
    target_branches = settings.target_branches # e.g., ["main", "master"]
    
    if x_github_event == "push":
        try:
            ref = payload.get("ref", "") # e.g., "refs/heads/main"
            branch = ref.split('/')[-1]
            repo_info = payload.get("repository", {})
            repo_full_name = repo_info.get("full_name", "unknown/repo")
            
            if branch in target_branches:
                logger.info(f"Processing push event for '{repo_full_name}' on target branch '{branch}'")
                
                # Extract necessary details for the job
                commits = payload.get("commits", [])
                changed_files = set()
                for commit in commits:
                    changed_files.update(commit.get("added", []))
                    changed_files.update(commit.get("modified", []))
                    # We might only care about added/modified for doc generation
                    # changed_files.update(commit.get("removed", [])) 

                event_details = {
                    "event_type": "push",
                    "delivery_id": x_github_delivery,
                    "branch": branch,
                    "base_ref": payload.get("before"), # Commit SHA before push
                    "head_ref": payload.get("after"),  # Commit SHA after push
                    "changed_files": list(changed_files),
                }
                
                # --- 4. Enqueue Background Task ---
                background_tasks.add_task(
                    process_doc_update_job,
                    repo_info=repo_info, 
                    event_details=event_details
                )
                
                logger.info(f"Enqueued background job for '{repo_full_name}' push event.")
                
                return JSONResponse(
                    status_code=202, # Accepted for processing
                    content={
                        "success": True, 
                        "message": f"Accepted push event for '{repo_full_name}' on branch '{branch}'. Processing in background."
                    }
                )
            else:
                logger.info(f"Ignoring push event for '{repo_full_name}' on non-target branch '{branch}'")
                return JSONResponse(status_code=200, content={"success": True, "message": "Event ignored (non-target branch)"})

        except Exception as e:
            logger.exception(f"Error processing push event payload for {x_github_delivery}", exc_info=True)
            # Still return 200 OK to GitHub, but log the error
            return JSONResponse(status_code=200, content={"success": False, "message": "Error processing push event payload"})

    elif x_github_event == "ping":
        logger.info(f"Received ping event from GitHub (ID: {x_github_delivery}). Setup successful.")
        return JSONResponse(status_code=200, content={"success": True, "message": "Pong!"})
        
    elif x_github_event == "installation":
        # Handle installation event (Task #1) - Placeholder
        action = payload.get("action")
        logger.info(f"Received installation event (action: {action}) - Placeholder for Task #1")
        # Add logic here to store/update installation details in DB
        return JSONResponse(status_code=200, content={"success": True, "message": f"Installation event ({action}) received."})

    else:
        logger.info(f"Ignoring unsupported GitHub event: {x_github_event} (ID: {x_github_delivery})")
        return JSONResponse(status_code=200, content={"success": True, "message": f"Event ignored (type: {x_github_event})"})

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
        logger.error(f"Error parsing request payload: {str(e)}", exc_info=True)
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
        logger.exception(f"Error processing manual update: {str(e)}", exc_info=True)

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