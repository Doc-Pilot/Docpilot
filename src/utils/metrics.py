"""
Metrics Utility
==============

This module provides utilities for tracking and calculating token usage and costs
for Large Language Model interactions.
"""

from typing import Any
from pydantic import BaseModel, Field
from .logging import logger

class ModelCosts(BaseModel):
    """Defines cost structure for different LLM models"""
    input_cost_per_token: float = Field(default=0.0, description="Cost per input token")
    output_cost_per_token: float = Field(default=0.0, description="Cost per output token")
    
    @classmethod
    def for_model(cls, model_name: str) -> "ModelCosts":
        """Get cost structure for a specific model"""
        costs = {
            # OpenAI models
            "gpt-4": {
                "input_cost_per_token": 0.00003,  # $30/1M input
                "output_cost_per_token": 0.00006,  # $60/1M output
            },
            "gpt-4-turbo": {
                "input_cost_per_token": 0.00001,  # $10/1M input
                "output_cost_per_token": 0.00003,  # $30/1M output
            },
            "gpt-4o": {
                "input_cost_per_token": 0.000005,  # $5/1M input
                "output_cost_per_token": 0.000015,  # $15/1M output
            },
            "gpt-4o-mini": {
                "input_cost_per_token": 0.00000015,  # $0.15/1M input
                "output_cost_per_token": 0.0000006,  # $0.6/1M output
            },
            "gpt-3.5-turbo": {
                "input_cost_per_token": 0.0000005,  # $0.5/1M input
                "output_cost_per_token": 0.0000015,  # $1.5/1M output
            },
            
            # Anthropic models
            "claude-3-opus": {
                "input_cost_per_token": 0.000015,  # $15/1M input
                "output_cost_per_token": 0.000075,  # $75/1M output
            },
            "claude-3-sonnet": {
                "input_cost_per_token": 0.000003,  # $3/1M input
                "output_cost_per_token": 0.000015,  # $15/1M output
            },
            "claude-3-haiku": {
                "input_cost_per_token": 0.00000025,  # $0.25/1M input
                "output_cost_per_token": 0.00000125,  # $1.25/1M output
            },
            
            # Default for unknown models
            "default": {
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
            }
        }
        
        # Extract model name without provider prefix (e.g., openai:gpt-4o -> gpt-4o)
        if ":" in model_name:
            _, model_name = model_name.split(":", 1)
        
        # First try exact match
        if model_name in costs:
            cost_data = costs[model_name]
            return ModelCosts(
                input_cost_per_token=cost_data["input_cost_per_token"],
                output_cost_per_token=cost_data["output_cost_per_token"]
            )
        
        # If no exact match, try prefix match from most specific to least specific
        model_matches = []
        for key in costs:
            if model_name.startswith(key):
                model_matches.append((key, len(key)))
        
        # Sort by length (longest match first)
        model_matches.sort(key=lambda x: x[1], reverse=True)
        
        if model_matches:
            best_match = model_matches[0][0]
            cost_data = costs[best_match]
            return ModelCosts(
                input_cost_per_token=cost_data["input_cost_per_token"],
                output_cost_per_token=cost_data["output_cost_per_token"]
            )
            
        # If still no match, try substring match  
        for key in costs:
            if key in model_name:
                cost_data = costs[key]
                return ModelCosts(
                    input_cost_per_token=cost_data["input_cost_per_token"],
                    output_cost_per_token=cost_data["output_cost_per_token"]
                )
        
        # Return default if no match found
        default_data = costs["default"]
        return ModelCosts(
            input_cost_per_token=default_data["input_cost_per_token"],
            output_cost_per_token=default_data["output_cost_per_token"]
        )

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost for a given number of tokens"""
        input_cost = input_tokens * self.input_cost_per_token
        output_cost = output_tokens * self.output_cost_per_token
        total_cost = input_cost + output_cost
        return total_cost

class Usage(BaseModel):
    """Tracks token usage for a single operation"""
    prompt_tokens: int = Field(default=0, description="Number of tokens in the prompt")
    completion_tokens: int = Field(default=0, description="Number of tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens used")
    cost: float = Field(default=0.0, description="Calculated cost of the operation")
    model: str = Field(default="default", description="Model used for this operation")
    
    def calculate_cost(self, model_name: str) -> float:
        """Calculate cost based on model and update the cost field"""
        costs = ModelCosts.for_model(model_name)
        
        # Calculate actual costs in dollars
        prompt_cost = self.prompt_tokens * costs.input_cost_per_token
        completion_cost = self.completion_tokens * costs.output_cost_per_token
        
        # Store the actual dollar cost without any multiplier
        self.cost = round(prompt_cost + completion_cost, 6)
        
        self.model = model_name
        return self.cost
    
    def add(self, other: "Usage") -> "Usage":
        """Add another usage to this one - used for tracking cumulative usage"""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        # Recalculate cost if model is known
        if self.model and self.model != "default":
            self.calculate_cost(self.model)
        return self

def extract_usage_from_result(result: Any, model_name: str = "default") -> Usage:
    """
    Extract token usage information from a Pydantic AI result.
    
    The function handles Pydantic AI's usage format which returns:
    Usage(requests=n, request_tokens=x, response_tokens=y, total_tokens=z, details={...})
    
    Returns a standardized Usage object with the extracted information.
    """
    # Initialize with default values - ensure we always return a valid Usage object
    usage = Usage(model=model_name)
    
    # Return default usage if no result
    if result is None:
        return usage
    
    try:
        # Get usage data from the Pydantic AI result
        if hasattr(result, "usage") and callable(result.usage):
            usage_data = result.usage()
            
            # Validate that we have a usage object with the expected fields
            if usage_data is None:
                return usage
            
            # Map the Pydantic AI usage fields to our Usage object fields
            # Check each attribute individually to handle different usage formats
            if hasattr(usage_data, "request_tokens"):
                usage.prompt_tokens = usage_data.request_tokens
                
            if hasattr(usage_data, "response_tokens"):
                usage.completion_tokens = usage_data.response_tokens
                
            if hasattr(usage_data, "total_tokens"):
                usage.total_tokens = usage_data.total_tokens
            # If total_tokens not available but we have request and response tokens, calculate it
            elif usage.prompt_tokens > 0 or usage.completion_tokens > 0:
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            
            # Calculate the cost based on the token counts and model - for this individual result
            if usage.total_tokens > 0:
                usage.calculate_cost(model_name)
            else:
                # Only log real issues, not expected cases
                if usage_data and (hasattr(usage_data, "request_tokens") or hasattr(usage_data, "response_tokens")):
                    logger.warning(f"Zero tokens reported in usage data for {model_name}")
    
    except Exception as e:
        # Only log actual exceptions
        logger.error(f"Failed to extract usage metrics: {e}")
    
    # Ensure we return a valid Usage object
    return usage