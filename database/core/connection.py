"""
Database connection and session management.

Provides SQLAlchemy engine and session management for PostgreSQL.
"""

import os
from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

from database.models import Base

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/grading_system"
)

# OPTIMIZED: Create engine with connection pooling for concurrent requests
# This saves 50-100ms per request by reusing connections
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,  # Keep 10 connections ready (handles ~100 req/sec)
    max_overflow=20,  # Allow 20 extra during peaks (total 30 connections)
    pool_pre_ping=True,  # Verify connection health before use (prevents stale connections)
    pool_recycle=3600,  # Recycle connections every hour (prevents timeouts)
    pool_timeout=30,  # Wait max 30s for available connection
    echo=False,  # Set to True for SQL query logging (development)
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_engine():
    """
    Get the SQLAlchemy engine.
    
    Returns:
        SQLAlchemy engine instance
    """
    return engine


def get_session() -> Session:
    """
    Get a new database session.
    
    Returns:
        SQLAlchemy Session
        
    Note: Remember to close the session after use:
        session = get_session()
        try:
            # use session
        finally:
            session.close()
    """
    return SessionLocal()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_db() as db:
            user = db.query(User).first()
            
    Yields:
        SQLAlchemy Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database.
    
    Creates all tables if they don't exist.
    Enables pgvector extension for Agentic RAG (Phase 1.1).
    This should be called once at application startup.
    """
    print("🗄️  Initializing PostgreSQL database...")
    
    try:
        # Test connection
        with engine.connect() as conn:
            print(f"✅ Connected to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")
            
            # Enable pgvector extension (Phase 1.1: Agentic RAG)
            try:
                from sqlalchemy import text
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print("✅ pgvector extension enabled (L2 Vector Store ready)")
            except Exception as e:
                print(f"⚠️  pgvector extension not available: {e}")
                print("   Vector similarity search will be limited.")
                print("   To enable pgvector:")
                print("   1. Install: sudo apt-get install postgresql-<version>-pgvector")
                print("   2. Or on macOS: brew install pgvector")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
        print("   • L2 Vector Store (document_vectors)")
        print("   • L3 Learning Store (grade_exceptions)")
        print("   • RAG Query Logs (rag_query_logs)")
        
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("\n⚠️  Database features will be disabled.")
        print("   To enable database features:")
        print("   1. Install PostgreSQL")
        print("   2. Set DATABASE_URL in .env")
        print("   3. Restart the application")
        return False


def reset_db():
    """
    Reset the database (drop and recreate all tables).
    
    WARNING: This will delete all data!
    Use only for development/testing.
    """
    print("⚠️  WARNING: This will delete all database data!")
    
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("🗑️  All tables dropped")
    
    # Recreate tables
    Base.metadata.create_all(bind=engine)
    print("✅ Tables recreated")


def check_db_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def get_pool_status() -> dict:
    """
    Get connection pool statistics.
    
    OPTIMIZATION: Monitor pool usage to identify bottlenecks.
    
    Returns:
        Dict with pool statistics
    """
    pool = engine.pool
    return {
        'size': pool.size(),  # Current pool size
        'checked_in': pool.checkedin(),  # Available connections
        'checked_out': pool.checkedout(),  # In-use connections
        'overflow': pool.overflow(),  # Overflow connections
        'max_overflow': pool._max_overflow,  # Max overflow allowed
        'pool_size': pool._pool.maxsize,  # Configured pool size
    }


# Dependency for FastAPI endpoints
async def get_db_dependency() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage in FastAPI:
        @app.get("/users")
        async def get_users(db: Session = Depends(get_db_dependency)):
            users = db.query(User).all()
            return users
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db():
    """
    Close database connection and dispose of the engine.
    
    Use this when shutting down the application.
    """
    engine.dispose()


def execute_raw_sql(sql: str, params: dict = None):
    """
    Execute raw SQL query.
    
    Args:
        sql: SQL query string
        params: Optional parameters for the query
        
    Returns:
        Query result
    """
    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text(sql), params or {})
        conn.commit()
        return result

