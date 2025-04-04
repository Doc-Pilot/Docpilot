"""
Utility Module
=============

This module provides core utilities for the Docpilot library, including:
- Code parsing and structure extraction
- Repository scanning and analysis
- Documentation scanning and metrics
- Logging and configuration

These tools can be used independently or combined into workflows/pipelines.
"""

# Logging and configuration
from .logging import logger
from .config import get_settings

# Repository scanning
from .repo_scanner import RepoScanner

# Metrics and usage tracking
from .metrics import (
    ModelCosts, 
    Usage, 
    extract_usage_from_result
)

# Code parsing and structure extraction
from .code_parser import (
    # Core data structures
    CodeModule,
    CodeClass,
    CodeFunction,
    
    # Main functions
    parse_file,
    parse_code,
    extract_structure,
    
    # Helper functions
    detect_language,
    get_supported_languages,
)

# Document scanning
# No need to import classes that don't exist
# Commenting out this section until we can confirm what's available in doc_scanner.py
# from .doc_scanner import (
#     DocScanner,
#     DocstringStats,
#     DocQuality,
#     scan_file_docstrings,
#     analyze_docstring_quality
# )

# Organize exports by category for better readability and discoverability
__all__ = [
    # Configuration and logging
    "logger",
    "get_settings",
    
    # Repository utilities
    "RepoScanner",
    
    # Cost and token utilities
    "ModelCosts",
    "Usage",
    "extract_usage_from_result",
    
    # Code parsing - core structures
    "CodeModule",
    "CodeClass",
    "CodeFunction",
    
    # Code parsing - main functions
    "parse_file",
    "parse_code",
    "extract_structure",
    "detect_language",
    "get_supported_languages",
    
    # Documentation scanning - commented out until we can verify what's available
    # "DocScanner",
    # "DocstringStats",
    # "DocQuality",
    # "scan_file_docstrings",
    # "analyze_docstring_quality"
]