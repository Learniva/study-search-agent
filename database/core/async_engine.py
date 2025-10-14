"""
Async database engine with connection pooling and optimization.

Features:
- Async SQLAlchemy with asyncpg driver
- Connection pooling with configurable size
- Health checks and reconnection logic
- Query timeout handling
- Performance monitoring
"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import asyncio
import random

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import text, event

from config import settings


class AsyncDatabaseEngine:
    """Async database engine manager with connection pooling."""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
    
    def create_engine(self) -> AsyncEngine:
        """Create async database engine with optimized settings."""
        
        # Choose pool class based on configuration (async requires AsyncAdaptedQueuePool)
        pool_class = AsyncAdaptedQueuePool if not settings.testing else NullPool
        
        engine = create_async_engine(
            settings.async_database_url,
            # Connection pool settings
            poolclass=pool_class,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_timeout=settings.db_pool_timeout,
            # Performance settings
            echo=settings.db_echo,
            echo_pool=settings.debug,
            # Execution options
            future=True,
            # Query execution timeout
            connect_args={"command_timeout": settings.db_command_timeout},
            # Connection pooling optimizations
            pool_use_lifo=True,  # Last In, First Out - better cache locality
            reset_on_return="rollback",  # Auto-rollback on return to pool
        )
        
        # Register event listeners for monitoring
        self._register_events(engine.sync_engine)
        
        return engine
    
    def _register_events(self, engine):
        """Register SQLAlchemy event listeners for monitoring."""
        
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Track new connections."""
            if settings.debug:
                print(f"📊 Database: New connection established")
        
        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout from pool."""
            if settings.debug:
                print(f"📊 Database: Connection checked out from pool")
        
        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Track connection checkin to pool."""
            if settings.debug:
                print(f"📊 Database: Connection returned to pool")
    
    @property
    def engine(self) -> AsyncEngine:
        """Get or create async engine."""
        if self._engine is None:
            self._engine = self.create_engine()
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return self._session_factory
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with automatic cleanup and retry logic.
        
        Usage:
            async with db_engine.get_session() as session:
                result = await session.execute(query)
        """
        from sqlalchemy.exc import DBAPIError, OperationalError
        from config import settings
        import time
        
        # Retry configuration
        max_retries = settings.db_connection_retries
        retry_backoff = settings.db_retry_backoff
        
        for attempt in range(max_retries + 1):
            try:
                async with self.session_factory() as session:
                    # Set statement timeout if configured
                    if settings.db_statement_timeout > 0:
                        await session.execute(
                            text(f"SET statement_timeout = {settings.db_statement_timeout}")
                        )
                    
                    try:
                        yield session
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        raise
                    finally:
                        await session.close()
                        
                # If we get here, session was successful
                return
                
            except (DBAPIError, OperationalError) as e:
                # Connection errors that might be worth retrying
                if attempt < max_retries:
                    # Calculate exponential backoff with jitter
                    backoff = retry_backoff * (2 ** attempt) * (0.5 + 0.5 * random.random())
                    print(f"Database connection error, retrying in {backoff:.2f}s: {e}")
                    await asyncio.sleep(backoff)
                else:
                    # Last attempt failed, re-raise
                    print(f"Database connection failed after {max_retries} retries: {e}")
                    raise
    
    async def health_check(self) -> bool:
        """Check database connection health."""
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"❌ Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database engine and cleanup connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            print("📊 Database: Engine closed and connections cleaned up")


# Global async database engine
async_db_engine = AsyncDatabaseEngine()


# Dependency for FastAPI
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions."""
    async with async_db_engine.get_session() as session:
        yield session


# Utility functions
async def execute_with_timeout(
    session: AsyncSession,
    query,
    timeout: int = 30
):
    """Execute query with timeout."""
    try:
        result = await asyncio.wait_for(
            session.execute(query),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"Query exceeded {timeout}s timeout")

