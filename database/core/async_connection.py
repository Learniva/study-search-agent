"""
Async Database Connection and Session Management

Provides async SQLAlchemy engine and session management for FastAPI.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

# Create async engine
async_engine = create_async_engine(
    settings.async_database_url,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    echo=settings.db_echo,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions.
    
    Usage:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(User))
            users = result.scalars().all()
            return users
    
    Yields:
        AsyncSession
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_async_db():
    """
    Initialize async database connection.
    
    Should be called during app startup.
    """
    try:
        async with async_engine.begin() as conn:
            logger.info("✅ Async database engine initialized")
            return True
    except Exception as e:
        logger.error(f"❌ Async database initialization failed: {e}")
        return False


async def close_async_db():
    """
    Close async database connection.
    
    Should be called during app shutdown.
    """
    await async_engine.dispose()
    logger.info("🔌 Async database engine disposed")


__all__ = [
    'async_engine',
    'AsyncSessionLocal',
    'get_session',
    'init_async_db',
    'close_async_db',
]

