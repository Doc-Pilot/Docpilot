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
    is_supported_language,
)

# Document scanning
from .doc_scanner import (
    scan_documentation,
    get_changed_files,
    find_related_docs,
    should_update_documentation,
    check_for_significant_changes,
    get_doc_type,
    extract_title,
    get_last_modified
)

# Organize exports by category for better readability and discoverability
__all__ = [
    # Configuration and logging
    "logger",
    "get_settings",
    
    # Cost and token utilities
    "ModelCosts",
    "Usage",
    "extract_usage_from_result",

    # Repository Scanning
    "RepoScanner",
    
    # Code parsing
    "parse_file",
    "parse_code",
    "extract_structure",
    "detect_language",
    "get_supported_languages",
    "is_supported_language",
    
    # Documentation Scanning
    'scan_documentation',
    'get_changed_files',
    'find_related_docs',
    'should_update_documentation',
    'check_for_significant_changes',
    'get_doc_type',
    'extract_title',
    'get_last_modified'
]