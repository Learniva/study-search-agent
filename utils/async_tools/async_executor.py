"""
Async tool execution with proper resource management.

Handles synchronous tools in async context with thread pools.
"""

import asyncio
from typing import Any, Callable, Optional, Dict
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time

from config import settings
from utils.monitoring import get_logger

logger = get_logger(__name__)


class AsyncToolExecutor:
    """
    Async executor for synchronous tools.
    
    Features:
    - Thread pool for I/O-bound operations
    - Process pool for CPU-bound operations
    - Timeout handling
    - Resource cleanup
    - Performance tracking
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        timeout: int = None
    ):
        """
        Initialize async tool executor.
        
        Args:
            max_workers: Max threads/processes (default: from settings)
            timeout: Default timeout in seconds (default: from settings)
        """
        self.max_workers = max_workers or settings.max_concurrent_requests
        self.timeout = timeout or settings.request_timeout
        
        # Thread pool for I/O-bound tasks
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="tool_"
        )
        
        # Process pool for CPU-bound tasks (optional)
        self.process_pool = None
        
        # Performance tracking
        self.execution_count = 0
        self.total_time = 0.0
        self.timeouts = 0
        self.errors = 0
    
    async def run_sync_tool(
        self,
        func: Callable,
        *args,
        timeout: Optional[int] = None,
        use_process_pool: bool = False,
        **kwargs
    ) -> Any:
        """
        Run synchronous tool function in async context.
        
        Args:
            func: Synchronous function to run
            *args: Positional arguments
            timeout: Custom timeout (overrides default)
            use_process_pool: Use process pool for CPU-bound tasks
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            TimeoutError: If execution exceeds timeout
        """
        start_time = time.time()
        timeout_val = timeout or self.timeout
        
        try:
            # Choose executor
            executor = self.process_pool if use_process_pool else self.thread_pool
            
            # Create partial function with args
            partial_func = partial(func, *args, **kwargs)
            
            # Run in executor with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(executor, partial_func),
                timeout=timeout_val
            )
            
            # Track metrics
            execution_time = time.time() - start_time
            self.execution_count += 1
            self.total_time += execution_time
            
            logger.debug(
                f"Tool {func.__name__} executed in {execution_time:.2f}s"
            )
            
            return result
            
        except asyncio.TimeoutError:
            self.timeouts += 1
            logger.warning(
                f"Tool {func.__name__} timeout after {timeout_val}s"
            )
            raise TimeoutError(
                f"Tool {func.__name__} exceeded {timeout_val}s timeout"
            )
        
        except Exception as e:
            self.errors += 1
            logger.error(f"Tool {func.__name__} error: {e}")
            raise
    
    async def run_multiple(
        self,
        tasks: Dict[str, tuple[Callable, tuple, dict]],
        return_exceptions: bool = False
    ) -> Dict[str, Any]:
        """
        Run multiple tools concurrently.
        
        Args:
            tasks: Dict of {name: (func, args, kwargs)}
            return_exceptions: Return exceptions instead of raising
            
        Returns:
            Dict of {name: result}
        """
        # Create async tasks
        async_tasks = {
            name: self.run_sync_tool(func, *args, **kwargs)
            for name, (func, args, kwargs) in tasks.items()
        }
        
        # Run concurrently
        if return_exceptions:
            results = await asyncio.gather(
                *async_tasks.values(),
                return_exceptions=True
            )
        else:
            results = await asyncio.gather(*async_tasks.values())
        
        # Map results back to names
        return dict(zip(async_tasks.keys(), results))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        avg_time = (
            self.total_time / self.execution_count 
            if self.execution_count > 0 
            else 0
        )
        
        return {
            "total_executions": self.execution_count,
            "total_time_seconds": round(self.total_time, 2),
            "average_time_seconds": round(avg_time, 2),
            "timeouts": self.timeouts,
            "errors": self.errors,
            "max_workers": self.max_workers,
            "default_timeout": self.timeout,
        }
    
    async def cleanup(self):
        """Cleanup executors and free resources."""
        logger.info("Cleaning up tool executors...")
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        # Shutdown process pool if initialized
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        
        logger.info("Tool executors cleaned up")
    
    def __del__(self):
        """Ensure cleanup on deletion."""
        try:
            asyncio.create_task(self.cleanup())
        except RuntimeError:
            # Event loop might be closed
            pass


# Global executor instance
_global_executor: Optional[AsyncToolExecutor] = None


def get_async_executor() -> AsyncToolExecutor:
    """Get or create global async tool executor."""
    global _global_executor
    if _global_executor is None:
        _global_executor = AsyncToolExecutor()
    return _global_executor


async def run_sync_in_executor(
    func: Callable,
    *args,
    timeout: Optional[int] = None,
    **kwargs
) -> Any:
    """
    Convenience function to run sync function in async context.
    
    Usage:
        result = await run_sync_in_executor(sync_function, arg1, arg2)
    """
    executor = get_async_executor()
    return await executor.run_sync_tool(func, *args, timeout=timeout, **kwargs)


# Decorator for making sync tools async
def async_tool(timeout: Optional[int] = None):
    """
    Decorator to wrap synchronous tool as async.
    
    Usage:
        @async_tool(timeout=30)
        def my_sync_tool(query: str) -> str:
            return process(query)
        
        # Can now be awaited
        result = await my_sync_tool("query")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await run_sync_in_executor(
                func, *args, timeout=timeout, **kwargs
            )
        
        # Preserve original function
        async_wrapper.__wrapped__ = func
        return async_wrapper
    
    return decorator


