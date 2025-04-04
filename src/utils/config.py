"""
Configuration Utility
====================

This utility provides configuration settings for DocPilot.
"""

# Importing Dependencies
import os
from functools import lru_cache
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseModel):
    """Application settings from environment variables"""
    # Application settings
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Logfire settings
    logfire_token: str = os.getenv("LOGFIRE_TOKEN", "")
    
    # GitHub settings
    github_app_id: str = os.getenv("GITHUB_APP_ID", "")
    github_private_key_path: str = os.getenv("GITHUB_PRIVATE_KEY_PATH", "")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    
    # Database settings
    database_url: str = os.getenv("DATABASE_URL", "")
    
    # AI API settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Model settings
    default_model: str = os.getenv("DEFAULT_MODEL", "openai:gpt-4o-mini")
    model_temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "2"))
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """def get_settings() -> Settings:
    """
    Get cached settings.

    This function retrieves the settings that have been cached using an
    LRU (Least Recently Used) cache to optimize performance. The cached
    settings can be used throughout the application to avoid repeated
    computation and fetching of configuration values.

    Returns:
        Settings: An instance of the `Settings` class containing the
        cached configuration values.

    Example:
        settings = get_settings()
        print(settings.some_config_value)
    """"""
    return Settings() 