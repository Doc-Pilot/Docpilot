# Importing Dependencies
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Optional, Dict, Any, Callable, Type, Union
from ..utils.logging import logger
from ..utils.config import get_settings

# Define a single generic type for both dependencies and results
ModelType = TypeVar('ModelType')

@dataclass
class AgentConfig:
    """Configuration for AI agents"""
    def __init__(self):
        settings = get_settings()
        self.model_name = settings.default_model
        self.temperature = settings.model_temperature
        self.max_tokens = settings.max_tokens
        self.retry_attempts = settings.retry_attempts

class BaseAgent(Generic[ModelType]):
    """Base class for all AI agents"""
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        system_prompt: str = "",
        model_type: Optional[Type[ModelType]] = None
    ):
        self.config = config or AgentConfig()
        self.model_type = model_type
        
        # Log agent initialization
        logger.info(
            "Initializing agent",
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            retry_attempts=self.config.retry_attempts
        )
        
        # Initialize the Pydantic AI agent with Logfire instrumentation
        self.agent = Agent(
            model=self.config.model_name,
            result_type=self.model_type,
            system_prompt=system_prompt,
            instrument=True  # Enable Logfire instrumentation
        )
    
    def tool(self, func: Callable) -> Callable:
        """Decorator for registering tools with the agent"""
        logger.debug(f"Registering tool: {func.__name__}")
        return self.agent.tool(func)
    
    async def run(
        self,
        user_prompt: str,
        deps: Optional[ModelType] = None,
        **kwargs: Dict[str, Any]
    ) -> ModelType:
        """Run the agent with the given prompt and dependencies"""
        try:
            # Log the start of the run with detailed context
            logger.info(
                "Starting agent run",
                prompt_length=len(user_prompt),
                has_dependencies=deps is not None,
                model=self.config.model_name,
                temperature=self.config.temperature,
                **kwargs
            )
            
            # Run the agent with proper context handling
            result = await self.agent.run(
                user_prompt=user_prompt,
                deps=deps,
                **kwargs
            )
            
            # Log successful completion
            logger.info(
                "Agent run completed successfully",
                result_type=type(result.data).__name__
            )
            
            return result.data
                
        except Exception as e:
            # Log error with detailed context
            logger.error(
                "Agent run failed",
                error=str(e),
                error_type=type(e).__name__,
                retry_attempts_remaining=self.config.retry_attempts,
                model=self.config.model_name
            )
            
            if self.config.retry_attempts > 0:
                self.config.retry_attempts -= 1
                logger.info(
                    f"Retrying run",
                    attempts_remaining=self.config.retry_attempts,
                    model=self.config.model_name
                )
                return await self.run(user_prompt, deps, **kwargs)
            raise
    
    def run_sync(
        self,
        user_prompt: str,
        deps: Optional[ModelType] = None
    ) -> ModelType:
        """Run the agent synchronously and return typed result"""
        # Validate user prompt is not empty
        if not user_prompt or not user_prompt.strip():
            logger.error("Empty prompt provided")
            raise ValueError("User prompt cannot be empty")
            
        # Log the start of the synchronous run
        logger.info(
            "Starting synchronous agent run",
            prompt_length=len(user_prompt),
            has_dependencies=deps is not None,
            model=self.config.model_name
        )
        
        # Run the agent synchronously
        result = self.agent.run_sync(
            user_prompt=user_prompt,
            deps=deps
        )
        
        # Log successful completion
        logger.info(
            "Synchronous agent run completed successfully",
            result_type=type(result.data).__name__
        )
        
        return result.data
    
    @property
    def system_prompt(self) -> str:
        """Get the current system prompt"""
        return self.agent.system_prompt
    
    @system_prompt.setter
    def system_prompt(self, value: str):
        """Update the system prompt"""
        logger.info(
            "Updating system prompt",
            prompt_length=len(value),
            model=self.config.model_name
        )
        self.agent.system_prompt = value 