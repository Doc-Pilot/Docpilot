"""
Greeting Example
================

This example demonstrates how to generate greetings using DocPilot's agents.
"""
# Importing Dependencies
import os
import sys
from dataclasses import dataclass
from pydantic import BaseModel, Field

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.agents.base import BaseAgent, AgentConfig

# Define the input type as a dataclass
@dataclass
class GreetingInput:
    """Input for greeting generation"""
    language: str
    formality: str
    recipient: str = "everyone"

# Define the result type as a Pydantic model
class GreetingResult(BaseModel):
    """Result of greeting generation"""
    greeting: str = Field(description="The generated greeting")
    language: str = Field(description="The language of the greeting")
    formality: str = Field(description="The formality level (formal, casual)")

# Create the greeting agent
class GreetingAgent(BaseAgent[GreetingResult]):
    """Agent for generating greetings in different languages"""
    
    def __init__(self, config: AgentConfig = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt="""You are a greeting expert. Generate appropriate greetings based on the user's request.
            Consider the language and formality level specified.""",
            model_type=GreetingResult
        )

def main():
    # Create agent with default config
    agent = GreetingAgent()
    
    # Example 1: Generate a formal greeting in Spanish
    print("\nExample 1: Formal Spanish Greeting")
    input_data = GreetingInput(
        language="Spanish",
        formality="formal"
    )
    result = agent.run_sync(
        user_prompt="Generate a formal greeting in Spanish for " + input_data.recipient,
        deps=input_data
    )
    print(f"Greeting: {result.greeting}")
    print(f"Language: {result.language}")
    print(f"Formality: {result.formality}")
    
    # Example 2: Generate a casual greeting in French
    print("\nExample 2: Casual French Greeting")
    input_data = GreetingInput(
        language="French",
        formality="casual",
        recipient="friends"
    )
    result = agent.run_sync(
        user_prompt=f"Generate a casual greeting in {input_data.language} for {input_data.recipient}",
        deps=input_data
    )
    print(f"Greeting: {result.greeting}")
    print(f"Language: {result.language}")
    print(f"Formality: {result.formality}")

if __name__ == "__main__":
    main() 