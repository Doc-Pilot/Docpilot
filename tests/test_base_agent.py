"""
Test Base Agent Module
=====================

This module contains comprehensive tests for the BaseAgent class,
testing all capabilities including token tracking, cost calculation,
metrics integration, and execution flows.
"""

# Importing Dependencies
import os
import sys
import time
import asyncio
import pytest
from typing import Dict, Any, Optional

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.agents.base import BaseAgent, AgentConfig, TaskResult
from src.utils.costs import TokenUsage, ModelCosts, extract_usage_from_result
from src.utils.metrics import get_metrics, reset_metrics

class MockAgent(BaseAgent):
    """Simple agent implementation for testing"""
    
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        super().__init__(config=config, **kwargs)
        
    def success_method(self, sleep_time: float = 0, token_count: int = 100) -> Dict[str, Any]:
        """Test method that always succeeds"""
        # Simulate some processing time
        if sleep_time > 0:
            time.sleep(sleep_time)
            
        # Simulate token usage
        result = {
            "message": "Success!",
            "data": {"value": 42}
        }
        
        # Add mock usage data
        result["usage"] = {
            "prompt_tokens": token_count // 2,
            "completion_tokens": token_count // 2,
            "total_tokens": token_count
        }
        
        return result
    
    def error_method(self, error_message: str = "Test error") -> None:
        """Test method that always fails"""
        raise ValueError(error_message)
        
    def tool_test_tool(self, arg1: str, arg2: int = 0) -> Dict[str, Any]:
        """Test tool implementation"""
        return {
            "arg1": arg1,
            "arg2": arg2,
            "processed": True
        }
    
    async def async_success_method(self, sleep_time: float = 0, token_count: int = 100) -> Dict[str, Any]:
        """Async test method that always succeeds"""
        # Simulate some processing time
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
            
        # Return the same as sync version
        return self.success_method(0, token_count)

@pytest.fixture
def reset_test_metrics():
    """Reset metrics before and after test"""
    reset_metrics()
    yield
    reset_metrics()

@pytest.fixture
def agent(reset_test_metrics):
    """Fixture to create a MockAgent with default config"""
    return MockAgent()

@pytest.fixture
def custom_agent(reset_test_metrics):
    """Fixture to create a MockAgent with custom config"""
    config = AgentConfig(
        model_name="openai:gpt-4o-mini",
        temperature=0.7,
        max_tokens=2000,
        retries=2,
        timeout=30.0,
        log_to_logfire=False
    )
    return MockAgent(config=config)

# Basic Agent Tests
# ===============================

def test_agent_initialization():
    """Test agent initialization with default and custom configs"""
    # Default config
    agent = MockAgent()
    assert agent.config.model_name == "openai:gpt-4o-mini"
    assert agent.config.temperature == 0.1
    assert agent.total_tokens == 0
    assert agent.total_cost == 0.0
    assert isinstance(agent._last_usage, TokenUsage)
    assert agent.agent_id is not None
    
    # Custom config
    custom_config = AgentConfig(
        model_name="claude-3-sonnet",
        temperature=0.7,
        max_tokens=2000
    )
    agent = MockAgent(config=custom_config)
    assert agent.config.model_name == "claude-3-sonnet"
    assert agent.config.temperature == 0.7
    assert agent.config.max_tokens == 2000

# Cost and Token Tracking Tests
# ===============================

def test_model_costs():
    """Test model costs retrieval and calculation"""
    # Check costs for various models
    gpt4_costs = ModelCosts.for_model("gpt-4")
    assert gpt4_costs.input_cost_per_1k == 0.03
    assert gpt4_costs.output_cost_per_1k == 0.06
    
    claude_costs = ModelCosts.for_model("claude-3-haiku")
    assert claude_costs.input_cost_per_1k == 0.00025
    assert claude_costs.output_cost_per_1k == 0.00125
    
    # Test with provider prefix
    gpt4_with_prefix = ModelCosts.for_model("openai:gpt-4")
    assert gpt4_with_prefix.input_cost_per_1k == gpt4_costs.input_cost_per_1k
    
    # Test unknown model (should use default)
    unknown = ModelCosts.for_model("unknown-model")
    assert unknown.input_cost_per_1k == 0.001
    assert unknown.output_cost_per_1k == 0.002

def test_token_usage_and_cost_calculation():
    """Test token usage tracking and cost calculation"""
    # Create token usage
    usage = TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500
    )
    
    # Calculate cost for GPT-4
    cost = usage.calculate_cost("gpt-4")
    expected_cost = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
    assert cost == pytest.approx(expected_cost, rel=1e-6)
    assert usage.cost == pytest.approx(expected_cost, rel=1e-6)
    
    # Calculate cost for Claude model
    usage.cost = 0  # Reset cost
    cost = usage.calculate_cost("claude-3-haiku")
    expected_cost = (1000 * 0.00025 / 1000) + (500 * 0.00125 / 1000)
    assert cost == pytest.approx(expected_cost, rel=1e-6)

def test_extract_usage_from_different_result_types():
    """Test extraction of token usage from different result types"""
    # Test with OpenAI-like completion object
    class MockCompletion:
        def __init__(self):
            self.usage = type('obj', (object,), {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            })
    
    usage = extract_usage_from_result(MockCompletion())
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    
    # Test with dict usage
    result = {"usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}}
    usage = extract_usage_from_result(result)
    assert usage.prompt_tokens == 200
    assert usage.completion_tokens == 100
    assert usage.total_tokens == 300
    
    # Test with _last_usage attribute
    result = type('obj', (object,), {
        '_last_usage': {'prompt_tokens': 300, 'completion_tokens': 150}
    })
    usage = extract_usage_from_result(result)
    assert usage.prompt_tokens == 300
    assert usage.completion_tokens == 150
    assert usage.total_tokens == (usage.prompt_tokens + usage.completion_tokens) or usage.total_tokens == 450

def test_agent_token_tracking(agent):
    """Test the agent's ability to track tokens and costs"""
    # Run operations to generate token usage
    agent.run("success_method", token_count=200)
    agent.run("success_method", token_count=300)
    
    # Check agent's internal tracking
    assert agent.total_tokens == 500
    assert agent.total_cost > 0
    
    # Check usage stats
    stats = agent.get_usage_stats()
    assert stats["total_tokens"] == 500
    assert stats["total_cost"] > 0
    assert stats["model"] == agent.config.model_name
    assert stats["agent_type"] == "MockAgent"

# Method Execution Tests
# ===============================

def test_run_method_success(agent):
    """Test the run method with a successful execution"""
    # Run a method that succeeds
    result = agent.run("success_method", sleep_time=0.1, token_count=200)
    
    # Check the result
    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.error is None
    assert "Success!" in result.result["message"]
    assert result.duration >= 0.1  # Should take at least the sleep time
    assert result.tokens.total_tokens == 200
    assert result.tokens.prompt_tokens == 100
    assert result.tokens.completion_tokens == 100

def test_run_method_error(agent):
    """Test the run method with an execution that fails"""
    # Run a method that fails
    error_message = "Custom error for testing"
    result = agent.run("error_method", error_message=error_message)
    
    # Check the result
    assert isinstance(result, TaskResult)
    assert result.success is False
    assert error_message in result.error
    assert result.result is None
    assert result.duration >= 0

@pytest.mark.asyncio
async def test_run_async_method(agent):
    """Test the run_async method with async and non-async functions"""
    # Run an async method
    result = await agent.run_async("async_success_method", sleep_time=0.1, token_count=150)
    
    # Check the result
    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.tokens.total_tokens == 150
    
    # Run a sync method through run_async
    result = await agent.run_async("success_method", sleep_time=0.1, token_count=250)
    
    # Check the result
    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.tokens.total_tokens == 250
    
    # Check agent state was updated for both calls
    assert agent.total_tokens == 400  # 150 + 250

@pytest.mark.asyncio
async def test_run_tool(agent):
    """Test the run_tool method"""
    # Run a tool
    result = await agent.run_tool("test_tool", {"arg1": "value", "arg2": 42})
    
    # Check the result
    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.result["arg1"] == "value"
    assert result.result["arg2"] == 42
    assert result.result["processed"] is True

# Metrics Integration Tests
# ===============================

def test_agent_metrics_integration(agent):
    """Test the integration between agent and metrics module"""
    # Run multiple operations
    agent.run("success_method", token_count=100)
    agent.run("success_method", token_count=200)
    
    # Check metrics were recorded
    metrics = get_metrics()
    
    # Check token usage metrics
    token_usage = metrics["token_usage"]
    assert token_usage["total_tokens"] == 300
    assert token_usage["prompt_tokens"] == 150
    assert token_usage["completion_tokens"] == 150
    assert token_usage["total_cost"] > 0
    
    # Check operation metrics
    assert len(metrics["operations"]) > 0
    
    # Check model-specific metrics - be resilient to model name issues
    model_name = agent.config.model_name
    assert model_name in token_usage["models"], f"Model '{model_name}' not found in metrics"
    
    model_metrics = token_usage["models"][model_name]
    assert model_metrics["total_tokens"] == 300
    
    # Check operation-specific metrics
    assert "success_method" in model_metrics["operations"]
    op_metrics = model_metrics["operations"]["success_method"]
    assert op_metrics["count"] == 2
    assert op_metrics["total_tokens"] == 300

def test_metrics_with_errors(agent):
    """Test that error operations are properly recorded in metrics"""
    # Run a success operation
    agent.run("success_method", token_count=100)
    
    # Run an error operation
    try:
        agent.run("error_method", error_message="Test error")
    except Exception:
        pass
    
    # Check metrics for both operations
    metrics = get_metrics()
    
    # Verify both operations are recorded
    operations = metrics["operations"]
    assert "success_method" in operations
    assert "error_method" in operations
    
    # Verify success operation details
    success_op = operations["success_method"]
    assert success_op["count"] == 1
    assert success_op["failure_count"] == 0
    
    # Verify error operation details
    error_op = operations["error_method"]
    assert error_op["count"] == 1
    assert error_op["failure_count"] == 1
    
    # Check token usage model metrics
    token_usage = metrics["token_usage"]
    model_name = agent.config.model_name
    
    # Verify model metrics exist
    assert model_name in token_usage["models"]
    
    # Verify model operation metrics
    model_metrics = token_usage["models"][model_name]
    assert "success_method" in model_metrics["operations"]
    
    # Error operations should be recorded with zero tokens
    if "error_method" in model_metrics["operations"]:
        error_tokens = model_metrics["operations"]["error_method"]["total_tokens"]
        assert error_tokens == 0


def verify_metrics_operations(metrics, expected_operations):
    """Helper function to verify metrics operations"""
    operations = metrics["operations"]
    for expected_op in expected_operations:
        assert expected_op in operations, f"Expected operation '{expected_op}' not found in metrics"
    return True

def test_end_to_end_agent_workflow(custom_agent):
    """Test the full agent workflow with token tracking, cost calculation and metrics"""
    # Run multiple operations with different token counts
    custom_agent.run("success_method", token_count=150)
    custom_agent.run("success_method", token_count=250)
    
    try:
        custom_agent.run("error_method", error_message="Expected test error")
    except Exception:
        pass
    
    # Get agent stats
    stats = custom_agent.get_usage_stats()
    assert stats["total_tokens"] == 400
    assert stats["total_cost"] > 0
    assert stats["model"] == "openai:gpt-4o-mini"
    assert stats["agent_type"] == "MockAgent"
    
    # Check metrics integration
    metrics = get_metrics()
    assert metrics["token_usage"]["total_tokens"] == 400
    
    # Check all expected operations are present
    assert verify_metrics_operations(metrics, ["success_method", "error_method"])
    
    # We should have at least 2 operations
    assert len(metrics["operations"]) >= 2
    
    # Check model-specific metrics - be resilient to model name issues
    model_name = custom_agent.config.model_name
    assert model_name in metrics["token_usage"]["models"], f"Model '{model_name}' not found in metrics"
    
    model_metrics = metrics["token_usage"]["models"][model_name]
    assert model_metrics["total_tokens"] == 400
    assert "success_method" in model_metrics["operations"]
    
    # Check combined metrics from all operations
    assert model_metrics["operations"]["success_method"]["count"] == 2
    assert model_metrics["operations"]["success_method"]["total_tokens"] == 400

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 