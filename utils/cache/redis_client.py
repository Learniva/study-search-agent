"""
Redis Client Utilities

Provides a singleton Redis client for caching, token storage, and session management.
"""

import redis
import json
from typing import Optional, Any
from datetime import timedelta
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis client for application-wide use."""
    
    _instance: Optional[redis.Redis] = None
    _connected: bool = False
    
    @classmethod
    def get_instance(cls) -> Optional[redis.Redis]:
        """
        Get Redis client instance.
        
        Returns:
            Redis client if configured, None otherwise
        """
        if cls._instance is None and settings.redis_url:
            try:
                cls._instance = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                cls._instance.ping()
                cls._connected = True
                logger.info("✅ Redis client initialized successfully")
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"⚠️  Redis connection failed: {e}")
                logger.info("📝 Falling back to in-memory storage")
                cls._instance = None
                cls._connected = False
        
        return cls._instance
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Redis is connected."""
        return cls._connected
    
    @classmethod
    def close(cls):
        """Close Redis connection."""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            cls._connected = False
            logger.info("🔌 Redis connection closed")


class TokenStore:
    """Token storage with Redis backend (falls back to in-memory)."""
    
    def __init__(self):
        self.redis_client = RedisClient.get_instance()
        self._memory_store: dict = {}  # Fallback for when Redis is unavailable
        self.prefix = "auth:token:"
    
    def set(self, token: str, data: dict, ttl: int = 86400) -> bool:
        """
        Store token with TTL.
        
        Args:
            token: Authentication token
            data: Token metadata (user_id, role, etc.)
            ttl: Time to live in seconds (default: 24 hours)
        
        Returns:
            True if stored successfully
        """
        try:
            if self.redis_client:
                key = f"{self.prefix}{token}"
                value = json.dumps(data)
                self.redis_client.setex(key, ttl, value)
                logger.debug(f"🔑 Token stored in Redis: {token[:20]}...")
                return True
            else:
                # Fallback to in-memory
                self._memory_store[token] = data
                logger.debug(f"🔑 Token stored in memory: {token[:20]}...")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to store token: {e}")
            # Emergency fallback
            self._memory_store[token] = data
            return True
    
    def get(self, token: str) -> Optional[dict]:
        """
        Retrieve token data.
        
        Args:
            token: Authentication token
        
        Returns:
            Token metadata or None if not found/expired
        """
        try:
            if self.redis_client:
                key = f"{self.prefix}{token}"
                value = self.redis_client.get(key)
                if value:
                    logger.debug(f"🔍 Token found in Redis: {token[:20]}...")
                    return json.loads(value)
                logger.debug(f"🔍 Token not found in Redis: {token[:20]}...")
                return None
            else:
                # Fallback to in-memory
                data = self._memory_store.get(token)
                if data:
                    logger.debug(f"🔍 Token found in memory: {token[:20]}...")
                else:
                    logger.debug(f"🔍 Token not found in memory: {token[:20]}...")
                return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve token: {e}")
            return self._memory_store.get(token)
    
    def delete(self, token: str) -> bool:
        """
        Delete token (logout).
        
        Args:
            token: Authentication token
        
        Returns:
            True if deleted successfully
        """
        try:
            if self.redis_client:
                key = f"{self.prefix}{token}"
                self.redis_client.delete(key)
                logger.debug(f"🗑️  Token deleted from Redis: {token[:20]}...")
                return True
            else:
                # Fallback to in-memory
                if token in self._memory_store:
                    del self._memory_store[token]
                    logger.debug(f"🗑️  Token deleted from memory: {token[:20]}...")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to delete token: {e}")
            if token in self._memory_store:
                del self._memory_store[token]
            return True
    
    def exists(self, token: str) -> bool:
        """Check if token exists."""
        try:
            if self.redis_client:
                key = f"{self.prefix}{token}"
                return bool(self.redis_client.exists(key))
            else:
                return token in self._memory_store
        except Exception as e:
            logger.error(f"❌ Failed to check token existence: {e}")
            return token in self._memory_store
    
    def count(self) -> int:
        """Count active tokens."""
        try:
            if self.redis_client:
                pattern = f"{self.prefix}*"
                return len(list(self.redis_client.scan_iter(match=pattern)))
            else:
                return len(self._memory_store)
        except Exception as e:
            logger.error(f"❌ Failed to count tokens: {e}")
            return len(self._memory_store)
    
    def clear_all(self):
        """Clear all tokens (emergency use only)."""
        try:
            if self.redis_client:
                pattern = f"{self.prefix}*"
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
                logger.warning("⚠️  All tokens cleared from Redis")
            else:
                self._memory_store.clear()
                logger.warning("⚠️  All tokens cleared from memory")
        except Exception as e:
            logger.error(f"❌ Failed to clear tokens: {e}")
            self._memory_store.clear()


# Global token store instance
token_store = TokenStore()


__all__ = ['RedisClient', 'TokenStore', 'token_store']

