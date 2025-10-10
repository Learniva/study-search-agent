"""
Resource management and lifecycle utilities.

Handles database connections, caches, and other resources with proper cleanup.
"""

import asyncio
from typing import Any, Optional, Dict, List, Callable, AsyncContextManager
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
import weakref

from utils.monitoring import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceInfo:
    """Information about a managed resource."""
    name: str
    type: str
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    cleanup_func: Optional[Callable] = None


class ResourceManager:
    """
    Centralized resource lifecycle management.
    
    Features:
    - Automatic cleanup on shutdown
    - Resource tracking and monitoring
    - Weak references to prevent leaks
    - Async context manager support
    """
    
    def __init__(self):
        self.resources: Dict[str, ResourceInfo] = {}
        self._cleanup_tasks: List[Callable] = []
        self._locks: Dict[str, asyncio.Lock] = {}
        self._shutdown = False
    
    async def register_resource(
        self,
        name: str,
        resource: Any,
        resource_type: str = "generic",
        cleanup_func: Optional[Callable] = None
    ) -> None:
        """
        Register a resource for lifecycle management.
        
        Args:
            name: Unique resource identifier
            resource: The resource object
            resource_type: Type of resource (db, cache, etc.)
            cleanup_func: Optional cleanup function
        """
        if self._shutdown:
            raise RuntimeError("ResourceManager is shut down")
        
        self.resources[name] = ResourceInfo(
            name=name,
            type=resource_type,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            cleanup_func=cleanup_func
        )
        
        if cleanup_func:
            self._cleanup_tasks.append(cleanup_func)
        
        logger.info(f"Registered resource: {name} ({resource_type})")
    
    async def unregister_resource(self, name: str) -> None:
        """Unregister and cleanup a resource."""
        if name in self.resources:
            info = self.resources[name]
            
            # Run cleanup if available
            if info.cleanup_func:
                try:
                    if asyncio.iscoroutinefunction(info.cleanup_func):
                        await info.cleanup_func()
                    else:
                        info.cleanup_func()
                except Exception as e:
                    logger.error(f"Error cleaning up {name}: {e}")
            
            del self.resources[name]
            logger.info(f"Unregistered resource: {name}")
    
    def track_usage(self, name: str):
        """Track resource usage."""
        if name in self.resources:
            self.resources[name].last_used = datetime.utcnow()
            self.resources[name].use_count += 1
    
    def get_lock(self, name: str) -> asyncio.Lock:
        """Get or create lock for resource."""
        if name not in self._locks:
            self._locks[name] = asyncio.Lock()
        return self._locks[name]
    
    @asynccontextmanager
    async def acquire_resource(self, name: str):
        """
        Acquire resource with automatic tracking and locking.
        
        Usage:
            async with resource_manager.acquire_resource("db") as db:
                await db.execute(query)
        """
        if name not in self.resources:
            raise ValueError(f"Resource {name} not registered")
        
        lock = self.get_lock(name)
        
        async with lock:
            self.track_usage(name)
            try:
                yield name
            finally:
                pass  # Cleanup handled by context manager
    
    async def cleanup_all(self):
        """Cleanup all registered resources."""
        logger.info("Cleaning up all resources...")
        
        self._shutdown = True
        
        # Cleanup in reverse registration order
        for cleanup_func in reversed(self._cleanup_tasks):
            try:
                if asyncio.iscoroutinefunction(cleanup_func):
                    await cleanup_func()
                else:
                    cleanup_func()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
        
        self.resources.clear()
        self._cleanup_tasks.clear()
        self._locks.clear()
        
        logger.info("All resources cleaned up")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get resource statistics."""
        stats = {
            "total_resources": len(self.resources),
            "resources_by_type": {},
            "resources": []
        }
        
        for info in self.resources.values():
            # Count by type
            stats["resources_by_type"][info.type] = \
                stats["resources_by_type"].get(info.type, 0) + 1
            
            # Resource details
            stats["resources"].append({
                "name": info.name,
                "type": info.type,
                "created_at": info.created_at.isoformat(),
                "last_used": info.last_used.isoformat(),
                "use_count": info.use_count,
            })
        
        return stats


# Global resource manager
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get or create global resource manager."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


@asynccontextmanager
async def async_resource(
    name: str,
    create_func: Callable,
    cleanup_func: Optional[Callable] = None,
    resource_type: str = "generic"
):
    """
    Context manager for temporary async resources.
    
    Usage:
        async with async_resource(
            "temp_db",
            create_func=create_db,
            cleanup_func=close_db,
            resource_type="database"
        ) as db:
            await db.query(...)
    """
    manager = get_resource_manager()
    resource = None
    
    try:
        # Create resource
        if asyncio.iscoroutinefunction(create_func):
            resource = await create_func()
        else:
            resource = create_func()
        
        # Register
        await manager.register_resource(
            name=name,
            resource=resource,
            resource_type=resource_type,
            cleanup_func=cleanup_func
        )
        
        yield resource
        
    finally:
        # Cleanup
        await manager.unregister_resource(name)


class ResourcePool:
    """
    Generic resource pool with async support.
    
    Manages a pool of reusable resources (connections, clients, etc.)
    """
    
    def __init__(
        self,
        create_func: Callable,
        max_size: int = 10,
        min_size: int = 2,
        timeout: int = 30
    ):
        """
        Initialize resource pool.
        
        Args:
            create_func: Function to create new resources
            max_size: Maximum pool size
            min_size: Minimum pool size
            timeout: Acquire timeout in seconds
        """
        self.create_func = create_func
        self.max_size = max_size
        self.min_size = min_size
        self.timeout = timeout
        
        self.pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.size = 0
        self.lock = asyncio.Lock()
        
        # Stats
        self.created_count = 0
        self.acquired_count = 0
        self.released_count = 0
    
    async def _create_resource(self) -> Any:
        """Create new resource."""
        if asyncio.iscoroutinefunction(self.create_func):
            resource = await self.create_func()
        else:
            resource = self.create_func()
        
        self.created_count += 1
        return resource
    
    async def acquire(self) -> Any:
        """Acquire resource from pool."""
        try:
            # Try to get from pool with timeout
            resource = await asyncio.wait_for(
                self.pool.get(),
                timeout=1.0
            )
            self.acquired_count += 1
            return resource
            
        except asyncio.TimeoutError:
            # Create new if under max size
            async with self.lock:
                if self.size < self.max_size:
                    resource = await self._create_resource()
                    self.size += 1
                    self.acquired_count += 1
                    return resource
            
            # Wait for available resource
            resource = await asyncio.wait_for(
                self.pool.get(),
                timeout=self.timeout
            )
            self.acquired_count += 1
            return resource
    
    async def release(self, resource: Any) -> None:
        """Release resource back to pool."""
        try:
            self.pool.put_nowait(resource)
            self.released_count += 1
        except asyncio.QueueFull:
            # Pool full, discard resource
            async with self.lock:
                self.size -= 1
    
    @asynccontextmanager
    async def get_resource(self):
        """
        Get resource from pool with automatic release.
        
        Usage:
            async with pool.get_resource() as resource:
                await resource.do_something()
        """
        resource = await self.acquire()
        try:
            yield resource
        finally:
            await self.release(resource)
    
    async def fill_pool(self):
        """Pre-fill pool to min_size."""
        async with self.lock:
            while self.size < self.min_size:
                resource = await self._create_resource()
                await self.pool.put(resource)
                self.size += 1
    
    async def drain_pool(self):
        """Drain and cleanup all resources."""
        while not self.pool.empty():
            try:
                resource = self.pool.get_nowait()
                # Call cleanup if available
                if hasattr(resource, 'close'):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
            except asyncio.QueueEmpty:
                break
        
        async with self.lock:
            self.size = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "current_size": self.size,
            "max_size": self.max_size,
            "min_size": self.min_size,
            "available": self.pool.qsize(),
            "in_use": self.size - self.pool.qsize(),
            "total_created": self.created_count,
            "total_acquired": self.acquired_count,
            "total_released": self.released_count,
        }

