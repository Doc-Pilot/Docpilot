"""
Docpilot API Application
========================

Main FastAPI application for Docpilot.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logfire

from ..utils import get_settings
from .github_webhook import router as github_router

# Get logger
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fastapi")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    settings = get_settings()
    logger.info(
        "DocPilot API starting up",
        extra={
            "environment": settings.app_env,
            "debug_mode": settings.debug
        }
    )
    yield
    logger.info("DocPilot API shutting down")

# Initialize the FastAPI application
app = FastAPI(
    title="Docpilot API",
    description="API for Docpilot, an AI-powered documentation assistant",
    version="0.1.0",
    lifespan=lifespan
)

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

# Instrument FastAPI with Logfire if available
try:
    logfire.instrument_fastapi(app)
except (ImportError, AttributeError):
    logger.warning("Logfire FastAPI instrumentation not available")

@app.get("/")
async def root():
    """Root endpoint returning basic API information"""
    return {
        "name": "Docpilot API",
        "version": "0.1.0",
        "description": "AI-powered documentation assistant"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    logger.debug(
        "Health check requested",
        extra={"environment": settings.app_env}
    )
    return {"status": "healthy"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred",
            "error": str(exc)
        }
    )

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Can be used for testing or when more setup is needed before returning the app.
    """
    # Initialize additional resources or configurations if needed
    settings = get_settings()
    
    # Log configuration details
    logger.info(f"Starting Docpilot API in {settings.app_env} environment")
    
    return app

# This allows the app to be imported and used with different ASGI servers
if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True) 