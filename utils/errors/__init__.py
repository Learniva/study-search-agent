"""Comprehensive error handling framework."""

from .exceptions import (
    BaseApplicationError,
    AgentError,
    DatabaseError,
    CacheError,
    RateLimitError,
    AuthenticationError,
    ValidationError,
    LLMError,
    ToolError,
)
from .handlers import (
    ErrorHandler,
    get_error_handler,
    handle_errors,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
)

__all__ = [
    # Exceptions
    "BaseApplicationError",
    "AgentError",
    "DatabaseError",
    "CacheError",
    "RateLimitError",
    "AuthenticationError",
    "ValidationError",
    "LLMError",
    "ToolError",
    # Handlers
    "ErrorHandler",
    "get_error_handler",
    "handle_errors",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "get_circuit_breaker",
]

