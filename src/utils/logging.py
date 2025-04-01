# Importing Dependencies
import logfire
from dotenv import load_dotenv

from .config import get_settings

# Load environment variables
load_dotenv()

def setup_logging():
    """Configure Logfire logging with proper settings"""
    settings = get_settings()
    
    # Configure Logfire with correct parameters
    logfire.configure(
        token=settings.logfire_token,
        service_name="docpilot",
        environment=settings.app_env
    )

    # Instrument Pydantic for validation monitoring
    logfire.instrument_pydantic_ai()
    
    # Log startup information
    logfire.info(
        "Logfire logging configured",
        environment=settings.app_env,
        debug_mode=settings.debug
    )
    
    return logfire

# Create a global logger instance
logger = setup_logging()