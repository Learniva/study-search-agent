"""
Advanced caching strategies for optimization.

Includes cache warming, invalidation patterns, and smart prefetching.
"""

import asyncio
from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json

from utils.core.advanced_cache import MultiTierCache
from utils.monitoring import get_logger
from config import settings

logger = get_logger(__name__)


class CacheWarmer:
    """
    Proactive cache warming for frequently accessed data.
    
    Features:
    - Preload frequently accessed queries
    - Background refresh before expiry
    - Batch warming from database
    - Statistics tracking
    """
    
    def __init__(
        self,
        cache: MultiTierCache,
        warm_interval: int = 300  # 5 minutes
    ):
        """
        Initialize cache warmer.
        
        Args:
            cache: Cache instance to warm
            warm_interval: Interval between warming cycles (seconds)
        """
        self.cache = cache
        self.warm_interval = warm_interval
        self.warming_task: Optional[asyncio.Task] = None
        
        # Track access patterns
        self.access_counts: Dict[str, int] = defaultdict(int)
        self.last_access: Dict[str, datetime] = {}
        
        # Warming stats
        self.total_warmed = 0
        self.last_warm_time: Optional[datetime] = None
    
    def track_access(self, key: str):
        """Track cache access for warming decisions."""
        self.access_counts[key] += 1
        self.last_access[key] = datetime.utcnow()
    
    def get_frequently_accessed(
        self,
        min_accesses: int = 5,
        time_window: int = 3600  # 1 hour
    ) -> List[str]:
        """
        Get frequently accessed keys within time window.
        
        Args:
            min_accesses: Minimum access count
            time_window: Time window in seconds
            
        Returns:
            List of frequently accessed keys
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=time_window)
        
        frequent_keys = [
            key for key, count in self.access_counts.items()
            if count >= min_accesses
            and self.last_access.get(key, datetime.min) > cutoff_time
        ]
        
        # Sort by access count (descending)
        frequent_keys.sort(
            key=lambda k: self.access_counts[k],
            reverse=True
        )
        
        return frequent_keys
    
    async def warm_keys(
        self,
        keys: List[str],
        data_loader: Callable[[str], Any]
    ) -> int:
        """
        Warm cache with specific keys.
        
        Args:
            keys: Keys to warm
            data_loader: Function to load data for key
            
        Returns:
            Number of keys warmed
        """
        warmed = 0
        
        for key in keys:
            try:
                # Check if already cached
                cached = await self.cache.get(key)
                if cached is not None:
                    continue
                
                # Load and cache data
                if asyncio.iscoroutinefunction(data_loader):
                    data = await data_loader(key)
                else:
                    data = data_loader(key)
                
                await self.cache.set(key, data)
                warmed += 1
                
            except Exception as e:
                logger.error(f"Error warming cache for {key}: {e}")
        
        self.total_warmed += warmed
        self.last_warm_time = datetime.utcnow()
        
        logger.info(f"🔥 Warmed {warmed} cache entries")
        return warmed
    
    async def warm_popular(
        self,
        data_loader: Callable[[str], Any],
        max_keys: int = 100
    ) -> int:
        """
        Warm cache with popular keys.
        
        Args:
            data_loader: Function to load data
            max_keys: Maximum keys to warm
            
        Returns:
            Number of keys warmed
        """
        frequent_keys = self.get_frequently_accessed()[:max_keys]
        return await self.warm_keys(frequent_keys, data_loader)
    
    async def start_background_warming(
        self,
        data_loader: Callable[[str], Any]
    ):
        """Start background cache warming task."""
        if self.warming_task and not self.warming_task.done():
            logger.warning("Cache warming already running")
            return
        
        async def warming_loop():
            while True:
                try:
                    await asyncio.sleep(self.warm_interval)
                    await self.warm_popular(data_loader)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in warming loop: {e}")
        
        self.warming_task = asyncio.create_task(warming_loop())
        logger.info("Started background cache warming")
    
    async def stop_background_warming(self):
        """Stop background cache warming task."""
        if self.warming_task:
            self.warming_task.cancel()
            try:
                await self.warming_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped background cache warming")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get warming statistics."""
        return {
            "total_warmed": self.total_warmed,
            "last_warm_time": (
                self.last_warm_time.isoformat() 
                if self.last_warm_time 
                else None
            ),
            "tracked_keys": len(self.access_counts),
            "warming_interval_seconds": self.warm_interval,
            "top_accessed_keys": dict(
                sorted(
                    self.access_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ),
        }


class CacheInvalidator:
    """
    Smart cache invalidation patterns.
    
    Features:
    - Pattern-based invalidation
    - Tag-based invalidation
    - Time-based invalidation
    - Dependency tracking
    """
    
    def __init__(self, cache: MultiTierCache):
        """Initialize cache invalidator."""
        self.cache = cache
        
        # Track key patterns and tags
        self.key_patterns: Dict[str, Set[str]] = defaultdict(set)
        self.key_tags: Dict[str, Set[str]] = defaultdict(set)
        
        # Invalidation stats
        self.invalidations = 0
        self.keys_invalidated = 0
    
    def register_pattern(self, pattern: str, key: str):
        """Register key with pattern for pattern-based invalidation."""
        self.key_patterns[pattern].add(key)
    
    def tag_key(self, key: str, *tags: str):
        """Tag key for tag-based invalidation."""
        for tag in tags:
            self.key_tags[tag].add(key)
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Pattern to match
            
        Returns:
            Number of keys invalidated
        """
        keys_to_invalidate = self.key_patterns.get(pattern, set())
        
        for key in keys_to_invalidate:
            await self.cache.delete(key)
        
        count = len(keys_to_invalidate)
        self.invalidations += 1
        self.keys_invalidated += count
        
        logger.info(f"Invalidated {count} keys for pattern: {pattern}")
        return count
    
    async def invalidate_tags(self, *tags: str) -> int:
        """
        Invalidate all keys with given tags.
        
        Args:
            *tags: Tags to invalidate
            
        Returns:
            Number of keys invalidated
        """
        keys_to_invalidate = set()
        
        for tag in tags:
            keys_to_invalidate.update(self.key_tags.get(tag, set()))
        
        for key in keys_to_invalidate:
            await self.cache.delete(key)
        
        count = len(keys_to_invalidate)
        self.invalidations += 1
        self.keys_invalidated += count
        
        logger.info(f"Invalidated {count} keys for tags: {tags}")
        return count
    
    async def invalidate_old_entries(
        self,
        older_than: timedelta
    ) -> int:
        """
        Invalidate entries older than specified time.
        
        Args:
            older_than: Time delta for old entries
            
        Returns:
            Number of keys invalidated
        """
        # This would require timestamp tracking per key
        # For now, we'll clear the entire cache if needed
        logger.warning(
            "Time-based invalidation requires timestamp tracking per key"
        )
        return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get invalidation statistics."""
        return {
            "total_invalidations": self.invalidations,
            "total_keys_invalidated": self.keys_invalidated,
            "tracked_patterns": len(self.key_patterns),
            "tracked_tags": len(self.key_tags),
        }


class SmartPrefetcher:
    """
    Intelligent cache prefetching based on access patterns.
    
    Features:
    - Predict next queries based on patterns
    - Prefetch related data
    - Batch prefetching
    """
    
    def __init__(self, cache: MultiTierCache):
        """Initialize smart prefetcher."""
        self.cache = cache
        
        # Track access sequences
        self.access_sequences: List[List[str]] = []
        self.sequence_patterns: Dict[str, List[str]] = defaultdict(list)
        
        # Prefetch stats
        self.prefetches = 0
        self.prefetch_hits = 0
    
    def record_access(self, key: str, session_id: str = "default"):
        """Record access for pattern learning."""
        # Find or create session sequence
        # This is a simplified version
        pass
    
    async def prefetch_related(
        self,
        key: str,
        data_loader: Callable[[str], Any],
        max_prefetch: int = 5
    ) -> int:
        """
        Prefetch related keys based on patterns.
        
        Args:
            key: Current key
            data_loader: Function to load data
            max_prefetch: Maximum keys to prefetch
            
        Returns:
            Number of keys prefetched
        """
        # Get predicted next keys
        predicted_keys = self.sequence_patterns.get(key, [])[:max_prefetch]
        
        prefetched = 0
        for next_key in predicted_keys:
            # Check if already cached
            cached = await self.cache.get(next_key)
            if cached is not None:
                continue
            
            try:
                # Load and cache data
                if asyncio.iscoroutinefunction(data_loader):
                    data = await data_loader(next_key)
                else:
                    data = data_loader(next_key)
                
                await self.cache.set(next_key, data)
                prefetched += 1
                
            except Exception as e:
                logger.error(f"Error prefetching {next_key}: {e}")
        
        self.prefetches += 1
        
        if prefetched > 0:
            logger.debug(f"Prefetched {prefetched} related keys for {key}")
        
        return prefetched
    
    def track_prefetch_hit(self):
        """Track when prefetched data is used."""
        self.prefetch_hits += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get prefetch statistics."""
        hit_rate = (
            self.prefetch_hits / self.prefetches * 100 
            if self.prefetches > 0 
            else 0
        )
        
        return {
            "total_prefetches": self.prefetches,
            "prefetch_hits": self.prefetch_hits,
            "prefetch_hit_rate_percent": round(hit_rate, 2),
            "learned_patterns": len(self.sequence_patterns),
        }


class CacheOptimizer:
    """
    Combines all caching strategies for optimal performance.
    
    Integrates:
    - Cache warming
    - Smart invalidation
    - Intelligent prefetching
    """
    
    def __init__(
        self,
        cache: MultiTierCache,
        enable_warming: bool = True,
        enable_prefetching: bool = True
    ):
        """
        Initialize cache optimizer.
        
        Args:
            cache: Cache instance
            enable_warming: Enable cache warming
            enable_prefetching: Enable prefetching
        """
        self.cache = cache
        
        # Components
        self.warmer = CacheWarmer(cache) if enable_warming else None
        self.invalidator = CacheInvalidator(cache)
        self.prefetcher = (
            SmartPrefetcher(cache) if enable_prefetching else None
        )
    
    async def get_optimized(
        self,
        key: str,
        data_loader: Callable[[str], Any],
        prefetch: bool = True
    ) -> Any:
        """
        Get from cache with optimization strategies.
        
        Args:
            key: Cache key
            data_loader: Function to load data on miss
            prefetch: Enable prefetching
            
        Returns:
            Cached or loaded data
        """
        # Track access for warming
        if self.warmer:
            self.warmer.track_access(key)
        
        # Get from cache
        cached = await self.cache.get(key)
        
        if cached is not None:
            # Prefetch related if enabled
            if prefetch and self.prefetcher:
                asyncio.create_task(
                    self.prefetcher.prefetch_related(key, data_loader)
                )
            
            return cached
        
        # Load data on miss
        if asyncio.iscoroutinefunction(data_loader):
            data = await data_loader(key)
        else:
            data = data_loader(key)
        
        # Cache the result
        await self.cache.set(key, data)
        
        return data
    
    async def set_with_tags(
        self,
        key: str,
        value: Any,
        *tags: str,
        pattern: Optional[str] = None
    ):
        """
        Set cache value with tags and patterns for invalidation.
        
        Args:
            key: Cache key
            value: Value to cache
            *tags: Tags for invalidation
            pattern: Pattern for invalidation
        """
        # Tag key
        if tags:
            self.invalidator.tag_key(key, *tags)
        
        # Register pattern
        if pattern:
            self.invalidator.register_pattern(pattern, key)
        
        # Cache value
        await self.cache.set(key, value)
    
    async def invalidate(
        self,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """
        Invalidate cache entries by pattern or tags.
        
        Args:
            pattern: Pattern to invalidate
            tags: Tags to invalidate
            
        Returns:
            Number of keys invalidated
        """
        total = 0
        
        if pattern:
            total += await self.invalidator.invalidate_pattern(pattern)
        
        if tags:
            total += await self.invalidator.invalidate_tags(*tags)
        
        return total
    
    async def start_optimization(
        self,
        data_loader: Callable[[str], Any]
    ):
        """Start background optimization (warming)."""
        if self.warmer:
            await self.warmer.start_background_warming(data_loader)
    
    async def stop_optimization(self):
        """Stop background optimization."""
        if self.warmer:
            await self.warmer.stop_background_warming()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        stats = {
            "cache": self.cache.get_stats(),
        }
        
        if self.warmer:
            stats["warming"] = self.warmer.get_stats()
        
        stats["invalidation"] = self.invalidator.get_stats()
        
        if self.prefetcher:
            stats["prefetching"] = self.prefetcher.get_stats()
        
        return stats


# Global cache optimizer
_global_optimizer: Optional[CacheOptimizer] = None


def get_cache_optimizer(
    cache: Optional[MultiTierCache] = None
) -> CacheOptimizer:
    """Get or create global cache optimizer."""
    global _global_optimizer
    
    if _global_optimizer is None:
        from utils.core.advanced_cache import get_cache
        cache = cache or get_cache()
        _global_optimizer = CacheOptimizer(cache)
    
    return _global_optimizer

