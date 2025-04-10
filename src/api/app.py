"""
Docpilot API Application
========================

Main FastAPI application for Docpilot.
"""

import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

# Add the project root to sys.path when running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import project modules after path setup
from src.utils.config import get_settings
from src.database import init_db
from src.api.github_webhook import router as github_router
from src.utils.logging import fastapi_logger

# Get settings
settings = get_settings()

# Initialize FastAPI application
app = FastAPI(
    title="Docpilot API",
    description="API for Docpilot, an AI-powered documentation assistant",
    version="0.1.0"
)

# Configure Logfire for FastAPI
logger = fastapi_logger(app)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    logger.info(
        "DocPilot API starting up",
        extra={
            "environment": settings.app_env,
            "debug_mode": settings.debug
        }
    )
    
    # Initialize the database
    init_db()
    
    yield
    logger.info("DocPilot API shutting down")

# Assign lifespan to the app after logger is initialized
app.router.lifespan_context = lifespan

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you'd want to restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(github_router)

@app.get("/")
async def root():
    """Root endpoint returning basic API information"""
    logger.info("Root endpoint requested")
    return {
        "name": "Docpilot API",
        "version": "0.1.0",
        "description": "AI-powered documentation assistant tool."
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug(
        "Health check requested",
        extra={"environment": settings.app_env}
    )
    return {"status": "healthy"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.exception(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred",
            "error": str(exc)
        }
    )

if __name__ == "__main__":
    if settings.app_env == "development":
        uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)