"""Error handling utilities."""

from typing import Optional, Any, Dict
from functools import wraps
import traceback

from .logging import get_logger
from .metrics import track_error


class AgentError(Exception):
    """Base exception for agent errors."""
    
    def __init__(
        self,
        message: str,
        agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.agent = agent
        self.context = context or {}
        super().__init__(message)


class DatabaseError(AgentError):
    """Database operation error."""
    pass


class LLMError(AgentError):
    """LLM invocation error."""
    pass


class ToolExecutionError(AgentError):
    """Tool execution error."""
    
    def __init__(
        self,
        message: str,
        tool: str,
        context: Optional[Dict[str, Any]] = None
    ):
        self.tool = tool
        super().__init__(message, context=context)


def handle_error(
    error: Exception,
    agent: Optional[str] = None,
    user_id: Optional[str] = None,
    **context
) -> str:
    """
    Handle and log error with context.
    
    Args:
        error: Exception that occurred
        agent: Agent where error occurred
        user_id: Optional user ID
        **context: Additional context
        
    Returns:
        User-friendly error message
    """
    logger = get_logger(__name__)
    
    error_type = type(error).__name__
    track_error(error_type)
    
    logger.error(
        f"Error in {agent or 'system'}: {str(error)}",
        error=error,
        agent=agent,
        user_id=user_id,
        error_type=error_type,
        traceback=traceback.format_exc(),
        **context
    )
    
    # Return user-friendly message
    if isinstance(error, AgentError):
        return error.message
    elif isinstance(error, TimeoutError):
        return "Request timed out. Please try again."
    elif isinstance(error, ConnectionError):
        return "Service temporarily unavailable. Please try again."
    else:
        return "An unexpected error occurred. Our team has been notified."


def with_error_handling(agent: str):
    """Decorator for error handling in agent methods."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return handle_error(e, agent=agent)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return handle_error(e, agent=agent)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

