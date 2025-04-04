"""
Utility Module
=============

This module provides utilities for the Docpilot library, including logging,
cost calculation, token tracking, repository scanning, and file operations.
"""

# Import utility functions
from .repo_scanner import RepoScanner
from .costs import ModelCosts, TokenUsage, extract_usage_from_result
from .metrics import (
    start_operation, end_operation, 
    increment_counter, record_performance_metric, 
    record_error, get_metrics, reset_metrics,
    record_token_usage
)

__all__ = [    
    # Repository utilities
    "RepoScanner",
    
    # Cost and token utilities
    "ModelCosts",
    "TokenUsage",
    "extract_usage_from_result",
    
    # Metrics utilities
    "start_operation",
    "end_operation",
    "increment_counter",
    "record_performance_metric",
    "record_error",
    "get_metrics",
    "reset_metrics",
    "record_token_usage"
]