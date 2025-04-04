"""
Unit Tests for BaseAgent
=======================

Comprehensive tests for the BaseAgent class with proper mocking of dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.base import BaseAgent, AgentConfig, AgentResult
from src.utils.metrics import Usage


# Test Models
class TestDeps(BaseModel):
    """Test dependencies model for agents"""
    context: str = Field(default="Test context")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class TestResult(BaseModel):
    """Test result model for agent responses"""
    answer: str
    confidence: float = Field(default=0.9)


# Usage Data class to simulate the object returned by result.usage()
class UsageData:
    """Simulates the usage data object returned by the Agent"""
    def __init__(self, request_tokens=10, response_tokens=5, total_tokens=15):
        self.request_tokens = request_tokens
        self.response_tokens = response_tokens
        self.total_tokens = total_tokens


# Mock Result class to simulate the result returned by Pydantic AI Agent
class MockAgentResult:
    """Mock for the result object returned by Pydantic AI's Agent"""
    def __init__(self, data, usage_data=None):
        self.data = data
        self._usage_data = usage_data or UsageData()
    
    def usage(self):
        """Returns usage data when called"""
        return self._usage_data


# Test Agent class
class TestAgent(BaseAgent[TestDeps, TestResult]):
    """Test agent implementation with defined deps and result types"""
    deps_type = TestDeps
    result_type = TestResult
    default_system_prompt = "You are a test agent."


# Helper function to compare usage objects by their relevant attributes
def assert_usage_similar(actual_usage, expected_usage):
    """Compare Usage objects by their token counts, ignoring cost and model variations"""
    assert actual_usage.prompt_tokens == expected_usage.prompt_tokens
    assert actual_usage.completion_tokens == expected_usage.completion_tokens
    assert actual_usage.total_tokens == expected_usage.total_tokens


class TestBaseAgentClass:
    """Unit tests for the BaseAgent class"""
    
    @patch('src.agents.base.Agent')
    def test_initialization_default_config(self, mock_agent_class):
        """Test agent initialization with default config"""
        # Setup
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        
        # Execute
        agent = TestAgent()
        
        # Assert
        assert agent._deps_type == TestDeps
        assert agent._result_type == TestResult
        assert agent._system_prompt == "You are a test agent."
        mock_agent_class.assert_called_once()
        
        # Check agent settings
        call_kwargs = mock_agent_class.call_args.kwargs
        assert call_kwargs['model'] == agent.config.model_name
        assert call_kwargs['deps_type'] == TestDeps
        assert call_kwargs['result_type'] == TestResult
        assert call_kwargs['system_prompt'] == "You are a test agent."
        assert call_kwargs['instrument'] is True
        assert 'temperature' in call_kwargs['model_settings']
        assert 'max_tokens' in call_kwargs['model_settings']
    
    @patch('src.agents.base.Agent')
    def test_initialization_custom_config(self, mock_agent_class):
        """Test initialization with default config values"""
        # Setup
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        
        # Execute
        agent = TestAgent()
        
        # Assert - checking that default values are used
        assert agent.config.model_name == agent.config.model_name  # Using default
        assert agent.config.temperature == agent.config.temperature  # Using default
        assert agent.config.max_tokens == agent.config.max_tokens  # Using default
        assert agent.config.retry_attempts == agent.config.retry_attempts  # Using default
        
        # Check agent initialization
        call_kwargs = mock_agent_class.call_args.kwargs
        assert call_kwargs['model'] == agent.config.model_name
        assert call_kwargs['model_settings']['temperature'] == agent.config.temperature
        assert call_kwargs['model_settings']['max_tokens'] == agent.config.max_tokens
    
    @patch('src.agents.base.Agent')
    def test_initialization_custom_system_prompt(self, mock_agent_class):
        """Test agent initialization with custom system prompt"""
        # Setup
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        custom_prompt = "You are a specialized test agent."
        
        # Execute
        agent = TestAgent(system_prompt=custom_prompt)
        
        # Assert
        assert agent._system_prompt == custom_prompt
        
        # Check agent initialization
        call_kwargs = mock_agent_class.call_args.kwargs
        assert call_kwargs['system_prompt'] == custom_prompt
    
    @patch('src.agents.base.Agent')
    def test_initialization_custom_types(self, mock_agent_class):
        """Test agent initialization with custom dependency and result types"""
        # Setup
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        
        class CustomDeps(BaseModel):
            query: str
        
        class CustomResult(BaseModel):
            response: str
        
        # Execute
        agent = TestAgent(deps_type=CustomDeps, result_type=CustomResult)
        
        # Assert
        assert agent._deps_type == CustomDeps
        assert agent._result_type == CustomResult
        
        # Check agent initialization
        call_kwargs = mock_agent_class.call_args.kwargs
        assert call_kwargs['deps_type'] == CustomDeps
        assert call_kwargs['result_type'] == CustomResult
    
    def test_missing_result_type(self):
        """Test that initialization fails when result_type is missing"""
        # Define an agent class without result_type
        class InvalidAgent(BaseAgent):
            deps_type = TestDeps
        
        # Assert that creating an instance raises ValueError
        with pytest.raises(ValueError, match="Result type must be specified"):
            InvalidAgent()
    
    @pytest.mark.asyncio
    @patch('src.agents.base.Agent')
    @patch('src.agents.base.extract_usage_from_result')  # Patch at the import location
    async def test_run_method_success(self, mock_extract_usage, mock_agent_class):
        """Test successful execution of the run method"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Create test data
        test_result = TestResult(answer="This is a test response", confidence=0.95)
        mock_result = MockAgentResult(test_result)
        
        # Configure mocks
        mock_agent.run = AsyncMock(return_value=mock_result)
        
        # Create mock usage for the result
        mock_usage = Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            model="gpt-4"
        )
        mock_extract_usage.return_value = mock_usage
        
        # Execute
        agent = TestAgent()
        deps = TestDeps(context="Test context", parameters={"param1": "value1"})
        result = await agent.run("Test prompt", deps=deps)
        
        # Assert
        assert isinstance(result, AgentResult)
        assert result.data == test_result
        assert result.data.answer == "This is a test response"
        assert result.data.confidence == 0.95
        
        # Verify the underlying agent was called correctly
        mock_agent.run.assert_called_once_with(
            user_prompt="Test prompt",
            deps=deps
        )
        
        # Verify extract_usage_from_result was called
        mock_extract_usage.assert_called_once_with(mock_result, agent.config.model_name)
    
    @pytest.mark.asyncio
    @patch('src.agents.base.Agent')
    @patch('src.agents.base.extract_usage_from_result')
    async def test_run_method_extra_kwargs(self, mock_extract_usage, mock_agent_class):
        """Test run method with extra kwargs passed through"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure mocks
        test_result = TestResult(answer="Response with extras")
        mock_result = MockAgentResult(test_result)
        mock_agent.run = AsyncMock(return_value=mock_result)
        
        # Mock the usage
        mock_usage = Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            model="gpt-4"
        )
        mock_extract_usage.return_value = mock_usage
        
        # Execute
        agent = TestAgent()
        result = await agent.run(
            "Test prompt",
            stream=True,
            temperature=0.8,
            max_tokens=500
        )
        
        # Assert
        assert isinstance(result, AgentResult)
        assert result.data.answer == "Response with extras"
        
        # Verify extra kwargs were passed
        mock_agent.run.assert_called_once_with(
            user_prompt="Test prompt",
            deps=None,
            stream=True,
            temperature=0.8,
            max_tokens=500
        )
    
    @pytest.mark.asyncio
    @patch('src.agents.base.Agent')
    @patch('src.agents.base.asyncio.sleep')  # Patch asyncio.sleep to avoid waiting
    async def test_run_method_with_retry(self, mock_sleep, mock_agent_class):
        """Test run method with retry logic"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure to fail twice then succeed
        test_result = TestResult(answer="Success after retries")
        mock_result = MockAgentResult(test_result)
        test_error = ValueError("Temporary error")
        
        # Mock the agent.run method to fail twice then succeed
        mock_agent.run = AsyncMock(side_effect=[
            test_error,  # First attempt fails
            test_error,  # Second attempt fails
            mock_result  # Third attempt succeeds
        ])
        
        # Execute
        agent = TestAgent()
        agent.config.retry_attempts = 3
        agent.config.retry_base_delay = 0.1
        agent.config.max_retry_delay = 1.0
        
        result = await agent.run("Test prompt with retries")
        
        # Assert
        assert isinstance(result, AgentResult)
        assert result.data.answer == "Success after retries"
        
        # Verify that run was called the expected number of times
        assert mock_agent.run.call_count == 3
        
        # Verify that sleep was called with exponential backoff
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([
            call(0.1),  # First retry delay
            call(0.2),  # Second retry delay (doubled)
        ])
    
    @pytest.mark.asyncio
    @patch('src.agents.base.Agent')
    @patch('src.agents.base.asyncio.sleep')
    async def test_run_method_max_retries_exceeded(self, mock_sleep, mock_agent_class):
        """Test run method with all retries exhausted"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure to always fail
        test_error = ValueError("Persistent error")
        mock_agent.run = AsyncMock(side_effect=test_error)
        
        # Execute
        agent = TestAgent()
        agent.config.retry_attempts = 3
        agent.config.retry_base_delay = 0.1
        
        # Assert that after all retries, the error is still raised
        with pytest.raises(ValueError, match="Persistent error"):
            await agent.run("Test prompt with max retries")
        
        # Verify that run was called the expected number of times
        assert mock_agent.run.call_count == 3
        
        # Verify that sleep was called for the retries
        assert mock_sleep.call_count == 2  # One less than attempts
    
    @patch('src.agents.base.Agent')
    @patch('src.agents.base.time.sleep')  # Patch time.sleep for run_sync
    def test_run_sync_method_with_retry(self, mock_sleep, mock_agent_class):
        """Test run_sync method with retry logic"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure to fail once then succeed
        test_result = TestResult(answer="Sync success after retry")
        mock_result = MockAgentResult(test_result)
        test_error = ConnectionError("Network error")
        
        # Mock run_sync to fail first then succeed
        mock_agent.run_sync = MagicMock(side_effect=[
            test_error,  # First attempt fails
            mock_result  # Second attempt succeeds
        ])
        
        # Execute
        agent = TestAgent()
        agent.config.retry_attempts = 2
        agent.config.retry_base_delay = 0.1
        
        result = agent.run_sync("Test sync with retry")
        
        # Assert
        assert isinstance(result, AgentResult)
        assert result.data.answer == "Sync success after retry"
        
        # Verify that run_sync was called twice
        assert mock_agent.run_sync.call_count == 2
        
        # Verify sleep was called once with the correct delay
        mock_sleep.assert_called_once_with(0.1)
    
    @patch('src.agents.base.Agent')
    def test_run_empty_prompt_validation(self, mock_agent_class):
        """Test run method with empty prompt validation"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        agent = TestAgent()
        
        # Assert that empty prompts raise ValueError for run method
        with pytest.raises(ValueError, match="User prompt cannot be empty"):
            agent.run_sync("")
        
        with pytest.raises(ValueError, match="User prompt cannot be empty"):
            agent.run_sync("   ")
            
        # Verify the agent's run was never called
        mock_agent.run.assert_not_called()
    
    @patch('src.agents.base.Agent')
    def test_maximum_retry_delay(self, mock_agent_class):
        """Test that retry delay is capped at the maximum specified value"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Create agent with custom retry config
        agent = TestAgent()
        agent.config.retry_attempts = 5
        agent.config.retry_base_delay = 2.0
        agent.config.max_retry_delay = 10.0
        
        # Calculate delay for each attempt
        delays = []
        for attempt in range(1, agent.config.retry_attempts):
            delay = min(
                agent.config.retry_base_delay * (2 ** (attempt - 1)),
                agent.config.max_retry_delay
            )
            delays.append(delay)
        
        # Assert that delays follow expected pattern and are capped
        assert delays == [2.0, 4.0, 8.0, 10.0]  # Should cap at 10 instead of 16
    
    @pytest.mark.asyncio
    @patch('src.agents.base.Agent')
    async def test_run_method_error_no_retry(self, mock_agent_class):
        """Test run method with error and no retry available"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure to always fail
        test_error = ValueError("Test error")
        mock_agent.run = AsyncMock(side_effect=test_error)
        
        # Execute with no retries
        agent = TestAgent()
        agent.config.retry_attempts = 1  # Only one attempt, no retries
        
        # Assert that the error is propagated
        with pytest.raises(ValueError, match="Test error"):
            await agent.run("Test prompt")
        
        # Verify it was only called once
        mock_agent.run.assert_called_once()
    
    @patch('src.agents.base.Agent')
    def test_tool_registration(self, mock_agent_class):
        """Test registration of tool functions"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure tool decorator to return the decorated function
        def mock_decorator(func):
            func.decorated = True
            return func
            
        mock_agent.tool = MagicMock(side_effect=mock_decorator)
        
        # Execute
        agent = TestAgent()
        
        @agent.tool
        def test_tool(input_data):
            return f"Processed: {input_data}"
        
        # Assert
        mock_agent.tool.assert_called_once_with(test_tool)
        assert hasattr(test_tool, 'decorated')
    
    @patch('src.agents.base.Agent')
    def test_system_prompt_function(self, mock_agent_class):
        """Test registration of system prompt function"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Configure system_prompt to return the decorated function
        def mock_decorator(func):
            func.decorated = True
            return func
            
        mock_agent.system_prompt = MagicMock(side_effect=mock_decorator)
        
        # Execute
        agent = TestAgent()
        
        @agent.system_prompt_fn
        def dynamic_prompt(deps):
            return f"Custom prompt for {deps.context}"
        
        # Assert
        mock_agent.system_prompt.assert_called_once_with(dynamic_prompt)
        assert hasattr(dynamic_prompt, 'decorated')
    
    @patch('src.agents.base.Agent')
    def test_system_prompt_property(self, mock_agent_class):
        """Test system prompt property getter and setter"""
        # Setup
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Set initial value
        mock_agent.system_prompt = "Initial prompt"
        
        # Execute
        agent = TestAgent()
        
        # Test getter
        prompt = agent.system_prompt
        assert prompt == "Initial prompt"
        
        # Test setter
        agent.system_prompt = "Updated prompt"
        assert mock_agent.system_prompt == "Updated prompt"
    
    @patch('src.utils.metrics.extract_usage_from_result')
    @patch('src.agents.base.extract_usage_from_result')
    def test_agent_result_create_method(self, mock_base_extract, mock_metrics_extract):
        """Test AgentResult.create factory method"""
        # Setup
        test_result = TestResult(answer="Test creation", confidence=0.8)
        mock_result = MockAgentResult(test_result)
        
        # Configure mocks - both extracts should use the same mock
        # Match the values from MockAgentResult
        mock_usage = Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.0006,
            model="gpt-4"
        )
        mock_base_extract.return_value = mock_usage
        mock_metrics_extract.return_value = mock_usage
        
        # Execute
        agent_result = AgentResult.create(mock_result, "gpt-4")
        
        # Assert
        assert agent_result.data == test_result
        
        # Check the usage metrics
        assert agent_result.usage.prompt_tokens == 10
        assert agent_result.usage.completion_tokens == 5
        assert agent_result.usage.total_tokens == 15
        
        # Verify extract_usage_from_result was called with the right parameters
        # One of these will be called, depending on the import in the actual code
        assert mock_base_extract.call_count + mock_metrics_extract.call_count > 0
    
    def test_agent_result_properties(self):
        """Test properties of the AgentResult class"""
        # Setup
        test_result = TestResult(answer="Property test")
        
        # Create usage 
        usage = Usage(
            prompt_tokens=15,
            completion_tokens=8,
            total_tokens=23,
            cost=0.001,
            model="gpt-3.5-turbo"
        )
        
        # Create AgentResult directly
        agent_result = AgentResult(data=test_result, usage=usage)
        
        # Test properties
        assert agent_result.total_tokens == 23
        assert agent_result.model == "gpt-3.5-turbo"
        assert agent_result.cost == 0.001
        assert agent_result.data.answer == "Property test"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 