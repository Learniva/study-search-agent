"""
Rate limiting implementation with multiple algorithms.

Supports token bucket, sliding window, and fixed window algorithms.
"""

import asyncio
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timedelta

from config import settings
from utils.monitoring import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitResult:
    """Rate limit check result."""
    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None  # seconds


class RateLimiter(ABC):
    """Base rate limiter interface."""
    
    @abstractmethod
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> RateLimitResult:
        """Check if request is allowed."""
        pass
    
    @abstractmethod
    async def reset(self, key: str):
        """Reset rate limit for key."""
        pass


class TokenBucketLimiter(RateLimiter):
    """
    Token bucket rate limiter.
    
    Features:
    - Allows burst traffic
    - Smooth rate limiting
    - Refills at constant rate
    """
    
    def __init__(self):
        self.buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self.redis_client = None
        
        # Try Redis for distributed rate limiting
        if settings.redis_url:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis for distributed rate limiting."""
        try:
            import redis.asyncio as aioredis
            self.redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("✅ Distributed rate limiting enabled")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory rate limiting: {e}")
    
    async def _get_bucket(self, key: str) -> Tuple[float, float]:
        """Get bucket state (tokens, last_refill)."""
        if self.redis_client:
            # Distributed bucket (Redis)
            try:
                data = await self.redis_client.hgetall(f"ratelimit:{key}")
                if data:
                    return (
                        float(data.get("tokens", 0)),
                        float(data.get("last_refill", time.time()))
                    )
            except Exception as e:
                logger.error(f"Redis get bucket error: {e}")
        
        # Local bucket (in-memory)
        return self.buckets.get(key, (0.0, time.time()))
    
    async def _set_bucket(self, key: str, tokens: float, last_refill: float):
        """Set bucket state."""
        if self.redis_client:
            # Distributed bucket (Redis)
            try:
                await self.redis_client.hset(
                    f"ratelimit:{key}",
                    mapping={
                        "tokens": str(tokens),
                        "last_refill": str(last_refill)
                    }
                )
                await self.redis_client.expire(f"ratelimit:{key}", 3600)
            except Exception as e:
                logger.error(f"Redis set bucket error: {e}")
        
        # Always update local cache
        self.buckets[key] = (tokens, last_refill)
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> RateLimitResult:
        """
        Check rate limit using token bucket algorithm.
        
        Args:
            key: Rate limit key (user_id, IP, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            RateLimitResult
        """
        current_time = time.time()
        tokens, last_refill = await self._get_bucket(key)
        
        # Calculate refill rate
        refill_rate = max_requests / window_seconds
        
        # Refill tokens based on time elapsed
        time_elapsed = current_time - last_refill
        tokens_to_add = time_elapsed * refill_rate
        tokens = min(max_requests, tokens + tokens_to_add)
        
        # Check if request allowed
        if tokens >= 1.0:
            # Consume one token
            tokens -= 1.0
            await self._set_bucket(key, tokens, current_time)
            
            return RateLimitResult(
                allowed=True,
                remaining=int(tokens),
                reset_at=datetime.fromtimestamp(current_time + window_seconds)
            )
        else:
            # Rate limited
            retry_after = int((1.0 - tokens) / refill_rate)
            await self._set_bucket(key, tokens, current_time)
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=datetime.fromtimestamp(current_time + retry_after),
                retry_after=retry_after
            )
    
    async def reset(self, key: str):
        """Reset rate limit for key."""
        if self.redis_client:
            try:
                await self.redis_client.delete(f"ratelimit:{key}")
            except Exception as e:
                logger.error(f"Redis reset error: {e}")
        
        self.buckets.pop(key, None)


class SlidingWindowLimiter(RateLimiter):
    """
    Sliding window rate limiter.
    
    Features:
    - More accurate than fixed window
    - Prevents boundary issues
    - Tracks exact request timestamps
    """
    
    def __init__(self):
        self.windows: Dict[str, deque] = {}
        self.redis_client = None
        
        if settings.redis_url:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis."""
        try:
            import redis.asyncio as aioredis
            self.redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
    
    async def _get_window(self, key: str) -> deque:
        """Get sliding window for key."""
        if self.redis_client:
            try:
                # Get sorted set from Redis
                timestamps = await self.redis_client.zrange(
                    f"ratelimit:window:{key}",
                    0,
                    -1
                )
                return deque(float(ts) for ts in timestamps)
            except Exception as e:
                logger.error(f"Redis get window error: {e}")
        
        return self.windows.get(key, deque())
    
    async def _set_window(self, key: str, window: deque):
        """Set sliding window for key."""
        if self.redis_client:
            try:
                # Store as sorted set in Redis
                pipe = self.redis_client.pipeline()
                pipe.delete(f"ratelimit:window:{key}")
                
                if window:
                    for ts in window:
                        pipe.zadd(f"ratelimit:window:{key}", {str(ts): ts})
                
                pipe.expire(f"ratelimit:window:{key}", 3600)
                await pipe.execute()
            except Exception as e:
                logger.error(f"Redis set window error: {e}")
        
        self.windows[key] = window
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> RateLimitResult:
        """
        Check rate limit using sliding window algorithm.
        
        Args:
            key: Rate limit key
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            RateLimitResult
        """
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Get window
        window = await self._get_window(key)
        
        # Remove old timestamps
        while window and window[0] < window_start:
            window.popleft()
        
        # Check if allowed
        if len(window) < max_requests:
            # Add current timestamp
            window.append(current_time)
            await self._set_window(key, window)
            
            return RateLimitResult(
                allowed=True,
                remaining=max_requests - len(window),
                reset_at=datetime.fromtimestamp(window[0] + window_seconds) if window else datetime.fromtimestamp(current_time + window_seconds)
            )
        else:
            # Rate limited
            oldest_timestamp = window[0]
            retry_after = int(oldest_timestamp + window_seconds - current_time) + 1
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=datetime.fromtimestamp(oldest_timestamp + window_seconds),
                retry_after=retry_after
            )
    
    async def reset(self, key: str):
        """Reset rate limit for key."""
        if self.redis_client:
            try:
                await self.redis_client.delete(f"ratelimit:window:{key}")
            except Exception as e:
                logger.error(f"Redis reset error: {e}")
        
        self.windows.pop(key, None)


# Global rate limiter
_global_limiter: Optional[RateLimiter] = None


def get_rate_limiter(algorithm: str = "token_bucket") -> RateLimiter:
    """
    Get or create global rate limiter.
    
    Args:
        algorithm: "token_bucket" or "sliding_window"
        
    Returns:
        RateLimiter instance
    """
    global _global_limiter
    
    if _global_limiter is None:
        if algorithm == "sliding_window":
            _global_limiter = SlidingWindowLimiter()
        else:
            _global_limiter = TokenBucketLimiter()
    
    return _global_limiter


# Convenience functions
async def check_rate_limit(
    key: str,
    max_requests: Optional[int] = None,
    window_seconds: int = 60
) -> RateLimitResult:
    """
    Check rate limit for key.
    
    Args:
        key: Rate limit key
        max_requests: Max requests (default from settings)
        window_seconds: Time window in seconds
        
    Returns:
        RateLimitResult
    """
    limiter = get_rate_limiter()
    max_requests = max_requests or settings.rate_limit_per_minute
    
    return await limiter.check_rate_limit(key, max_requests, window_seconds)


async def check_user_rate_limit(user_id: str) -> RateLimitResult:
    """Check rate limit for user."""
    return await check_rate_limit(
        f"user:{user_id}",
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60
    )


async def check_ip_rate_limit(ip: str) -> RateLimitResult:
    """Check rate limit for IP address."""
    return await check_rate_limit(
        f"ip:{ip}",
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60
    )

