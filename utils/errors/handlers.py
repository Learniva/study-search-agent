"""Error handling utilities and decorators."""

import asyncio
import traceback
from typing import Optional, Callable, Any, TypeVar, Dict
from functools import wraps

from .exceptions import BaseApplicationError, TimeoutError as AppTimeoutError
from utils.monitoring import get_logger, track_error

logger = get_logger(__name__)
T = TypeVar('T')


class ErrorHandler:
    """
    Centralized error handling.
    
    Features:
    - Error logging
    - Error tracking
    - Error transformation
    - Retry logic
    """
    
    def __init__(self):
        self.error_count = 0
        self.error_history: list = []
        self.max_history = 100
    
    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log error with context.
        
        Args:
            error: Exception to log
            context: Additional context
        """
        self.error_count += 1
        
        # Track in history
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "context": context or {},
            "traceback": traceback.format_exc(),
        }
        
        self.error_history.append(error_info)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
        
        # Log error
        if isinstance(error, BaseApplicationError):
            logger.error(
                f"{error.error_code}: {error.message}",
                extra={
                    "error_code": error.error_code,
                    "status_code": error.status_code,
                    "details": error.details,
                    "context": context,
                }
            )
        else:
            logger.error(
                f"{type(error).__name__}: {str(error)}",
                extra={"context": context},
                exc_info=True
            )
        
        # Track for monitoring
        error_type = type(error).__name__
        track_error(error_type)
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        default_response: Any = None
    ) -> Any:
        """
        Handle error and return response.
        
        Args:
            error: Exception to handle
            context: Additional context
            default_response: Default response on error
            
        Returns:
            Error response or default
        """
        self.log_error(error, context)
        
        if isinstance(error, BaseApplicationError):
            return error.to_dict()
        
        # Generic error response
        return {
            "error": "INTERNAL_ERROR",
            "message": "An internal error occurred",
            "status_code": 500,
        } if default_response is None else default_response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        error_types = {}
        for error in self.error_history:
            error_type = error["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_errors": self.error_count,
            "recent_errors": len(self.error_history),
            "error_types": error_types,
        }


# Global error handler
_global_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get or create global error handler."""
    global _global_handler
    if _global_handler is None:
        _global_handler = ErrorHandler()
    return _global_handler


# Decorators
def handle_errors(
    default_response: Any = None,
    log_errors: bool = True,
    raise_on_error: bool = False
):
    """
    Decorator to handle errors in functions.
    
    Usage:
        @handle_errors(default_response="Error occurred")
        async def my_function():
            # May raise errors
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    handler = get_error_handler()
                    response = handler.handle_error(
                        e,
                        context={
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "kwargs": str(kwargs)[:100],
                        },
                        default_response=default_response
                    )
                
                if raise_on_error:
                    raise
                
                return response if log_errors else default_response
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    handler = get_error_handler()
                    response = handler.handle_error(
                        e,
                        context={
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "kwargs": str(kwargs)[:100],
                        },
                        default_response=default_response
                    )
                
                if raise_on_error:
                    raise
                
                return response if log_errors else default_response
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry function on error.
    
    Usage:
        @retry_on_error(max_retries=3, delay=1.0)
        async def unreliable_function():
            # May fail sometimes
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after error: {str(e)}"
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after error: {str(e)}"
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def timeout(seconds: int):
    """
    Decorator to add timeout to async functions.
    
    Usage:
        @timeout(30)
        async def slow_function():
            await asyncio.sleep(60)  # Will timeout
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise AppTimeoutError(
                    f"Function {func.__name__} exceeded {seconds}s timeout",
                    timeout_seconds=seconds
                )
        
        return wrapper
    
    return decorator

