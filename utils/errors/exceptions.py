"""Custom exception classes with detailed error information."""

from typing import Optional, Dict, Any
from datetime import datetime


class BaseApplicationError(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base error.
        
        Args:
            message: Error message
            error_code: Machine-readable error code
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentError(BaseApplicationError):
    """Error in agent execution."""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="AGENT_ERROR", **kwargs)
        self.details["agent_name"] = agent_name


class DatabaseError(BaseApplicationError):
    """Database operation error."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="DATABASE_ERROR", **kwargs)
        self.details["query"] = query


class CacheError(BaseApplicationError):
    """Cache operation error."""
    
    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="CACHE_ERROR", **kwargs)
        self.details["cache_key"] = cache_key


class RateLimitError(BaseApplicationError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            **kwargs
        )
        self.details["retry_after"] = retry_after


class AuthenticationError(BaseApplicationError):
    """Authentication/authorization error."""
    
    def __init__(
        self,
        message: str,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            **kwargs
        )


class ValidationError(BaseApplicationError):
    """Request validation error."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            **kwargs
        )
        self.details["field"] = field


class LLMError(BaseApplicationError):
    """LLM API error."""
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="LLM_ERROR", **kwargs)
        self.details["provider"] = provider
        self.details["model"] = model


class ToolError(BaseApplicationError):
    """Tool execution error."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="TOOL_ERROR", **kwargs)
        self.details["tool_name"] = tool_name


class TimeoutError(BaseApplicationError):
    """Operation timeout error."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="TIMEOUT_ERROR",
            status_code=504,
            **kwargs
        )
        self.details["timeout_seconds"] = timeout_seconds


class CircuitBreakerError(BaseApplicationError):
    """Circuit breaker open error."""
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
            **kwargs
        )

