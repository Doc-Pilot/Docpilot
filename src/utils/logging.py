"""
Logging Configuration
====================

This module provides a centralized logging configuration for the Docpilot project.
It uses Logfire for structured logging and monitoring.
"""

import logfire
from fastapi import FastAPI

from .config import get_settings

settings = get_settings()

def core_logger():
    """
    Logfire instrumentation for core logging
    """
    logfire.configure(
        token=settings.logfire_token,
        service_name="Core",
        environment=settings.app_env
    )

    return logfire

def pydantic_logger():
    """
    Logfire instrumentation for Pydantic AI
    """
    logfire.configure(
        token=settings.logfire_token,
        service_name="Agents",
        environment=settings.app_env
    )

    logfire.instrument_pydantic_ai()

    return logfire

def fastapi_logger(app: FastAPI):
    """
    Logfire instrumentation for FastAPI
    """
    logfire.configure(
        token=settings.logfire_token,
        service_name="FastAPI",
        environment=settings.app_env
    )

    logfire.instrument_fastapi(app)

    return logfire

def sqlalchemy_logger(engine):
    """
    Logfire instrumentation for SQLAlchemy
    """
    logfire.configure(
        token=settings.logfire_token,
        service_name="SQLAlchemy",
        environment=settings.app_env
    )

    logfire.instrument_sqlalchemy(engine)

    return logfire