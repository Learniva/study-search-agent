"""
Token Cache for Authentication.

Caches validated JWT tokens and user data to eliminate repeated database queries.
This can reduce authentication overhead from 20-50ms to <1ms for cached tokens.

Supports both in-memory LRU cache and a distributed Redis cache.
"""

import time
import json
import logging
from typing import Optional, Dict, Any
from collections import OrderedDict
from threading import Lock

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[ConnectionPool] = None

async def get_redis_pool() -> ConnectionPool:
    """Get or create the global Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        try:
            logger.info(f"Creating Redis connection pool for: {settings.redis_url}")
            _redis_pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=20,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
        except Exception as e:
            logger.error(f"❌ Failed to create Redis connection pool: {e}")
            raise
    return _redis_pool

async def close_redis_pool():
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        logger.info("Closing Redis connection pool...")
        await _redis_pool.disconnect()
        _redis_pool = None

class RedisTokenCache:
    """Distributed token cache using Redis."""
    
    def __init__(self, pool: ConnectionPool, ttl_seconds: int = 300):
        self._redis = redis.Redis(connection_pool=pool)
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    async def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user data from Redis cache."""
        try:
            cached_data = await self._redis.get(f"token:{token}")
            if cached_data:
                self._hits += 1
                logger.debug(f"⚡ Redis cache HIT for token: {token[:10]}...")
                return json.loads(cached_data)
            else:
                self._misses += 1
                logger.debug(f"📦 Redis cache MISS for token: {token[:10]}...")
                return None
        except Exception as e:
            # Catch all exceptions to prevent breaking the auth flow
            logger.debug(f"Redis GET error: {e}")
            self._misses += 1
            return None

    async def set(self, token: str, user_data: Dict[str, Any]):
        """Cache user data in Redis with a TTL."""
        try:
            await self._redis.setex(
                f"token:{token}",
                self._ttl_seconds,
                json.dumps(user_data)
            )
            logger.debug(f"✅ Cached token in Redis: {token[:10]}...")
        except Exception as e:
            # Catch all exceptions to prevent breaking the auth flow
            logger.debug(f"Redis SET error: {e}")

    async def invalidate(self, token: str):
        """Invalidate a cached token in Redis."""
        try:
            await self._redis.delete(f"token:{token}")
        except Exception as e:
            logger.error(f"❌ Redis DELETE error: {e}")

    async def clear(self):
        """Clear all cached tokens from Redis (use with caution)."""
        try:
            await self._redis.flushdb()
        except RedisError as e:
            logger.error(f"❌ Redis FLUSHDB error: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "implementation": "RedisTokenCache",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "ttl_seconds": self._ttl_seconds,
        }

class InMemoryTokenCache:
    """
    Thread-safe in-memory LRU cache for JWT tokens and user data.
    Fallback for when Redis is not available.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user data from cache."""
        with self._lock:
            if token not in self._cache:
                self._misses += 1
                return None
            
            cached_data = self._cache[token]
            
            if time.time() - cached_data["cached_at"] > self._ttl_seconds:
                del self._cache[token]
                self._misses += 1
                return None
            
            self._cache.move_to_end(token)
            self._hits += 1
            return cached_data["user_data"]

    async def set(self, token: str, user_data: Dict[str, Any]):
        """Cache user data for token."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            
            self._cache[token] = {
                "user_data": user_data,
                "cached_at": time.time()
            }

    async def invalidate(self, token: str):
        """Invalidate a cached token."""
        with self._lock:
            if token in self._cache:
                del self._cache[token]

    async def clear(self):
        """Clear all cached tokens."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "implementation": "InMemoryTokenCache",
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "ttl_seconds": self._ttl_seconds,
            }

# Global token cache instance
_token_cache: Optional[Any] = None
_redis_failed = False  # Circuit breaker flag

async def get_token_cache():
    """
    Get global token cache instance with circuit breaker pattern.
    
    Initializes RedisTokenCache if enabled and available,
    otherwise falls back to InMemoryTokenCache.
    
    Once Redis fails, we stick with in-memory cache to avoid
    repeated connection attempts and token loss.
    """
    global _token_cache, _redis_failed
    
    if _token_cache is None:
        if settings.redis_enabled and settings.redis_url and not _redis_failed:
            try:
                pool = await get_redis_pool()
                redis_cache = RedisTokenCache(pool, ttl_seconds=settings.cache_ttl)
                
                # Test the connection immediately
                await redis_cache._redis.ping()
                
                _token_cache = redis_cache
                logger.info("✅ Using Redis for token cache.")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to in-memory cache.")
                _redis_failed = True
                _token_cache = InMemoryTokenCache(max_size=settings.cache_max_size, ttl_seconds=settings.cache_ttl)
        else:
            if _redis_failed:
                logger.info("Redis previously failed. Using in-memory token cache.")
            else:
                logger.info("Redis is disabled. Using in-memory token cache.")
            _token_cache = InMemoryTokenCache(max_size=settings.cache_max_size, ttl_seconds=settings.cache_ttl)
    
    return _token_cache


async def reset_token_cache():
    """Reset the global token cache instance (useful for testing or recovery)."""
    global _token_cache, _redis_failed
    _token_cache = None
    _redis_failed = False
    logger.info("🔄 Token cache reset.")

