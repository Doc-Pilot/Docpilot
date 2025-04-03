"""
Base Agent Module
===============

This module defines the base Agent class that all specialized agents inherit from.
It provides common functionality for agent configuration, execution, token tracking,
cost calculation, logging, and tool calling.
"""

# Importing Dependencies
import os
import time
import uuid
import asyncio
import inspect
from typing import Any, Dict, Optional, TypeVar

import logfire
from pydantic import BaseModel, Field, model_validator
import logging

# Import utility classes and functions
from ..utils import log_completion
from ..utils.costs import TokenUsage, extract_usage_from_result
from ..utils.metrics import record_token_usage, record_performance_metric, start_operation, end_operation

# Type variables for generic typing
T = TypeVar('T')

class AgentConfig(BaseModel):
    """Configuration for agents"""
    model_name: str = Field(default="openai:gpt-4o-mini", description="The model name to use")
    temperature: float = Field(default=0.0, description="Model temperature")
    max_tokens: int = Field(default=4096, description="Maximum tokens for the response")
    retries: int = Field(default=3, description="Number of retries for API failures")
    timeout: float = Field(default=60.0, description="Timeout in seconds for API calls")
    log_to_logfire: bool = Field(default=True, description="Whether to log to Logfire")
    log_level: str = Field(default="INFO", description="Logging level")

class TaskResult(BaseModel):
    """Result of a task execution"""
    success: bool = True
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    
    @model_validator(mode="after")
    def set_total_tokens(self) -> "TaskResult":
        """Ensure total_tokens is set"""
        if self.tokens.total_tokens == 0 and (self.tokens.prompt_tokens > 0 or self.tokens.completion_tokens > 0):
            self.tokens.total_tokens = self.tokens.prompt_tokens + self.tokens.completion_tokens
        return self

class BaseAgent:
    """
    Base class for all Docpilot agents.
    
    This class provides common functionality for agent configuration,
    execution tracking, token tracking, logging, and tool calling.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        """
        Initialize the base agent.
        
        Args:
            config: Agent configuration
            **kwargs: Additional arguments for specialized agents
        """
        # Set up agent configuration
        self.config = config or AgentConfig()
        
        # Initialize token tracking
        self.total_tokens = 0
        self.total_cost = 0.0
        self._last_usage = TokenUsage()
        
        # Initialize logger
        self.logger = self._get_logger()
        self._setup_logfire()
        
        # Generate a unique agent ID
        self.agent_id = str(uuid.uuid4())[:8]
        
        # Initialize metrics
        self.metrics = {
            "operations": {},
            "tokens": {}
        }
        
        # Log initialization
        if self.config.log_to_logfire:
            self._log_completion(
                operation="initialization",
                success=True,
                model=None,
                tokens=0,
                cost=0.0,
                duration=0.0
            )
    
    def _setup_logfire(self) -> None:
        """Set up Logfire integration if enabled"""
        if not self.config.log_to_logfire:
            return
            
        try:
            # Get token from environment
            token = os.environ.get("LOGFIRE_TOKEN")
            if not token:
                self.logger.warning("LOGFIRE_TOKEN not found in environment variables, disabling Logfire logging")
                self.config.log_to_logfire = False
                return
                
            # Configure Logfire
            try:
                logfire.configure(
                    token=token,
                    service_name=os.environ.get("SERVICE_NAME", "docpilot"),
                    environment=os.environ.get("APP_ENV", "development")
                )
                self.logger.info("Logfire configured successfully")
            except Exception as e:
                self.logger.warning(f"Failed to configure Logfire: {str(e)}")
                self.config.log_to_logfire = False
                return
            
            # Test if we can get a logger
            try:
                if hasattr(logfire, 'getLogger'):
                    logfire.getLogger()
                elif hasattr(logfire, 'get_logger'):
                    logfire.get_logger()
                else:
                    self.logger.warning("Logfire has no logger method, disabling Logfire logging")
                    self.config.log_to_logfire = False
                    return
            except Exception as e:
                self.logger.warning(f"Failed to get Logfire logger: {str(e)}")
                self.config.log_to_logfire = False
                return
                
            # Instrument pydantic for validation (optional)
            try:
                if hasattr(logfire, 'instrument_pydantic_ai'):
                    logfire.instrument_pydantic_ai()
            except (AttributeError, Exception):
                # This is optional, so we don't need to disable Logfire if it fails
                pass
        except Exception as e:
            self.logger.warning(f"Failed to set up Logfire: {str(e)}")
            self.config.log_to_logfire = False
    
    def _get_logger(self):
        """Get a properly configured logger for the agent"""
        # Get agent class name for logger name
        logger_name = f"docpilot.agents.{self.__class__.__name__}"
        
        # Create and configure logger
        logger = logging.getLogger(logger_name)
        
        # Set level from config
        level = getattr(logging, self.config.log_level, logging.INFO)
        logger.setLevel(level)
        
        # Add handler if not already set up
        if not logger.handlers and not logging.getLogger().handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _log_completion(
        self,
        operation: str,
        success: bool,
        model: Optional[str] = None,
        tokens: int = 0,
        cost: float = 0.0,
        duration: float = 0.0,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a single entry when an agent operation completes.
        
        Args:
            operation: Operation performed
            success: Whether the operation succeeded
            model: LLM model used
            tokens: Number of tokens used
            cost: Cost of the operation
            duration: Duration in seconds
            error: Error message if operation failed
            details: Additional details to include in the log
        """
        # Always log to standard logger
        if success:
            self.logger.info(f"{operation} completed successfully")
        else:
            self.logger.error(f"{operation} failed: {error or ''}")
        
        # Skip logfire logging if disabled
        if not self.config.log_to_logfire:
            return
            
        try:
            # Build complete log data
            log_data = {
                "component": self.__class__.__name__,
                "operation": operation,
                "success": success,
                "agent_id": self.agent_id
            }
            
            # Add optional fields if they have values
            if model:
                log_data["model"] = model
            if tokens > 0:
                log_data["tokens"] = tokens
            if cost > 0:
                log_data["cost"] = round(cost, 6)
            if duration > 0:
                log_data["duration"] = round(duration, 3)
            if error:
                log_data["error"] = error
            if details:
                log_data.update(details)
            
            # Get logfire logger
            logger = None
            
            # Try different methods to get the logger based on what's available
            if hasattr(logfire, 'getLogger'):
                logger = logfire.getLogger()
            elif hasattr(logfire, 'get_logger'):
                logger = logfire.get_logger()
            
            # If we couldn't get a logger, log a warning and return
            if logger is None:
                self.logger.warning("Failed to get Logfire logger - no suitable method found")
                return
            
            # Log the entry with appropriate level based on success
            try:
                if success:
                    logger.info(f"{self.__class__.__name__}.{operation} completed", **log_data)
                else:
                    logger.error(f"{self.__class__.__name__}.{operation} failed", **log_data)
            except TypeError as te:
                # If the logger doesn't accept keyword arguments, try a simpler approach
                message = f"{self.__class__.__name__}.{operation} {'completed' if success else 'failed'} - {log_data}"
                if success:
                    logger.info(message)
                else:
                    logger.error(message)
        except Exception as e:
            # Log the issue but don't crash
            self.logger.warning(f"Failed to log to Logfire: {str(e)}")
    
    def run(self, method_name: str, *args, **kwargs) -> TaskResult:
        """
        Run an agent method and collect metrics.
        
        Args:
            method_name: The method name to execute
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            The method result wrapped in a TaskResult
        """
        # Set up timer for duration tracking
        start_time = time.time()
        
        # Start operation tracking
        operation_id = start_operation(method_name, {
            "agent_type": self.__class__.__name__,
            "agent_id": self.agent_id,
            "model": self.config.model_name
        })
        
        try:
            # Find and execute the method
            if not hasattr(self, method_name):
                raise AttributeError(f"Method {method_name} not found in {self.__class__.__name__}")
            
            method = getattr(self, method_name)
            if not callable(method):
                raise TypeError(f"{method_name} is not a callable method")
            
            # Execute the method
            result = method(*args, **kwargs)
            
            # Extract usage data if available
            usage = extract_usage_from_result(result)
            
            # Calculate cost
            cost = usage.calculate_cost(self.config.model_name)
            
            # Update total token usage
            self.total_tokens += usage.total_tokens
            self.total_cost += cost
            
            # Record token metrics
            if usage.total_tokens > 0:
                record_token_usage(
                    model_name=self.config.model_name,
                    usage=usage,
                    cost=cost,
                    operation=method_name
                )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record performance metric
            record_performance_metric(f"{self.__class__.__name__}.{method_name}", duration, {
                "success": True,
                "tokens": usage.total_tokens,
                "cost": cost
            })
            
            # Log completion with metrics
            self._log_completion(
                operation=method_name,
                model=self.config.model_name,
                success=True,
                tokens=usage.total_tokens,
                cost=cost,
                duration=duration
            )
            
            # End operation tracking
            end_operation(operation_id, True, {
                "tokens": usage.total_tokens,
                "cost": cost,
                "duration": duration
            })
            
            # Return the task result
            return TaskResult(
                success=True,
                result=result,
                duration=duration,
                tokens=usage
            )
            
        except Exception as e:
            # Calculate duration even on error
            duration = time.time() - start_time
            
            # Record performance metric for failure
            record_performance_metric(f"{self.__class__.__name__}.{method_name}", duration, {
                "success": False,
                "error": str(e)
            })
            
            # Record a zero-token usage for this operation to ensure it appears in metrics
            # This is important for tracking error operations
            record_token_usage(
                model_name=self.config.model_name,
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                cost=0.0,
                operation=method_name
            )
            
            # Log the error
            error_msg = str(e)
            self._log_completion(
                operation=method_name,
                model=self.config.model_name,
                success=False,
                duration=duration,
                error=error_msg
            )
            
            # End operation tracking
            end_operation(operation_id, False, {
                "error": error_msg,
                "duration": duration
            })
            
            # Return error information
            return TaskResult(
                success=False,
                error=error_msg,
                duration=duration
            )
    
    async def run_async(self, method_name: str, *args, **kwargs) -> TaskResult:
        """
        Run an agent method asynchronously and collect metrics.
        
        Args:
            method_name: The method name to execute
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            The method result wrapped in a TaskResult
        """
        # Set up timer for duration tracking
        start_time = time.time()
        
        # Start operation tracking
        operation_id = start_operation(method_name, {
            "agent_type": self.__class__.__name__,
            "agent_id": self.agent_id,
            "model": self.config.model_name,
            "async": True
        })
        
        try:
            # Find and execute the method
            if not hasattr(self, method_name):
                raise AttributeError(f"Method {method_name} not found in {self.__class__.__name__}")
            
            method = getattr(self, method_name)
            if not callable(method):
                raise TypeError(f"{method_name} is not a callable method")
            
            # Check if method is async
            if inspect.iscoroutinefunction(method):
                # Execute async method
                result = await method(*args, **kwargs)
            else:
                # Run sync method in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: method(*args, **kwargs)
                )
            
            # Extract usage data if available
            usage = extract_usage_from_result(result)
            
            # Calculate cost
            cost = usage.calculate_cost(self.config.model_name)
            
            # Update total token usage
            self.total_tokens += usage.total_tokens
            self.total_cost += cost
            
            # Record token metrics
            if usage.total_tokens > 0:
                record_token_usage(
                    model_name=self.config.model_name,
                    usage=usage,
                    cost=cost,
                    operation=method_name
                )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record performance metric
            record_performance_metric(f"{self.__class__.__name__}.{method_name}", duration, {
                "success": True,
                "tokens": usage.total_tokens,
                "cost": cost,
                "async": True
            })
            
            # Log completion with metrics
            self._log_completion(
                operation=method_name,
                model=self.config.model_name,
                success=True,
                tokens=usage.total_tokens,
                cost=cost,
                duration=duration
            )
            
            # End operation tracking
            end_operation(operation_id, True, {
                "tokens": usage.total_tokens,
                "cost": cost,
                "duration": duration,
                "async": True
            })
            
            # Return the task result
            return TaskResult(
                success=True,
                result=result,
                duration=duration,
                tokens=usage
            )
            
        except Exception as e:
            # Calculate duration even on error
            duration = time.time() - start_time
            
            # Record performance metric for failure
            record_performance_metric(f"{self.__class__.__name__}.{method_name}", duration, {
                "success": False,
                "error": str(e),
                "async": True
            })
            
            # Record a zero-token usage for this operation to ensure it appears in metrics
            # This is important for tracking error operations
            record_token_usage(
                model_name=self.config.model_name,
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                cost=0.0,
                operation=method_name
            )
            
            # Log the error
            error_msg = str(e)
            self._log_completion(
                operation=method_name,
                model=self.config.model_name,
                success=False,
                duration=duration,
                error=error_msg
            )
            
            # End operation tracking
            end_operation(operation_id, False, {
                "error": error_msg,
                "duration": duration,
                "async": True
            })
            
            # Return error information
            return TaskResult(
                success=False,
                error=error_msg,
                duration=duration
            )
    
    async def run_tool(self, tool_name: str, arguments: Dict[str, Any]) -> TaskResult:
        """
        Run a tool by name with the given arguments.
        
        Args:
            tool_name: The name of the tool to run
            arguments: Arguments to pass to the tool
            
        Returns:
            The tool result wrapped in a TaskResult
        """
        # Set up timer for duration tracking
        start_time = time.time()
        
        # Create full operation name
        operation_name = f"tool_{tool_name}"
        
        # Start operation tracking
        operation_id = start_operation(operation_name, {
            "agent_type": self.__class__.__name__,
            "agent_id": self.agent_id,
            "arguments": arguments
        })
        
        try:
            # Find and execute the tool
            tool_method_name = operation_name
            if not hasattr(self, tool_method_name):
                raise AttributeError(f"Tool {tool_name} not found in {self.__class__.__name__}")
            
            tool_method = getattr(self, tool_method_name)
            if not callable(tool_method):
                raise TypeError(f"{tool_method_name} is not a callable method")
            
            # Check if tool is async
            if inspect.iscoroutinefunction(tool_method):
                # Execute async tool
                result = await tool_method(**arguments)
            else:
                # Run sync tool in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: tool_method(**arguments)
                )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record performance metric
            record_performance_metric(operation_name, duration, {
                "success": True,
                "arguments": arguments
            })
            
            # Log tool execution
            self._log_completion(
                operation=operation_name,
                success=True,
                duration=duration,
                details={"arguments": arguments}
            )
            
            # End operation tracking
            end_operation(operation_id, True, {
                "duration": duration,
                "result_type": type(result).__name__
            })
            
            # Return the task result
            return TaskResult(
                success=True,
                result=result,
                duration=duration
            )
            
        except Exception as e:
            # Calculate duration even on error
            duration = time.time() - start_time
            
            # Record performance metric for failure
            record_performance_metric(operation_name, duration, {
                "success": False,
                "error": str(e),
                "arguments": arguments
            })
            
            # Record a zero-token usage for this tool operation
            record_token_usage(
                model_name=self.config.model_name,
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                cost=0.0,
                operation=operation_name
            )
            
            # Log the error
            error_msg = str(e)
            self._log_completion(
                operation=operation_name,
                success=False,
                duration=duration,
                error=error_msg,
                details={"arguments": arguments}
            )
            
            # End operation tracking
            end_operation(operation_id, False, {
                "error": error_msg,
                "duration": duration
            })
            
            # Return error information
            return TaskResult(
                success=False,
                error=error_msg,
                duration=duration
            )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for this agent.
        
        Returns:
            Dictionary with token usage and cost statistics
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "model": self.config.model_name,
            "agent_id": self.agent_id,
            "agent_type": self.__class__.__name__
        }
    
    # Context manager support for better resource management
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        # Log final stats
        if self.config.log_to_logfire and self.total_tokens > 0:
            self._log_completion(
                operation="session_complete",
                success=exc_type is None,
                tokens=self.total_tokens,
                cost=self.total_cost,
                details={
                    "duration": time.time() - getattr(self, "_session_start_time", time.time()),
                    "error": str(exc_val) if exc_val else None
                }
            )