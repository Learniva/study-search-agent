"""
Application lifespan management for authentication-only mode.

This module handles the startup and shutdown of the FastAPI application
with minimal dependencies, focusing only on authentication functionality.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.settings import settings

# Use basic logging since we want to avoid complex monitoring dependencies
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Simplified application lifespan manager for authentication-only mode.
    
    This version avoids any AI/ML dependencies and focuses only on
    basic database connectivity and authentication functionality.
    """
    logger.info("🚀 Starting Authentication Service")
    
    # Initialize database connection if available
    try:
        from database import init_db, check_db_connection
        init_db()
        if check_db_connection():
            logger.info("✅ Database connection established")
        else:
            logger.warning("⚠️  Database connection check failed")
    except ImportError:
        logger.warning("⚠️  Database modules not available")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization failed: {e}")
    
    # Skip all AI/agent initialization - not needed for auth
    logger.info("🚫 Skipping agent initialization (auth-only mode)")
    logger.info("✅ Authentication Service ready")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Authentication Service")
    
    # Basic database cleanup if available
    try:
        from database import close_db
        close_db()
        logger.info("✅ Database connections closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Database cleanup warning: {e}")
    
    logger.info("✅ Shutdown complete")

