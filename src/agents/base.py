"""
Base Agent Module
================

This module provides the base agent class using Pydantic AI's Agent framework,
with typed dependencies and structured results.
"""

import time
import asyncio
from dataclasses import dataclass
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import TypeVar, Generic, Optional, Any, Callable, Type, ClassVar

from ..utils import logger, get_settings, extract_usage_from_result, Usage

# Define types for dependency injection and results
DepsT = TypeVar('DepsT')
ResultT = TypeVar('ResultT', bound=BaseModel)

# Settings
settings = get_settings()

@dataclass
class AgentConfig:
    """Configuration for AI agents"""
    model_name: str = settings.default_model
    temperature: float = settings.model_temperature
    max_tokens: int = settings.max_tokens
    retry_attempts: int = settings.retry_attempts
    retry_base_delay: float = 1.0  # Base delay for exponential backoff in seconds
    max_retry_delay: float = 60.0  # Maximum delay between retries in seconds

class AgentResult(BaseModel, Generic[ResultT]):
    """
    Standard result container for all agent runs.
    
    Contains both the agent-specific result data and usage information.
    """
    data: ResultT
    usage: Usage
    
    @property
    def total_tokens(self) -> int:
        """Get the total tokens used"""
        return self.usage.total_tokens
    
    @property
    def model(self) -> str:
        """Get the model used for this run"""
        return self.usage.model
        
    @property
    def cost(self) -> float:
        """Get the cost of this run"""
        return self.usage.cost
    
    @classmethod
    def create(cls, result: Any, model_name: str) -> "AgentResult":
        """Create an AgentResult from a Pydantic AI result"""
        # Extract the structured data from the result
        data = result.data
        
        # Extract usage metrics
        usage = extract_usage_from_result(result, model_name)
        
        # Ensure usage is a valid Usage object
        if usage is None:
            usage = Usage(model=model_name)
        
        return cls(data=data, usage=usage)

class BaseAgent(Generic[DepsT, ResultT]):
    """
    Base class for all AI agents following the Pydantic AI pattern.
    
    Uses dataclasses for dependencies and Pydantic models for results.
    Provides consistent token tracking, cost calculation, and logging.
    """
    
    # Class variables for agent configuration
    deps_type: ClassVar[Optional[Type[DepsT]]] = None
    result_type: ClassVar[Optional[Type[ResultT]]] = None
    default_system_prompt: ClassVar[str] = ""
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        system_prompt: Optional[str] = None,
        deps_type: Optional[Type[DepsT]] = None,
        result_type: Optional[Type[ResultT]] = None
    ):
        """
        Initializes the agent with the provided configuration.

        This constructor sets up an instance of the BaseAgent class, allowing for customized initialization 
        based on the provided configuration parameters. It may be used to configure the agent's behavior, 
        prompts, and dependencies.

        Args:
            config (Optional[AgentConfig]): An optional configuration object that specifies agent settings. 
                If not provided, defaults to None.
            system_prompt (Optional[str]): An optional string that sets the system prompt for the agent. 
                If not provided, defaults to None.
            deps_type (Optional[Type[DepsT]]): An optional parameter to specify the type of dependencies for the agent. 
                If not provided, defaults to None.
            result_type (Optional[Type[ResultT]]): An optional parameter to define the result type expected from the agent. 
                If not provided, defaults to None.

        Returns:
            None: This method does not return a value.

        Examples:
            # Example of initializing the agent with a configuration object
            agent_config = AgentConfig(...)  # Assuming AgentConfig is defined elsewhere
            agent = BaseAgent(config=agent_config, system_prompt="Hello, how can I assist you?", deps_type=..., result_type=...)

            # Example of initializing the agent without any configuration
            agent = BaseAgent()
        """
        self.config = config or AgentConfig()
        self._deps_type = deps_type or self.deps_type
        self._result_type = result_type or self.result_type
        self._system_prompt = system_prompt or self.default_system_prompt
        self._name = self.__class__.__name__
        
        # Validate that we have a result type
        if not self._result_type:
            raise ValueError("Result type must be specified")
        
        # Initialize the Pydantic AI agent
        self.agent = Agent(
            model=self.config.model_name,
            deps_type=self._deps_type,
            result_type=self._result_type,
            system_prompt=self._system_prompt,
            instrument=True,
            model_settings={
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
        )
    
    @property
    def name(self) -> str:
        """Return the name of the agent."""
        return self._name

    def tool(self, func: Callable) -> Callable:
        """Register a tool function with the agent"""
        return self.agent.tool(func)
    
    def system_prompt_fn(self, func: Callable) -> Callable:
        """Register a dynamic system prompt function"""
        return self.agent.system_prompt(func)
    
    async def run(
        self,
        user_prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> AgentResult[ResultT]:
        """
        Run the agent with the given prompt and dependencies.
        
        Implements retry logic with exponential backoff for transient errors.
        Returns an AgentResult containing both the result data and usage metrics.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("User prompt cannot be empty")
            
        start_time = time.monotonic()
        attempts = 0
        last_exception = None
        
        while attempts < self.config.retry_attempts:
            try:
                # Run the agent
                result = await self.agent.run(
                    user_prompt=user_prompt,
                    deps=deps,
                    **kwargs
                )
                
                # Package the result with usage information
                agent_result = AgentResult.create(result, self.config.model_name)
                time_taken = time.monotonic() - start_time
                
                # Log only completion with key metrics
                logger.info(
                    "{agent_name} completed in {time_taken:.2f}s (tokens: {tokens}, cost: ${cost:.4f})",
                    agent_name=self.name,
                    tokens=agent_result.total_tokens,
                    cost=agent_result.cost,
                    time_taken=time_taken
                )
                
                return agent_result
                    
            except Exception as e:
                attempts += 1
                last_exception = e
                
                # Calculate retry delay with exponential backoff
                wait_time = min(
                    self.config.retry_base_delay * (2 ** (attempts - 1)), 
                    self.config.max_retry_delay
                )
                
                # Log warning about retry
                logger.warning(
                    "{agent_name} attempt {attempt}/{max_attempts} failed: {error}. Retrying in {wait_time:.2f}s",
                    agent_name=self.name,
                    attempt=attempts,
                    max_attempts=self.config.retry_attempts,
                    error=str(e),
                    wait_time=wait_time
                )
                
                # Don't wait if this was the last attempt
                if attempts < self.config.retry_attempts:
                    await asyncio.sleep(wait_time)
        
        # If all retries are exhausted, log and re-raise the exception
        time_taken = time.monotonic() - start_time
        logger.error(
            "{agent_name} failed after {attempts} attempts: {error}",
            agent_name=self.name,
            attempts=attempts,
            error=str(last_exception),
            time_taken=f"{time_taken:.2f}s",
            exc_info=True
        )
        
        raise last_exception
    
    def run_sync(
        self,
        user_prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> AgentResult[ResultT]:
        """
        Run the agent synchronously with retry logic.
        
        Returns an AgentResult containing both the result data and usage metrics.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("User prompt cannot be empty")
            
        start_time = time.monotonic()
        attempts = 0
        last_exception = None
        
        while attempts < self.config.retry_attempts:
            try:    
                # Run the agent synchronously
                result = self.agent.run_sync(
                    user_prompt=user_prompt,
                    deps=deps,
                    **kwargs
                )
                
                # Package the result with usage information
                agent_result = AgentResult.create(result, self.config.model_name)
                time_taken = time.monotonic() - start_time
                
                # Log only completion with key metrics
                logger.info(
                    "{agent_name} completed in {time_taken:.2f}s (tokens: {tokens}, cost: ${cost:.4f})",
                    agent_name=self.name,
                    tokens=agent_result.total_tokens,
                    cost=agent_result.cost,
                    time_taken=time_taken
                )
                
                return agent_result

            except Exception as e:
                attempts += 1
                last_exception = e
                
                # Calculate retry delay with exponential backoff
                wait_time = min(
                    self.config.retry_base_delay * (2 ** (attempts - 1)), 
                    self.config.max_retry_delay
                )
                
                # Log warning about retry
                logger.warning(
                    "{agent_name} attempt {attempt}/{max_attempts} failed: {error}. Retrying in {wait_time:.2f}s",
                    agent_name=self.name,
                    attempt=attempts,
                    max_attempts=self.config.retry_attempts,
                    error=str(e),
                    wait_time=wait_time
                )
                
                # Don't wait if this was the last attempt
                if attempts < self.config.retry_attempts:
                    time.sleep(wait_time)
        
        # If all retries are exhausted, log and re-raise the exception
        time_taken = time.monotonic() - start_time
        logger.error(
            "{agent_name} failed after {attempts} attempts: {error}",
            agent_name=self.name,
            attempts=attempts,
            error=str(last_exception),
            time_taken=f"{time_taken:.2f}s",
            exc_info=True
        )
        
        raise last_exception
    
    @property
    def system_prompt(self) -> str:
        """Get the current system prompt"""
        return self.agent.system_prompt
    
    @system_prompt.setter
    def system_prompt(self, value: str):
        """Update the system prompt"""
        self.agent.system_prompt = value