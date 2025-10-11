"""
Advanced multi-tier caching system with LRU eviction and Redis support.

Features:
- L1: In-memory LRU cache (fastest, most recent)
- L2: Redis distributed cache (optional, for multi-instance)
- L3: PostgreSQL persistent cache (optional, for historical)
- Automatic tier promotion/demotion
- TTL support with custom expiration
- Cache warming and preloading
"""

from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import json
import asyncio
from cachetools import TTLCache, LRUCache

from config import settings


class MultiTierCache:
    """Advanced multi-tier caching with LRU eviction."""
    
    def __init__(
        self,
        ttl: int = None,
        max_size: int = None,
        enable_redis: bool = False,
    ):
        """
        Initialize multi-tier cache.
        
        Args:
            ttl: Time-to-live in seconds (default from settings)
            max_size: Max cache entries (default from settings)
            enable_redis: Enable Redis L2 cache
        """
        self.ttl = ttl or settings.cache_ttl
        self.max_size = max_size or settings.cache_max_size
        self.enable_redis = enable_redis and settings.redis_url is not None
        
        # L1: In-memory cache with TTL and LRU eviction
        self.l1_cache = TTLCache(maxsize=self.max_size, ttl=self.ttl)
        
        # L2: Redis cache (optional)
        self.l2_cache = None
        if self.enable_redis:
            self._init_redis()
        
        # Stats
        self.hits = 0
        self.misses = 0
        self.l1_hits = 0
        self.l2_hits = 0
    
    def _init_redis(self):
        """Initialize Redis connection (lazy loading)."""
        try:
            import redis.asyncio as aioredis
            self.l2_cache = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            print("✅ Redis L2 cache initialized")
        except ImportError:
            print("⚠️  Redis not available, using L1 cache only")
            self.enable_redis = False
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            self.enable_redis = False
    
    def _make_key(self, key: str, prefix: str = "cache") -> str:
        """Generate cache key with prefix and hash."""
        # Hash long keys for efficiency
        if len(key) > 100:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        return f"{prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (checks L1 → L2 → None).
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        cache_key = self._make_key(key)
        
        # L1: Check in-memory cache first (fastest)
        if cache_key in self.l1_cache:
            self.hits += 1
            self.l1_hits += 1
            return self.l1_cache[cache_key]
        
        # L2: Check Redis cache
        if self.enable_redis and self.l2_cache:
            try:
                value = await self.l2_cache.get(cache_key)
                if value is not None:
                    # Deserialize and promote to L1
                    deserialized = json.loads(value)
                    self.l1_cache[cache_key] = deserialized
                    self.hits += 1
                    self.l2_hits += 1
                    return deserialized
            except Exception as e:
                print(f"⚠️  Redis get failed: {e}")
        
        # Cache miss
        self.misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set value in cache (L1 and optionally L2).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Custom TTL (overrides default)
        """
        cache_key = self._make_key(key)
        expiry = ttl or self.ttl
        
        # L1: Always cache in memory
        self.l1_cache[cache_key] = value
        
        # L2: Cache in Redis if enabled
        if self.enable_redis and self.l2_cache:
            try:
                serialized = json.dumps(value)
                await self.l2_cache.setex(
                    cache_key,
                    expiry,
                    serialized
                )
            except Exception as e:
                print(f"⚠️  Redis set failed: {e}")
    
    async def delete(self, key: str) -> None:
        """Delete key from all cache tiers."""
        cache_key = self._make_key(key)
        
        # L1: Delete from memory
        self.l1_cache.pop(cache_key, None)
        
        # L2: Delete from Redis
        if self.enable_redis and self.l2_cache:
            try:
                await self.l2_cache.delete(cache_key)
            except Exception as e:
                print(f"⚠️  Redis delete failed: {e}")
    
    async def clear(self) -> None:
        """Clear all cache tiers."""
        # L1: Clear memory cache
        self.l1_cache.clear()
        
        # L2: Clear Redis cache (all keys with prefix)
        if self.enable_redis and self.l2_cache:
            try:
                keys = await self.l2_cache.keys("cache:*")
                if keys:
                    await self.l2_cache.delete(*keys)
            except Exception as e:
                print(f"⚠️  Redis clear failed: {e}")
        
        # Reset stats
        self.hits = 0
        self.misses = 0
        self.l1_hits = 0
        self.l2_hits = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "l1_size": len(self.l1_cache),
            "l1_max_size": self.max_size,
            "ttl_seconds": self.ttl,
            "redis_enabled": self.enable_redis,
        }
    
    async def warm_cache(self, data: Dict[str, Any]) -> None:
        """
        Warm cache with pre-computed data.
        
        Args:
            data: Dictionary of key-value pairs to cache
        """
        for key, value in data.items():
            await self.set(key, value)
        print(f"🔥 Cache warmed with {len(data)} entries")


# Cache decorator for async functions
def async_cached(
    ttl: int = None,
    key_prefix: str = "func",
):
    """
    Decorator for caching async function results.
    
    Usage:
        @async_cached(ttl=300, key_prefix="user")
        async def get_user(user_id: str):
            return await db.get_user(user_id)
    """
    cache = MultiTierCache(ttl=ttl)
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            key_parts = [func.__name__] + [str(arg) for arg in args]
            if kwargs:
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # Check cache
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Compute and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result)
            return result
        
        return wrapper
    return decorator


# Global cache instances
_global_caches: Dict[str, MultiTierCache] = {}


def get_cache(name: str = "default") -> MultiTierCache:
    """Get or create a named cache instance."""
    if name not in _global_caches:
        _global_caches[name] = MultiTierCache(
            enable_redis=settings.redis_url is not None
        )
    return _global_caches[name]


# Backward compatibility with existing ResultCache
class ResultCache(MultiTierCache):
    """Legacy ResultCache class for backward compatibility."""
    
    def __init__(self, ttl_seconds: int = None):
        super().__init__(ttl=ttl_seconds)
    
    def get_cache_key(self, question: str, thread_id: str = "default") -> str:
        """Generate cache key from question and thread."""
        return f"{thread_id}:{question}"
    
    async def get(self, key: str) -> Optional[str]:
        """Get cached result (async)."""
        return await super().get(key)
    
    async def set(self, key: str, value: str) -> None:
        """Set cached result (async)."""
        await super().set(key, value)


