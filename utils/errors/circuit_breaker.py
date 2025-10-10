"""
Circuit breaker pattern implementation.

Prevents cascading failures by stopping requests to failing services.
"""

import asyncio
import time
from typing import Optional, Callable, Any, Dict
from enum import Enum
from dataclasses import dataclass
from functools import wraps

from .exceptions import CircuitBreakerError
from utils.monitoring import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: int = 60  # Seconds before attempting recovery
    half_open_max_calls: int = 3  # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.
    
    Features:
    - Automatic failure detection
    - Temporary service blocking
    - Gradual recovery testing
    - Metrics tracking
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_rejected = 0
    
    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset to half-open."""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout
    
    def _record_success(self):
        """Record successful call."""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0
    
    def _record_failure(self):
        """Record failed call."""
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (failure)")
            self.state = CircuitState.OPEN
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            
            if self.failure_count >= self.config.failure_threshold:
                logger.warning(
                    f"Circuit breaker {self.name}: CLOSED -> OPEN "
                    f"({self.failure_count} failures)"
                )
                self.state = CircuitState.OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
        """
        self.total_calls += 1
        
        # Check if should attempt reset
        if self._should_attempt_reset():
            logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (timeout)")
            self.state = CircuitState.HALF_OPEN
            self.half_open_calls = 0
        
        # Check state
        if self.state == CircuitState.OPEN:
            self.total_rejected += 1
            raise CircuitBreakerError(
                f"Circuit breaker {self.name} is OPEN"
            )
        
        # Limit calls in half-open state
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                self.total_rejected += 1
                raise CircuitBreakerError(
                    f"Circuit breaker {self.name} is HALF_OPEN (max calls reached)"
                )
            self.half_open_calls += 1
        
        # Execute function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure()
            raise
    
    def get_state(self) -> str:
        """Get current state."""
        return self.state.value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_rejected": self.total_rejected,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
        }
    
    def reset(self):
        """Manually reset circuit breaker."""
        logger.info(f"Circuit breaker {self.name}: Manual reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0


# Global circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create circuit breaker.
    
    Args:
        name: Circuit breaker name
        config: Optional configuration
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    
    return _circuit_breakers[name]


# Decorator
def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: int = 60
):
    """
    Decorator to wrap function with circuit breaker.
    
    Usage:
        @circuit_breaker("external_api", failure_threshold=3)
        async def call_external_api():
            # May fail
            pass
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout=timeout
    )
    breaker = get_circuit_breaker(name, config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                breaker.call(func, *args, **kwargs)
            )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

