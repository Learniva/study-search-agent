"""
Distributed state management for horizontal scaling.

Supports multi-instance deployments with shared state via Redis.
"""

import asyncio
import json
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from config import settings
from utils.monitoring import get_logger

logger = get_logger(__name__)


@dataclass
class InstanceInfo:
    """Information about a service instance."""
    instance_id: str
    host: str
    port: int
    started_at: datetime
    last_heartbeat: datetime
    status: str = "active"  # active, draining, stopped
    load: float = 0.0  # 0.0 to 1.0


class DistributedStateManager:
    """
    Manage distributed state across multiple instances.
    
    Features:
    - Shared conversation state
    - Session affinity
    - Instance discovery
    - Health monitoring
    - Distributed locks
    """
    
    def __init__(self, instance_id: str):
        """
        Initialize distributed state manager.
        
        Args:
            instance_id: Unique identifier for this instance
        """
        self.instance_id = instance_id
        self.redis_client = None
        self.instance_info = InstanceInfo(
            instance_id=instance_id,
            host=settings.api_host,
            port=settings.api_port,
            started_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        # Try to initialize Redis
        self._init_redis()
        
        # Heartbeat task
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    def _init_redis(self):
        """Initialize Redis connection for distributed state."""
        if not settings.redis_url:
            logger.warning("Redis not configured - distributed state disabled")
            return
        
        try:
            import redis.asyncio as aioredis
            self.redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info(f"✅ Distributed state initialized for instance {self.instance_id}")
        except ImportError:
            logger.warning("Redis library not available - distributed state disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
    
    @property
    def is_distributed(self) -> bool:
        """Check if distributed mode is enabled."""
        return self.redis_client is not None
    
    async def register_instance(self):
        """Register this instance in the distributed registry."""
        if not self.is_distributed:
            return
        
        try:
            key = f"instances:{self.instance_id}"
            data = json.dumps(asdict(self.instance_info), default=str)
            
            # Store with TTL (auto-cleanup if instance dies)
            await self.redis_client.setex(key, 60, data)
            
            logger.info(f"Registered instance {self.instance_id}")
        except Exception as e:
            logger.error(f"Failed to register instance: {e}")
    
    async def update_heartbeat(self):
        """Update instance heartbeat."""
        if not self.is_distributed:
            return
        
        try:
            self.instance_info.last_heartbeat = datetime.utcnow()
            await self.register_instance()
        except Exception as e:
            logger.error(f"Heartbeat update failed: {e}")
    
    async def get_active_instances(self) -> List[InstanceInfo]:
        """Get list of active instances."""
        if not self.is_distributed:
            return [self.instance_info]
        
        try:
            keys = await self.redis_client.keys("instances:*")
            instances = []
            
            for key in keys:
                data = await self.redis_client.get(key)
                if data:
                    info = json.loads(data)
                    # Convert datetime strings back
                    info['started_at'] = datetime.fromisoformat(info['started_at'])
                    info['last_heartbeat'] = datetime.fromisoformat(info['last_heartbeat'])
                    instances.append(InstanceInfo(**info))
            
            return instances
        except Exception as e:
            logger.error(f"Failed to get active instances: {e}")
            return [self.instance_info]
    
    async def get_session_instance(self, session_id: str) -> Optional[str]:
        """
        Get instance ID for a session (session affinity).
        
        Args:
            session_id: Session identifier
            
        Returns:
            Instance ID or None
        """
        if not self.is_distributed:
            return self.instance_id
        
        try:
            key = f"session:{session_id}"
            instance_id = await self.redis_client.get(key)
            return instance_id
        except Exception as e:
            logger.error(f"Failed to get session instance: {e}")
            return None
    
    async def assign_session(self, session_id: str, ttl: int = 3600):
        """
        Assign session to this instance.
        
        Args:
            session_id: Session identifier
            ttl: Session TTL in seconds
        """
        if not self.is_distributed:
            return
        
        try:
            key = f"session:{session_id}"
            await self.redis_client.setex(key, ttl, self.instance_id)
            logger.debug(f"Assigned session {session_id} to {self.instance_id}")
        except Exception as e:
            logger.error(f"Failed to assign session: {e}")
    
    async def get_conversation_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation state from distributed storage.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Conversation state or None
        """
        if not self.is_distributed:
            return None
        
        try:
            key = f"conversation:{thread_id}"
            data = await self.redis_client.get(key)
            
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get conversation state: {e}")
            return None
    
    async def save_conversation_state(
        self,
        thread_id: str,
        state: Dict[str, Any],
        ttl: int = 3600
    ):
        """
        Save conversation state to distributed storage.
        
        Args:
            thread_id: Thread identifier
            state: Conversation state
            ttl: State TTL in seconds
        """
        if not self.is_distributed:
            return
        
        try:
            key = f"conversation:{thread_id}"
            data = json.dumps(state, default=str)
            await self.redis_client.setex(key, ttl, data)
        except Exception as e:
            logger.error(f"Failed to save conversation state: {e}")
    
    async def acquire_lock(
        self,
        resource: str,
        timeout: int = 10,
        ttl: int = 30
    ) -> bool:
        """
        Acquire distributed lock.
        
        Args:
            resource: Resource to lock
            timeout: Acquisition timeout in seconds
            ttl: Lock TTL in seconds
            
        Returns:
            True if lock acquired, False otherwise
        """
        if not self.is_distributed:
            return True  # No locking needed in single instance
        
        try:
            key = f"lock:{resource}"
            lock_id = f"{self.instance_id}:{asyncio.current_task().get_name()}"
            
            # Try to acquire lock
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # SET NX EX - set if not exists with expiry
                acquired = await self.redis_client.set(
                    key,
                    lock_id,
                    nx=True,
                    ex=ttl
                )
                
                if acquired:
                    logger.debug(f"Acquired lock on {resource}")
                    return True
                
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Lock acquisition timeout for {resource}")
                    return False
                
                # Wait a bit before retry
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False
    
    async def release_lock(self, resource: str):
        """
        Release distributed lock.
        
        Args:
            resource: Resource to unlock
        """
        if not self.is_distributed:
            return
        
        try:
            key = f"lock:{resource}"
            lock_id = f"{self.instance_id}:{asyncio.current_task().get_name()}"
            
            # Only delete if we own the lock
            current_lock = await self.redis_client.get(key)
            if current_lock == lock_id:
                await self.redis_client.delete(key)
                logger.debug(f"Released lock on {resource}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
    
    async def start_heartbeat(self, interval: int = 30):
        """
        Start heartbeat task.
        
        Args:
            interval: Heartbeat interval in seconds
        """
        if not self.is_distributed:
            return
        
        async def heartbeat_loop():
            while True:
                try:
                    await self.update_heartbeat()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info("Started heartbeat task")
    
    async def stop_heartbeat(self):
        """Stop heartbeat task."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped heartbeat task")
    
    async def deregister_instance(self):
        """Deregister this instance."""
        if not self.is_distributed:
            return
        
        try:
            key = f"instances:{self.instance_id}"
            await self.redis_client.delete(key)
            logger.info(f"Deregistered instance {self.instance_id}")
        except Exception as e:
            logger.error(f"Failed to deregister instance: {e}")
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.stop_heartbeat()
        await self.deregister_instance()
        
        if self.redis_client:
            await self.redis_client.close()


# Global distributed state manager
_distributed_state: Optional[DistributedStateManager] = None


def get_distributed_state(instance_id: Optional[str] = None) -> DistributedStateManager:
    """Get or create distributed state manager."""
    global _distributed_state
    
    if _distributed_state is None:
        if instance_id is None:
            # Generate instance ID from host and port
            instance_id = f"{settings.api_host}:{settings.api_port}"
        
        _distributed_state = DistributedStateManager(instance_id)
    
    return _distributed_state

