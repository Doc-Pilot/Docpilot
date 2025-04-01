"""Pytest configuration file."""
import os
import sys
import pytest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure pytest to handle module imports properly
def pytest_configure(config):
    """Configure pytest to handle module imports."""
    # Add modules to be rewritten
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    
    # Configure assertion rewriting
    config.addinivalue_line(
        "markers",
        "rewrite: marks tests that need assertion rewriting"
    )

# Configure test environment
@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    # Set test environment
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Clear any existing environment variables that might interfere
    if "LOGFIRE_TOKEN" in os.environ:
        del os.environ["LOGFIRE_TOKEN"]
    
    yield
    
    # Cleanup after tests
    if "LOGFIRE_TOKEN" in os.environ:
        del os.environ["LOGFIRE_TOKEN"] 