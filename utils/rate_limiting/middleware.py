"""FastAPI rate limiting middleware."""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional

from config import settings
from .rate_limiter import get_rate_limiter
from utils.monitoring import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Features:
    - Per-user rate limiting
    - Per-IP rate limiting
    - Configurable limits
    - Rate limit headers
    """
    
    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        per_minute: int = None,
        per_hour: int = None
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            enabled: Enable rate limiting
            per_minute: Requests per minute
            per_hour: Requests per hour
        """
        super().__init__(app)
        self.enabled = enabled and settings.rate_limit_enabled
        self.per_minute = per_minute or settings.rate_limit_per_minute
        self.per_hour = per_hour or settings.rate_limit_per_hour
        self.limiter = get_rate_limiter()
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try to get user ID from authentication
        user = getattr(request.state, "user", None)
        if user:
            return f"user:{user.get('sub', 'unknown')}"
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check per-minute limit
        minute_result = await self.limiter.check_rate_limit(
            f"{client_id}:minute",
            self.per_minute,
            60
        )
        
        # Check per-hour limit
        hour_result = await self.limiter.check_rate_limit(
            f"{client_id}:hour",
            self.per_hour,
            3600
        )
        
        # Determine if rate limited
        if not minute_result.allowed:
            logger.warning(f"Rate limit exceeded (minute): {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": minute_result.retry_after
                },
                headers={
                    "X-RateLimit-Limit": str(self.per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(minute_result.reset_at.timestamp())),
                    "Retry-After": str(minute_result.retry_after)
                }
            )
        
        if not hour_result.allowed:
            logger.warning(f"Rate limit exceeded (hour): {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Hourly rate limit exceeded. Please try again later.",
                    "retry_after": hour_result.retry_after
                },
                headers={
                    "X-RateLimit-Limit": str(self.per_hour),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(hour_result.reset_at.timestamp())),
                    "Retry-After": str(hour_result.retry_after)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.per_minute)
        response.headers["X-RateLimit-Remaining"] = str(minute_result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(minute_result.reset_at.timestamp()))
        
        return response

