"""
Cost Utility
===========

This module provides utilities for tracking and calculating token usage and costs
for Large Language Model interactions.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field

class ModelCosts(BaseModel):
    """Defines cost structure for different LLM models"""
    input_cost_per_1k: float = Field(default=0.0, description="Cost per 1000 input tokens")
    output_cost_per_1k: float = Field(default=0.0, description="Cost per 1000 output tokens")
    
    @classmethod
    def for_model(cls, model_name: str) -> "ModelCosts":
        """Get cost structure for a specific model"""
        costs = {
            # OpenAI models
            "gpt-4": cls(input_cost_per_1k=0.03, output_cost_per_1k=0.06),  # $30/1M input, $60/1M output
            "gpt-4-turbo": cls(input_cost_per_1k=0.01, output_cost_per_1k=0.03),  # $10/1M input, $30/1M output
            "gpt-3.5-turbo": cls(input_cost_per_1k=0.0005, output_cost_per_1k=0.0015),  # $0.5/1M input, $1.5/1M output
            
            # Anthropic models
            "claude-3-opus": cls(input_cost_per_1k=0.015, output_cost_per_1k=0.075),  # $15/1M input, $75/1M output
            "claude-3-sonnet": cls(input_cost_per_1k=0.003, output_cost_per_1k=0.015),  # $3/1M input, $15/1M output
            "claude-3-haiku": cls(input_cost_per_1k=0.00025, output_cost_per_1k=0.00125),  # $0.25/1M input, $1.25/1M output
            
            # Cohere models
            "cohere-command": cls(input_cost_per_1k=0.015, output_cost_per_1k=0.015),  # $15/1M tokens
            
            # Default for unknown models
            "default": cls(input_cost_per_1k=0.001, output_cost_per_1k=0.002)  # $1/1M input, $2/1M output
        }
        
        # Extract model name without provider prefix (e.g., openai:gpt-4 -> gpt-4)
        if ":" in model_name:
            _, model_name = model_name.split(":", 1)
        
        # Return costs for the model or default if not found
        return costs.get(model_name, costs["default"])

class TokenUsage(BaseModel):
    """Tracks token usage for a single operation"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    
    @property
    def has_usage(self) -> bool:
        """Check if there's any token usage"""
        return self.total_tokens > 0
    
    def calculate_cost(self, model_name: str) -> float:
        """Calculate cost based on token usage and model"""
        costs = ModelCosts.for_model(model_name)
        
        prompt_cost = self.prompt_tokens * costs.input_cost_per_1k / 1000
        completion_cost = self.completion_tokens * costs.output_cost_per_1k / 1000
        self.cost = round(prompt_cost + completion_cost, 6)
        return self.cost
    
    @classmethod
    def from_completion(cls, completion: Any) -> "TokenUsage":
        """Create TokenUsage from a completion object"""
        if hasattr(completion, "usage"):
            usage = completion.usage
            return cls(
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
                total_tokens=getattr(usage, "total_tokens", 0)
            )
        return cls()
        
def extract_usage_from_result(result: Any) -> TokenUsage:
    """
    Extract token usage information from an agent result.
    
    Args:
        result: The agent run result
        
    Returns:
        TokenUsage with token usage information
    """
    # Initialize token usage
    usage = TokenUsage()
    
    try:
        # Check if result is a dictionary with usage key
        if isinstance(result, dict) and "usage" in result:
            usage_data = result["usage"]
            # Handle dict usage data
            if isinstance(usage_data, dict):
                usage.prompt_tokens = usage_data.get("prompt_tokens", 0)
                usage.completion_tokens = usage_data.get("completion_tokens", 0)
                usage.total_tokens = usage_data.get("total_tokens", 0)
                # Ensure total tokens is set
                if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                return usage
        
        # Check if result is a completion object with usage info
        if hasattr(result, "usage"):
            # Handle obj.usage as dict-like or object-like
            if isinstance(result.usage, dict):
                usage_data = result.usage
                usage.prompt_tokens = usage_data.get("prompt_tokens", 0)
                usage.completion_tokens = usage_data.get("completion_tokens", 0)
                usage.total_tokens = usage_data.get("total_tokens", 0)
            elif hasattr(result.usage, "prompt_tokens"):
                usage.prompt_tokens = getattr(result.usage, "prompt_tokens", 0)
                usage.completion_tokens = getattr(result.usage, "completion_tokens", 0)
                usage.total_tokens = getattr(result.usage, "total_tokens", 0)
            # Ensure total tokens is set
            if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            return usage
        
        # Check if result is a structured object with usage method
        if hasattr(result, "usage") and callable(getattr(result, "usage")):
            usage_data = result.usage()
            if usage_data and isinstance(usage_data, dict):
                usage.prompt_tokens = usage_data.get("prompt_tokens", 0)
                usage.completion_tokens = usage_data.get("completion_tokens", 0)
                usage.total_tokens = usage_data.get("total_tokens", 0)
                # Ensure total tokens is set
                if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                return usage
        
        # Try to access _last_usage directly as fallback
        if hasattr(result, "_last_usage") and result._last_usage:
            usage_data = result._last_usage
            if isinstance(usage_data, dict):
                usage.prompt_tokens = usage_data.get("prompt_tokens", 0)
                usage.completion_tokens = usage_data.get("completion_tokens", 0)
                usage.total_tokens = usage_data.get("total_tokens", 0)
                # Ensure total tokens is set
                if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                return usage
        
        # Try to access raw completion if available
        if hasattr(result, "raw_completion") and result.raw_completion:
            completion = result.raw_completion
            if hasattr(completion, "usage"):
                usage_data = completion.usage
                if isinstance(usage_data, dict):
                    usage.prompt_tokens = usage_data.get("prompt_tokens", 0)
                    usage.completion_tokens = usage_data.get("completion_tokens", 0)
                    usage.total_tokens = usage_data.get("total_tokens", 0)
                else:
                    usage.prompt_tokens = getattr(usage_data, "prompt_tokens", 0)
                    usage.completion_tokens = getattr(usage_data, "completion_tokens", 0)
                    usage.total_tokens = getattr(usage_data, "total_tokens", 0)
                # Ensure total tokens is set
                if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                return usage
    
    except Exception as e:
        # Fail silently if usage extraction fails
        pass
    
    # Ensure total_tokens is properly calculated if not explicitly provided
    if usage.total_tokens == 0 and (usage.prompt_tokens > 0 or usage.completion_tokens > 0):
        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
    
    return usage 