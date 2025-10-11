"""
Async database operations with optimization.

High-performance async database queries with connection pooling,
caching, and monitoring.
"""

import asyncio
from typing import List, Dict, Any, Optional, TypeVar, Generic
from sqlalchemy import select, insert, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.core.async_engine import async_db_engine, execute_with_timeout
from database.models import GradingHistory, RubricModel
from utils.cache import get_cache_optimizer
from utils.monitoring import get_logger, track_query

logger = get_logger(__name__)
T = TypeVar('T')


class AsyncDatabaseOperations:
    """
    Async database operations with caching and optimization.
    
    Features:
    - Connection pooling
    - Query caching
    - Batch operations
    - Timeout handling
    - Performance tracking
    """
    
    def __init__(self):
        self.cache_optimizer = get_cache_optimizer()
        self.operation_count = 0
    
    async def get_with_cache(
        self,
        model_class,
        filter_kwargs: Dict[str, Any],
        cache_key: Optional[str] = None,
        ttl: int = 300
    ) -> Optional[Any]:
        """
        Get entity with caching.
        
        Args:
            model_class: SQLAlchemy model class
            filter_kwargs: Filter conditions
            cache_key: Custom cache key
            ttl: Cache TTL in seconds
            
        Returns:
            Model instance or None
        """
        # Generate cache key
        if cache_key is None:
            cache_key = f"{model_class.__name__}:{filter_kwargs}"
        
        # Define data loader
        async def load_from_db(key: str):
            async with async_db_engine.get_session() as session:
                query = select(model_class).filter_by(**filter_kwargs)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        
        # Get with optimization
        return await self.cache_optimizer.get_optimized(
            cache_key,
            load_from_db,
            prefetch=False
        )
    
    async def list_with_cache(
        self,
        model_class,
        filter_kwargs: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        cache_key: Optional[str] = None,
        ttl: int = 300
    ) -> List[Any]:
        """
        List entities with caching.
        
        Args:
            model_class: SQLAlchemy model class
            filter_kwargs: Optional filter conditions
            limit: Maximum results
            cache_key: Custom cache key
            ttl: Cache TTL in seconds
            
        Returns:
            List of model instances
        """
        filter_kwargs = filter_kwargs or {}
        
        # Generate cache key
        if cache_key is None:
            cache_key = f"{model_class.__name__}:list:{filter_kwargs}:{limit}"
        
        # Define data loader
        async def load_from_db(key: str):
            async with async_db_engine.get_session() as session:
                query = select(model_class).filter_by(**filter_kwargs).limit(limit)
                result = await session.execute(query)
                return result.scalars().all()
        
        # Get with optimization
        return await self.cache_optimizer.get_optimized(
            cache_key,
            load_from_db,
            prefetch=False
        )
    
    @track_query
    async def create_with_return(
        self,
        model_class,
        data: Dict[str, Any],
        invalidate_pattern: Optional[str] = None
    ) -> Any:
        """
        Create entity and return it.
        
        Args:
            model_class: SQLAlchemy model class
            data: Entity data
            invalidate_pattern: Cache pattern to invalidate
            
        Returns:
            Created entity
        """
        async with async_db_engine.get_session() as session:
            entity = model_class(**data)
            session.add(entity)
            await session.flush()
            await session.refresh(entity)
            
            # Invalidate related caches
            if invalidate_pattern:
                await self.cache_optimizer.invalidate(pattern=invalidate_pattern)
            
            self.operation_count += 1
            return entity
    
    @track_query
    async def bulk_create(
        self,
        model_class,
        data_list: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        Bulk create entities in batches.
        
        Args:
            model_class: SQLAlchemy model class
            data_list: List of entity data
            batch_size: Batch size for insertion
            
        Returns:
            Number of created entities
        """
        total_created = 0
        
        # Process in batches
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            
            async with async_db_engine.get_session() as session:
                stmt = insert(model_class).values(batch)
                await session.execute(stmt)
                total_created += len(batch)
        
        logger.info(f"Bulk created {total_created} {model_class.__name__} entities")
        self.operation_count += total_created
        
        return total_created
    
    @track_query
    async def update_with_return(
        self,
        model_class,
        filter_kwargs: Dict[str, Any],
        update_data: Dict[str, Any],
        invalidate_tags: Optional[List[str]] = None
    ) -> Optional[Any]:
        """
        Update entity and return it.
        
        Args:
            model_class: SQLAlchemy model class
            filter_kwargs: Filter conditions
            update_data: Data to update
            invalidate_tags: Cache tags to invalidate
            
        Returns:
            Updated entity or None
        """
        async with async_db_engine.get_session() as session:
            query = select(model_class).filter_by(**filter_kwargs)
            result = await session.execute(query)
            entity = result.scalar_one_or_none()
            
            if entity:
                for key, value in update_data.items():
                    setattr(entity, key, value)
                
                await session.flush()
                await session.refresh(entity)
                
                # Invalidate caches
                if invalidate_tags:
                    await self.cache_optimizer.invalidate(tags=invalidate_tags)
                
                self.operation_count += 1
                return entity
            
            return None
    
    @track_query
    async def delete_entity(
        self,
        model_class,
        filter_kwargs: Dict[str, Any],
        invalidate_pattern: Optional[str] = None
    ) -> bool:
        """
        Delete entity.
        
        Args:
            model_class: SQLAlchemy model class
            filter_kwargs: Filter conditions
            invalidate_pattern: Cache pattern to invalidate
            
        Returns:
            True if deleted, False if not found
        """
        async with async_db_engine.get_session() as session:
            query = delete(model_class).filter_by(**filter_kwargs)
            result = await session.execute(query)
            
            deleted = result.rowcount > 0
            
            if deleted and invalidate_pattern:
                await self.cache_optimizer.invalidate(pattern=invalidate_pattern)
            
            if deleted:
                self.operation_count += 1
            
            return deleted
    
    async def execute_raw_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Execute raw SQL query with timeout.
        
        Args:
            query: SQL query string
            params: Query parameters
            timeout: Timeout in seconds
            
        Returns:
            List of result dictionaries
        """
        from sqlalchemy import text
        
        async with async_db_engine.get_session() as session:
            stmt = text(query)
            
            if params:
                result = await execute_with_timeout(
                    session,
                    stmt.bindparams(**params),
                    timeout=timeout
                )
            else:
                result = await execute_with_timeout(
                    session,
                    stmt,
                    timeout=timeout
                )
            
            # Convert to dictionaries
            return [dict(row._mapping) for row in result]
    
    async def aggregate_query(
        self,
        model_class,
        aggregate_func,
        column,
        filter_kwargs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute aggregate query (COUNT, SUM, AVG, etc.).
        
        Args:
            model_class: SQLAlchemy model class
            aggregate_func: Aggregate function (func.count, func.sum, etc.)
            column: Column to aggregate
            filter_kwargs: Optional filter conditions
            
        Returns:
            Aggregate result
        """
        filter_kwargs = filter_kwargs or {}
        
        async with async_db_engine.get_session() as session:
            query = select(aggregate_func(column)).filter_by(**filter_kwargs)
            result = await session.execute(query)
            return result.scalar()
    
    async def paginated_query(
        self,
        model_class,
        page: int = 1,
        page_size: int = 50,
        filter_kwargs: Optional[Dict[str, Any]] = None,
        order_by = None
    ) -> Dict[str, Any]:
        """
        Paginated query with metadata.
        
        Args:
            model_class: SQLAlchemy model class
            page: Page number (1-indexed)
            page_size: Items per page
            filter_kwargs: Optional filter conditions
            order_by: Optional ordering
            
        Returns:
            Dictionary with items, total, page info
        """
        filter_kwargs = filter_kwargs or {}
        offset = (page - 1) * page_size
        
        async with async_db_engine.get_session() as session:
            # Count total
            count_query = select(func.count()).select_from(model_class).filter_by(**filter_kwargs)
            total_result = await session.execute(count_query)
            total = total_result.scalar()
            
            # Get page items
            query = select(model_class).filter_by(**filter_kwargs)
            
            if order_by is not None:
                query = query.order_by(order_by)
            
            query = query.limit(page_size).offset(offset)
            
            result = await session.execute(query)
            items = result.scalars().all()
            
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total,
                "has_prev": page > 1,
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operation statistics."""
        return {
            "total_operations": self.operation_count,
            "cache_stats": self.cache_optimizer.get_stats(),
        }


# Global instance
_async_db_ops: Optional[AsyncDatabaseOperations] = None


def get_async_db_ops() -> AsyncDatabaseOperations:
    """Get or create global async database operations instance."""
    global _async_db_ops
    if _async_db_ops is None:
        _async_db_ops = AsyncDatabaseOperations()
    return _async_db_ops


# Convenience functions
async def get_cached(model_class, **kwargs):
    """Get entity with caching."""
    ops = get_async_db_ops()
    return await ops.get_with_cache(model_class, kwargs)


async def list_cached(model_class, limit: int = 100, **kwargs):
    """List entities with caching."""
    ops = get_async_db_ops()
    return await ops.list_with_cache(model_class, kwargs, limit=limit)


async def create_async(model_class, data: Dict[str, Any]):
    """Create entity async."""
    ops = get_async_db_ops()
    return await ops.create_with_return(model_class, data)


async def update_async(model_class, filter_data: Dict[str, Any], update_data: Dict[str, Any]):
    """Update entity async."""
    ops = get_async_db_ops()
    return await ops.update_with_return(model_class, filter_data, update_data)


async def delete_async(model_class, **kwargs):
    """Delete entity async."""
    ops = get_async_db_ops()
    return await ops.delete_entity(model_class, kwargs)


