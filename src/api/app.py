from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logfire
from ..utils.logging import logger
from ..utils.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    settings = get_settings()
    logger.info(
        "DocPilot API starting up",
        environment=settings.app_env,
        debug_mode=settings.debug
    )
    yield
    logger.info("DocPilot API shutting down")

# Initialize FastAPI app
app = FastAPI(
    title="DocPilot API",
    description="API for DocPilot documentation generation and analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with Logfire
logfire.instrument_fastapi(app)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    logger.debug(
        "Health check requested",
        environment=settings.app_env
    )
    return {"status": "healthy"} 