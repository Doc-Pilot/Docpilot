"""
Metrics Utility
==============

This module provides utilities for tracking metrics and operations in the Docpilot pipeline.
It includes timing, counters, and performance tracking for various operations.
"""

import time
import logging
import threading
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from .costs import TokenUsage

# Thread-local storage for operation contexts
_local = threading.local()

# Global metrics registry
_metrics = {
    "operations": {},      # Operation timing metrics
    "counters": {},        # Simple counters
    "performance": {},     # Performance metrics
    "errors": {},          # Error counts by type
    "token_usage": {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_cost": 0.0,
        "models": {},
    },
}

# Logger for metrics
logger = logging.getLogger("metrics")

def start_operation(operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Start tracking an operation with timing.
    
    Args:
        operation_name: The name of the operation to track
        metadata: Optional metadata about the operation
        
    Returns:
        operation_id: A unique identifier for the operation
    """
    # Generate operation ID
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    operation_id = f"{operation_name}_{timestamp}_{id(threading.current_thread())}"
    
    # Initialize thread-local operations dict if needed
    if not hasattr(_local, 'operations'):
        _local.operations = {}
    
    # Store operation context
    _local.operations[operation_id] = {
        "name": operation_name,
        "start_time": time.time(),
        "metadata": metadata or {},
    }
    
    # Log operation start
    logger.debug(f"Operation started: {operation_name}", extra={
        "operation_id": operation_id,
        "metadata": metadata or {},
    })
    
    return operation_id

def end_operation(operation_id: str, success: bool = True, result_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    End tracking an operation and record its metrics.
    
    Args:
        operation_id: The operation ID returned from start_operation
        success: Whether the operation completed successfully
        result_metadata: Optional metadata about the operation result
        
    Returns:
        metrics: Dictionary with metrics about the operation
    """
    # Initialize thread-local operations dict if needed
    if not hasattr(_local, 'operations'):
        _local.operations = {}
    
    # Get operation context
    operation = _local.operations.get(operation_id)
    if not operation:
        logger.warning(f"No operation found with ID: {operation_id}")
        return {}
    
    # Calculate duration
    end_time = time.time()
    duration = end_time - operation["start_time"]
    
    # Record operation metrics
    operation_name = operation["name"]
    
    # Initialize metrics for this operation type if needed
    if operation_name not in _metrics["operations"]:
        _metrics["operations"][operation_name] = {
            "count": 0,
            "success_count": 0,
            "failure_count": 0, 
            "total_duration": 0,
            "max_duration": 0,
            "min_duration": float('inf'),
        }
    
    # Update metrics
    op_metrics = _metrics["operations"][operation_name]
    op_metrics["count"] += 1
    if success:
        op_metrics["success_count"] += 1
    else:
        op_metrics["failure_count"] += 1
    
    op_metrics["total_duration"] += duration
    op_metrics["max_duration"] = max(op_metrics["max_duration"], duration)
    op_metrics["min_duration"] = min(op_metrics["min_duration"], duration)
    
    # Prepare result
    result = {
        "operation_id": operation_id,
        "name": operation_name,
        "duration": duration,
        "success": success,
        "start_time": operation["start_time"],
        "end_time": end_time,
        "metadata": {**operation["metadata"], **(result_metadata or {})},
    }
    
    # Log operation end
    logger.debug(f"Operation ended: {operation_name}", extra={
        "operation_id": operation_id,
        "duration": duration,
        "success": success,
        "metadata": result_metadata or {},
    })
    
    # Clean up thread-local storage
    del _local.operations[operation_id]
    
    return result

def increment_counter(counter_name: str, value: int = 1) -> int:
    """
    Increment a named counter.
    
    Args:
        counter_name: The name of the counter to increment
        value: The amount to increment the counter by
        
    Returns:
        The new counter value
    """
    if counter_name not in _metrics["counters"]:
        _metrics["counters"][counter_name] = 0
    
    _metrics["counters"][counter_name] += value
    return _metrics["counters"][counter_name]

def record_performance_metric(name: str, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Record a performance metric.
    
    Args:
        name: The name of the metric
        value: The value to record
        metadata: Optional metadata about the metric
    """
    if name not in _metrics["performance"]:
        _metrics["performance"][name] = {
            "count": 0,
            "total": 0,
            "max": float('-inf'),
            "min": float('inf'),
            "samples": [],
        }
    
    perf_metric = _metrics["performance"][name]
    perf_metric["count"] += 1
    perf_metric["total"] += value
    perf_metric["max"] = max(perf_metric["max"], value)
    perf_metric["min"] = min(perf_metric["min"], value)
    
    # Store a limited number of samples with timestamps and metadata
    sample = {
        "value": value,
        "timestamp": time.time(),
        "metadata": metadata or {},
    }
    
    # Limit samples to prevent memory issues
    MAX_SAMPLES = 100
    perf_metric["samples"].append(sample)
    if len(perf_metric["samples"]) > MAX_SAMPLES:
        perf_metric["samples"] = perf_metric["samples"][-MAX_SAMPLES:]

def record_error(error_type: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Record an error occurrence.
    
    Args:
        error_type: The type or category of error
        details: Optional details about the error
    """
    if error_type not in _metrics["errors"]:
        _metrics["errors"][error_type] = {
            "count": 0,
            "occurrences": [],
        }
    
    error_metric = _metrics["errors"][error_type]
    error_metric["count"] += 1
    
    # Store error details with timestamp
    occurrence = {
        "timestamp": time.time(),
        "details": details or {},
    }
    
    # Limit occurrences to prevent memory issues
    MAX_OCCURRENCES = 50
    error_metric["occurrences"].append(occurrence)
    if len(error_metric["occurrences"]) > MAX_OCCURRENCES:
        error_metric["occurrences"] = error_metric["occurrences"][-MAX_OCCURRENCES:]

def record_token_usage(
    model_name: str,
    usage: Union[TokenUsage, Dict[str, int]],
    cost: float = 0.0,
    operation: Optional[str] = None
) -> None:
    """
    Record token usage for a model.
    
    Args:
        model_name: Name of the model used
        usage: TokenUsage instance or dict with token counts
        cost: Cost of the operation
        operation: Optional operation name for categorization
    """
    # Convert dict to TokenUsage if needed
    if isinstance(usage, dict):
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cost=cost
        )
    else:
        token_usage = usage
    
    # Update global token metrics
    _metrics["token_usage"]["total_tokens"] += token_usage.total_tokens
    _metrics["token_usage"]["prompt_tokens"] += token_usage.prompt_tokens
    _metrics["token_usage"]["completion_tokens"] += token_usage.completion_tokens
    _metrics["token_usage"]["total_cost"] += token_usage.cost if token_usage.cost > 0 else cost
    
    # Initialize model-specific metrics if needed
    if model_name not in _metrics["token_usage"]["models"]:
        _metrics["token_usage"]["models"][model_name] = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "operations": {}
        }
    
    # Update model-specific metrics
    model_metrics = _metrics["token_usage"]["models"][model_name]
    model_metrics["total_tokens"] += token_usage.total_tokens
    model_metrics["prompt_tokens"] += token_usage.prompt_tokens
    model_metrics["completion_tokens"] += token_usage.completion_tokens
    model_metrics["total_cost"] += token_usage.cost if token_usage.cost > 0 else cost
    
    # Track operation-specific metrics if provided
    if operation:
        if operation not in model_metrics["operations"]:
            model_metrics["operations"][operation] = {
                "count": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0.0
            }
        
        # Update operation metrics
        op_metrics = model_metrics["operations"][operation]
        op_metrics["count"] += 1
        op_metrics["total_tokens"] += token_usage.total_tokens
        op_metrics["prompt_tokens"] += token_usage.prompt_tokens
        op_metrics["completion_tokens"] += token_usage.completion_tokens
        op_metrics["total_cost"] += token_usage.cost if token_usage.cost > 0 else cost

def get_metrics() -> Dict[str, Any]:
    """
    Get the current metrics.
    
    Returns:
        Dictionary containing all recorded metrics
    """
    # Calculate averages for operations
    result = {
        "operations": {},
        "counters": _metrics["counters"].copy(),
        "performance": {},
        "errors": {},
        "token_usage": {
            "total_tokens": _metrics["token_usage"]["total_tokens"],
            "prompt_tokens": _metrics["token_usage"]["prompt_tokens"],
            "completion_tokens": _metrics["token_usage"]["completion_tokens"],
            "total_cost": round(_metrics["token_usage"]["total_cost"], 6),
            "models": {}
        },
    }
    
    # Process operations
    for name, metrics in _metrics["operations"].items():
        result["operations"][name] = metrics.copy()
        if metrics["count"] > 0:
            result["operations"][name]["avg_duration"] = metrics["total_duration"] / metrics["count"]
    
    # Process performance metrics
    for name, metrics in _metrics["performance"].items():
        result["performance"][name] = {
            "count": metrics["count"],
            "total": metrics["total"],
            "max": metrics["max"],
            "min": metrics["min"],
            "avg": metrics["total"] / metrics["count"] if metrics["count"] > 0 else 0,
            "samples": metrics["samples"][-5:],  # Include only the last 5 samples
        }
    
    # Process error metrics
    for name, metrics in _metrics["errors"].items():
        result["errors"][name] = {
            "count": metrics["count"],
            "recent_occurrences": metrics["occurrences"][-5:],  # Include only the last 5 occurrences
        }
    
    # Process model-specific metrics
    for model_name, model_metrics in _metrics["token_usage"]["models"].items():
        result["token_usage"]["models"][model_name] = {
            "total_tokens": model_metrics["total_tokens"],
            "prompt_tokens": model_metrics["prompt_tokens"],
            "completion_tokens": model_metrics["completion_tokens"],
            "total_cost": round(model_metrics["total_cost"], 6),
            "operations": model_metrics["operations"]
        }
    
    return result

def reset_metrics() -> None:
    """Reset all metrics to their initial state."""
    global _metrics
    _metrics = {
        "operations": {},
        "counters": {},
        "performance": {},
        "errors": {},
        "token_usage": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "models": {},
        },
    }
    
    # Also clear thread-local storage
    if hasattr(_local, 'operations'):
        _local.operations = {} 