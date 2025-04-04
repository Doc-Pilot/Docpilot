"""
Docpilot API Module

This module provides the API endpoints for Docpilot.

Key components:
- app.py: Main FastAPI application
- github_webhook.py: GitHub webhook endpoints
"""

# Import the router from github_webhook
from .github_webhook import router as github_router