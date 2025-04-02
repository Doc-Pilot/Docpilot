"""
Metrics Collection Module
========================

This module provides classes and functions for collecting metrics about workflow operations.
"""
import os
import json
import time
import uuid
import csv
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union

logger = logging.getLogger(__name__)

class ModelTokenCost:
    """
    Token cost tracker for different AI models.
    
    This class tracks input and output token costs for different LLM models,
    based on their pricing and uses the pydantic_ai.usage module to get
    actual token counts from agent calls.
    """
    # Model cost mapping in USD per 1K tokens
    MODEL_COSTS = {
        # OpenAI models
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4-32k": {"input": 0.06, "output": 0.12},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        # Anthropic models
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        # Default fallback values
        "default": {"input": 0.01, "output": 0.03}
    }
    
    @classmethod
    def get_model_cost(cls, model_name: str) -> Dict[str, float]:
        """
        Get the cost per token for a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with input and output costs per token
        """
        # Normalize model name (lowercase, remove version suffixes if not found)
        model_name_lower = model_name.lower()
        
        # Try direct match
        if model_name_lower in cls.MODEL_COSTS:
            costs = cls.MODEL_COSTS[model_name_lower]
        else:
            # Try to match model family
            for model_key in cls.MODEL_COSTS:
                if model_name_lower.startswith(model_key):
                    costs = cls.MODEL_COSTS[model_key]
                    break
            else:
                # Fallback to default costs
                costs = cls.MODEL_COSTS["default"]
                logger.warning(f"Using default costs for unknown model: {model_name}")
        
        # Convert from cost per 1K tokens to cost per token
        return {
            "input": costs["input"] / 1000,
            "output": costs["output"] / 1000
        }
    
    @classmethod
    def calculate_cost(cls, 
                      model_name: str, 
                      input_tokens: int, 
                      output_tokens: int) -> Tuple[float, int]:
        """
        Calculate the cost for a specific model and token usage.
        
        Args:
            model_name: Name of the model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Tuple of (total_cost, total_tokens)
        """
        costs = cls.get_model_cost(model_name)
        input_cost = input_tokens * costs["input"]
        output_cost = output_tokens * costs["output"]
        total_cost = input_cost + output_cost
        total_tokens = input_tokens + output_tokens
        
        return total_cost, total_tokens
    
    @classmethod
    def extract_usage_from_result(cls, result: Any) -> Tuple[int, int]:
        """
        Extract token usage from a pydantic_ai result.
        
        This method tries to extract token usage from a result object
        returned by pydantic_ai. If not available, it returns default values.
        
        Args:
            result: The result object from a pydantic_ai agent call
            
        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        # Default values
        input_tokens = 0
        output_tokens = 0
        
        # Try to extract usage from result
        try:
            # Check if result has usage attribute (RunContext)
            if hasattr(result, 'usage'):
                input_tokens = result.usage.prompt_tokens
                output_tokens = result.usage.completion_tokens
            # Check if result has metadata with token count
            elif hasattr(result, 'metadata') and 'token_count' in result.metadata:
                token_data = result.metadata['token_count']
                input_tokens = token_data.get('prompt', 0)
                output_tokens = token_data.get('completion', 0)
            # Try to access usage data through the context attribute
            elif hasattr(result, 'context') and hasattr(result.context, 'usage'):
                input_tokens = result.context.usage.prompt_tokens
                output_tokens = result.context.usage.completion_tokens
        except (AttributeError, KeyError) as e:
            logger.warning(f"Could not extract usage from result: {e}")
        
        return input_tokens, output_tokens

class WorkflowMetrics:
    """Track metrics for different workflows with file-based persistence"""
    
    def __init__(self, output_dir: str, project_name: str):
        """
        Initialize metrics tracking
        
        Args:
            output_dir: Directory to save metrics files
            project_name: Name of the project being analyzed
        """
        self.start_time = time.time()
        self.workflows = {}
        self.total_cost = 0.0
        self.total_tokens = 0
        self.project_name = project_name
        
        # Ensure output directory exists
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize metrics files
        self.metrics_file = os.path.join(self.output_dir, "metrics_summary.json")
        self.log_file = os.path.join(self.output_dir, "metrics_log.csv")
        self.detailed_log = os.path.join(self.output_dir, "detailed_log.txt")
        
        # Initialize log file with header
        with open(self.log_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Timestamp', 'Workflow', 'Action', 'Duration', 'Cost', 'Tokens', 'Model'])
        
        # Initialize detailed log
        with open(self.detailed_log, 'w') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{timestamp} - Metrics tracking initialized for project: {project_name}\n")
    
    def start_workflow(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Start tracking a workflow
        
        Args:
            name: Name of the workflow
            metadata: Additional metadata about the workflow
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.workflows[name] = {
            "start_time": time.time(),
            "steps": [],
            "cost": 0.0,
            "tokens": 0,
            "metadata": metadata or {},
            "success": None
        }
        
        # Log to detailed log
        with open(self.detailed_log, 'a') as f:
            metadata_str = json.dumps(metadata) if metadata else "{}"
            f.write(f"{timestamp} - Started workflow: {name} with metadata: {metadata_str}\n")
    
    def end_workflow(self, name: str, success: bool = True, cost: float = 0.0, tokens: int = 0, 
                     metadata: Optional[Dict[str, Any]] = None, model: str = None):
        """
        End tracking a workflow
        
        Args:
            name: Name of the workflow
            success: Whether the workflow completed successfully
            cost: Additional cost to add to the workflow
            tokens: Additional tokens to add to the workflow
            metadata: Additional metadata about the workflow
            model: The model used for this workflow step
        """
        if name not in self.workflows:
            # Create the workflow if it doesn't exist
            self.start_workflow(name)
        
        end_time = time.time()
        start_time = self.workflows[name]["start_time"]
        duration = end_time - start_time
        
        # Update workflow data
        self.workflows[name]["end_time"] = end_time
        self.workflows[name]["duration"] = duration
        self.workflows[name]["success"] = success
        
        if metadata:
            self.workflows[name]["metadata"].update(metadata)
        
        # Add cost and tokens
        self.workflows[name]["cost"] += cost
        self.workflows[name]["tokens"] += tokens
        self.total_cost += cost
        self.total_tokens += tokens
        
        # Log to CSV
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([timestamp, name, 'END', duration, cost, tokens, model])
        
        # Log to detailed log
        with open(self.detailed_log, 'a') as f:
            status = "successfully" if success else "with errors"
            f.write(f"{timestamp} - Ended workflow: {name} {status} in {duration:.2f}s (cost: ${cost:.6f}, tokens: {tokens})\n")
    
    def log_event(self, workflow: str, action: str, data: Optional[Dict[str, Any]] = None, 
                  model: str = None, result: Any = None):
        """
        Log a workflow event
        
        Args:
            workflow: Name of the workflow
            action: Action being performed
            data: Additional data about the event
            model: Model name used for the action (if applicable)
            result: The result from a pydantic_ai agent call (if available)
        """
        if workflow not in self.workflows:
            # Create the workflow if it doesn't exist
            self.start_workflow(workflow)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = data or {}
        
        # Extract token usage and calculate cost if result is provided
        input_tokens = data.get("input_tokens", 0)
        output_tokens = data.get("output_tokens", 0)
        cost = data.get("cost", 0.0)
        
        if result is not None:
            # Extract token usage from result
            input_tokens, output_tokens = ModelTokenCost.extract_usage_from_result(result)
            
            # Calculate cost based on model
            if model:
                cost, _ = ModelTokenCost.calculate_cost(model, input_tokens, output_tokens)
                
        # If cost or tokens are provided in data, use them
        if "estimated_cost" in data:
            cost = data["estimated_cost"]
        if "estimated_tokens" in data:
            tokens = data["estimated_tokens"]
        else:
            tokens = input_tokens + output_tokens
        
        # Add cost and tokens
        self.workflows[workflow]["cost"] += cost
        self.workflows[workflow]["tokens"] += tokens
        self.total_cost += cost
        self.total_tokens += tokens
        
        # Store the event
        event = {
            "timestamp": timestamp,
            "action": action,
            "data": data,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "model": model
        }
        self.workflows[workflow]["steps"].append(event)
        
        # Log to CSV
        with open(self.log_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            duration = data.get("duration", 0)
            writer.writerow([timestamp, workflow, action, duration, cost, tokens, model])
        
        # Log to detailed log
        with open(self.detailed_log, 'a') as f:
            data_str = ', '.join([f"{k}: {v}" for k, v in data.items()]) if data else ""
            tokens_str = f", tokens: {tokens} (in: {input_tokens}, out: {output_tokens})" if tokens > 0 else ""
            cost_str = f", cost: ${cost:.6f}" if cost > 0 else ""
            model_str = f", model: {model}" if model else ""
            
            f.write(f"{timestamp} - {workflow} - {action} - {data_str}{tokens_str}{cost_str}{model_str}\n")
    
    def save_summary(self):
        """Save a summary of all metrics to a JSON file"""
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        # Calculate metrics
        summary = {
            "project_name": self.project_name,
            "start_time": datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S'),
            "total_duration": total_duration,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "workflows": {}
        }
        
        # Add workflow summaries
        for name, workflow in self.workflows.items():
            workflow_summary = {
                "duration": workflow.get("duration", 0),
                "cost": workflow["cost"],
                "tokens": workflow["tokens"],
                "success": workflow.get("success", None)
            }
            
            if "metadata" in workflow and workflow["metadata"]:
                workflow_summary["metadata"] = workflow["metadata"]
            
            summary["workflows"][name] = workflow_summary
        
        # Save to file
        with open(self.metrics_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        return summary
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics"""
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        # Calculate metrics
        summary = {
            "project_name": self.project_name,
            "start_time": datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S'),
            "total_duration": total_duration,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "workflows": {}
        }
        
        # Add workflow summaries
        for name, workflow in self.workflows.items():
            workflow_summary = {
                "duration": workflow.get("duration", 0),
                "cost": workflow["cost"],
                "tokens": workflow["tokens"],
                "success": workflow.get("success", None)
            }
            
            if "metadata" in workflow and workflow["metadata"]:
                workflow_summary["metadata"] = workflow["metadata"]
            
            summary["workflows"][name] = workflow_summary
        
        return summary 