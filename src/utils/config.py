"""
Configuration Utility
====================

This utility provides configuration settings for DocPilot.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings from environment variables"""
    # Application settings
    app_env: str = "development"
    log_level: str = "INFO"
    debug: bool = False
    
    # Logfire settings
    logfire_token: str = ""
    
    # GitHub settings
    github_app_id: str = ""
    github_private_key_path: str = ""
    github_webhook_secret: str = ""
    github_token: str = ""
    
    # Database settings
    prod_database_url: Optional[str] = None
    dev_database_url: Optional[str] = None
    test_database_url: Optional[str] = None
    
    # AI API settings
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Model settings
    default_model: str = "openai:gpt-4o-mini"
    model_temperature: float = 0.0
    max_tokens: int = 4096
    retry_attempts: int = 2
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @property
    def database_url(self) -> str:
        """Get the database URL based on environment"""
        if self.app_env == "production":
            return self.prod_database_url or ""
        elif self.app_env == "testing":
            return self.test_database_url or ""
        else:
            return self.dev_database_url or ""

@lru_cache()
def get_settings():
    """Get cached settings"""
    return Settings()