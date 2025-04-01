import os
import sys
import pytest
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.agents.base import BaseAgent, AgentConfig

# Define input type as dataclass
@dataclass
class GreetingInput:
    """Input for greeting generation"""
    language: str
    formality: str
    recipient: str = "everyone"

# Define a simple result type as Pydantic model
class GreetingResult(BaseModel):
    """Result of greeting generation"""
    greeting: str = Field(description="The generated greeting")
    language: str = Field(description="The language of the greeting")
    formality: str = Field(description="The formality level (formal, casual)")

# Define a simple agent that generates greetings
class GreetingAgent(BaseAgent[GreetingResult]):
    """Agent for generating greetings in different languages"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config,
            system_prompt="""You are a greeting expert. Generate appropriate greetings based on the user's request.
            Consider the language and formality level specified.""",
            model_type=GreetingResult
        )

@pytest.mark.rewrite
def test_greeting_agent():
    """Test the greeting agent with a simple request"""
    # Create agent instance
    agent = GreetingAgent()
    
    # Test synchronous execution
    input_data = GreetingInput(
        language="Spanish",
        formality="formal"
    )
    result = agent.run_sync(
        user_prompt=f"Generate a {input_data.formality} greeting in {input_data.language} for {input_data.recipient}",
        deps=input_data
    )
    
    # Verify the result structure
    assert isinstance(result, GreetingResult)
    assert result.greeting
    assert result.language == "Spanish"
    assert result.formality == "formal"
    
    # Test with different parameters
    input_data = GreetingInput(
        language="French",
        formality="casual",
        recipient="friends"
    )
    result = agent.run_sync(
        user_prompt=f"Generate a {input_data.formality} greeting in {input_data.language} for {input_data.recipient}",
        deps=input_data
    )
    
    # Verify the result structure
    assert isinstance(result, GreetingResult)
    assert result.greeting
    assert result.language == "French"
    assert result.formality == "casual"

@pytest.mark.rewrite
def test_agent_config():
    """Test agent configuration"""
    # Create custom config
    config = AgentConfig()
    config.model_name = "openai:gpt-4o-mini"
    config.temperature = 0.5
    config.max_tokens = 1000
    config.retry_attempts = 2
    
    # Create agent with custom config
    agent = GreetingAgent(config=config)
    
    # Verify config was applied
    assert agent.config.model_name == "openai:gpt-4o-mini"
    assert agent.config.temperature == 0.5
    assert agent.config.max_tokens == 1000
    assert agent.config.retry_attempts == 2

@pytest.mark.rewrite
def test_system_prompt():
    """Test system prompt management"""
    agent = GreetingAgent()
    
    # Test getting system prompt
    assert agent.system_prompt
    
    # Test setting system prompt
    new_prompt = "You are a new greeting expert with different instructions."
    agent.system_prompt = new_prompt
    assert agent.system_prompt == new_prompt

@pytest.mark.rewrite
def test_error_handling():
    """Test error handling and retries"""
    # Create agent with minimal retries
    config = AgentConfig()
    config.retry_attempts = 1
    agent = GreetingAgent(config=config)
    
    # Test with invalid prompt (should raise after retries)
    with pytest.raises(ValueError):
        agent.run_sync(
            user_prompt="",  # Empty prompt should fail
            deps=GreetingInput(language="", formality="")
        )

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 