"""
Base Agent Module
================

This module provides the base agent class using Pydantic AI's Agent framework,
with typed dependencies and structured results.
"""

from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Optional, Dict, Any, Callable, Type, ClassVar, AsyncGenerator
from ..utils.logging import logger
from ..utils.metrics import Usage, extract_usage_from_result
from ..utils.config import get_settings

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
        """Initialize the agent with configuration"""
        self.config = config or AgentConfig()
        self._deps_type = deps_type or self.deps_type
        self._result_type = result_type or self.result_type
        self._system_prompt = system_prompt or self.default_system_prompt
        
        # Validate that we have a result type
        if not self._result_type:
            raise ValueError("Result type must be specified")
        
        # Initialize the Pydantic AI agent
        self.agent = Agent(
            model=self.config.model_name,
            deps_type=self._deps_type,
            result_type=self._result_type,
            system_prompt=self._system_prompt,
            instrument=True,  # Enable instrumentation for metrics
            model_settings={
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
        )
        
        logger.debug(f"Initialized {self.__class__.__name__} with model {self.config.model_name}")
    
    def tool(self, func: Callable) -> Callable:
        """Register a tool function with the agent"""
        logger.debug(f"Registering tool: {func.__name__}")
        return self.agent.tool(func)
    
    def system_prompt_fn(self, func: Callable) -> Callable:
        """Register a dynamic system prompt function"""
        logger.debug(f"Registering system prompt function: {func.__name__}")
        return self.agent.system_prompt(func)
    
    async def run(
        self,
        user_prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> AgentResult[ResultT]:
        """
        Run the agent with the given prompt and dependencies.
        
        Returns an AgentResult containing both the result data and usage metrics.
        """
        try:
            logger.info(f"Running agent", model=self.config.model_name, prompt_length=len(user_prompt))
            
            # Run the agent
            result = await self.agent.run(
                user_prompt=user_prompt,
                deps=deps,
                **kwargs
            )
            
            # Package the result with usage information
            agent_result = AgentResult.create(result, self.config.model_name)
            
            # Log completion metrics
            logger.info(
                "Agent run completed",
                tokens=agent_result.total_tokens,
                cost=agent_result.cost,
                model=agent_result.model
            )
            
            return agent_result
                
        except Exception as e:
            logger.error(
                "Agent run failed",
                error=str(e),
                error_type=type(e).__name__,
                retry_attempts_remaining=self.config.retry_attempts
            )
            
            # Retry logic if configured
            if self.config.retry_attempts > 0:
                logger.info("Retrying agent run", attempts_remaining=self.config.retry_attempts)
                # Create new config with decremented retry attempts
                retry_config = AgentConfig(
                    model_name=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    retry_attempts=self.config.retry_attempts - 1
                )
                self.config = retry_config
                return await self.run(user_prompt, deps, **kwargs)
            
            # If no more retries, re-raise the exception
            raise
    
    def run_sync(
        self,
        user_prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> AgentResult[ResultT]:
        """
        Run the agent synchronously.
        
        Returns an AgentResult containing both the result data and usage metrics.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("User prompt cannot be empty")
            
        logger.info(f"Running agent synchronously", model=self.config.model_name)
            
        # Run the agent synchronously
        result = self.agent.run_sync(
            user_prompt=user_prompt,
            deps=deps,
            **kwargs
        )
        
        # Package the result with usage information
        agent_result = AgentResult.create(result, self.config.model_name)
        
        # Log completion
        logger.info(
            "Synchronous agent run completed",
            tokens=agent_result.total_tokens,
            cost=agent_result.cost,
            model=agent_result.model
        )
        
        return agent_result
    
    async def stream(
        self,
        user_prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream the agent's response"""
        logger.info(f"Streaming agent response", model=self.config.model_name)
        
        async for chunk in self.agent.stream(
            user_prompt=user_prompt,
            deps=deps,
            **kwargs
        ):
            yield chunk
    
    @property
    def system_prompt(self) -> str:
        """Get the current system prompt"""
        return self.agent.system_prompt
    
    @system_prompt.setter
    def system_prompt(self, value: str):
        """Update the system prompt"""
        logger.debug(f"Updating system prompt")
        self.agent.system_prompt = value 