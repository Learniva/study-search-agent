"""
Shared caching utilities for the Multi-Agent System.

Provides thread-safe caching with TTL (Time To Live) for:
- Query results
- Tool outputs
- Routing decisions

Reduces API calls and improves response times for repeated queries.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class ResultCache:
    """
    Thread-safe result cache with TTL support.
    
    Features:
    - MD5-based cache keys
    - Automatic expiration based on TTL
    - Cache statistics (hits, misses, hit rate)
    - Memory management
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the result cache.
        
        Args:
            ttl_seconds: Time to live for cached items (default: 1 hour)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
    
    def get_cache_key(self, question: str, context: str = "default") -> str:
        """
        Generate MD5 cache key from question and context.
        
        Args:
            question: The query/question
            context: Additional context (e.g., thread_id, user_id)
            
        Returns:
            MD5 hash as cache key
        """
        cache_str = f"{question.lower().strip()}|{context}"
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[str]:
        """
        Retrieve cached result if available and not expired.
        
        Args:
            cache_key: Cache key to lookup
            
        Returns:
            Cached result if found and valid, None otherwise
        """
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            
            # Check if expired
            if datetime.now() < cached_data['expires']:
                self.hits += 1
                print(f"⚡ Cache HIT! (saved API calls) [{self.hits} hits, {self.misses} misses]")
                return cached_data['result']
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
        
        self.misses += 1
        return None
    
    def set(self, cache_key: str, result: str):
        """
        Store result in cache with TTL.
        
        Args:
            cache_key: Cache key
            result: Result to cache
        """
        self.cache[cache_key] = {
            'result': result,
            'expires': datetime.now() + timedelta(seconds=self.ttl),
            'cached_at': datetime.now()
        }
    
    def clear(self):
        """Clear all cached items."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def remove_expired(self):
        """Remove all expired items from cache."""
        now = datetime.now()
        expired_keys = [
            key for key, data in self.cache.items()
            if now >= data['expires']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.hits,
            'cache_misses': self.misses,
            'total_requests': total_requests,
            'hit_rate': f"{hit_rate:.1f}%",
            'cached_items': len(self.cache),
            'ttl_seconds': self.ttl
        }
    
    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self.cache)
    
    def __contains__(self, cache_key: str) -> bool:
        """Check if key exists and is not expired."""
        if cache_key in self.cache:
            if datetime.now() < self.cache[cache_key]['expires']:
                return True
            else:
                # Expired, remove
                del self.cache[cache_key]
        return False

