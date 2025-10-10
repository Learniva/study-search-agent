"""
Application Lifespan Manager.

Handles startup and shutdown events with proper resource management.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from agents.supervisor import SupervisorAgent
from api.dependencies import get_supervisor
from utils.monitoring import setup_logging, get_logger
from utils.scaling import get_distributed_state
from utils.async_tools import get_resource_manager
from config import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles:
    - Logging setup
    - Database initialization
    - Agent initialization
    - Distributed state setup
    - Resource cleanup
    """
    # ========================================================================
    # STARTUP
    # ========================================================================
    
    logger.info("🚀 Starting Multi-Agent Study & Grading System API v2.0")
    
    # Setup logging
    setup_logging()
    
    # Initialize database if available
    try:
        from database.core.async_engine import async_db_engine
        
        logger.info("📊 Initializing database connection pool...")
        health = await async_db_engine.health_check()
        
        if health:
            logger.info("✅ Database initialized successfully")
            
            # Start pool monitoring
            try:
                from database.monitoring import get_pool_monitor
                
                monitor = get_pool_monitor(async_db_engine.engine)
                await monitor.start_monitoring()
                logger.info("✅ Database pool monitoring started")
            except Exception as e:
                logger.warning(f"Pool monitoring failed: {e}")
        else:
            logger.warning("⚠️  Database health check failed")
            
    except ImportError:
        logger.warning("⚠️  Database module not available")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    
    # Initialize distributed state if Redis available
    if settings.redis_url:
        try:
            logger.info("🌐 Initializing distributed state management...")
            dist_state = get_distributed_state()
            await dist_state.register_instance()
            await dist_state.start_heartbeat()
            logger.info("✅ Distributed state initialized")
        except Exception as e:
            logger.warning(f"Distributed state failed: {e}")
    
    # Document loading is now handled via L2 Vector Store (pgvector)
    # Documents should be uploaded via POST /documents/upload API endpoint
    documents_dir = os.getenv("DOCUMENTS_DIR", "documents")
    if os.path.exists(documents_dir) and os.listdir(documents_dir):
        logger.info(f"📚 Documents directory found: {documents_dir}")
        logger.info("💡 Use POST /documents/upload to index documents in the vector store")
    
    # Initialize supervisor agent
    logger.info("🤖 Initializing Supervisor Agent...")
    try:
        llm_provider = os.getenv("LLM_PROVIDER", settings.llm_provider)
        supervisor = SupervisorAgent(llm_provider=llm_provider)
        
        # Set supervisor in dependency
        get_supervisor.set_supervisor(supervisor)
        
        logger.info("✅ Supervisor Agent initialized")
        logger.info("   • Study & Search Agent: Ready")
        logger.info("   • AI Grading Agent: Ready (Teachers only)")
        
    except Exception as e:
        logger.error(f"❌ Supervisor initialization failed: {e}")
        raise
    
    # Register resources
    resource_manager = get_resource_manager()
    await resource_manager.register_resource(
        "supervisor",
        supervisor,
        resource_type="agent",
        cleanup_func=lambda: logger.info("Supervisor cleaned up")
    )
    
    # Warm cache if enabled
    if settings.cache_enabled:
        try:
            from utils.cache import get_cache_optimizer
            
            logger.info("🔥 Warming cache...")
            optimizer = get_cache_optimizer()
            # Could load frequently accessed data here
            logger.info("✅ Cache warmed")
        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")
    
    logger.info("=" * 70)
    logger.info("✅ API Server Ready!")
    logger.info(f"   Docs: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info(f"   Health: http://{settings.api_host}:{settings.api_port}/health")
    logger.info("=" * 70)
    
    yield
    
    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    
    logger.info("🛑 Shutting down gracefully...")
    
    # Stop distributed state
    if settings.redis_url:
        try:
            dist_state = get_distributed_state()
            await dist_state.cleanup()
            logger.info("✅ Distributed state cleaned up")
        except Exception as e:
            logger.error(f"Distributed state cleanup error: {e}")
    
    # Stop database monitoring
    try:
        from database.monitoring import get_pool_monitor
        from database.core.async_engine import async_db_engine
        
        monitor = get_pool_monitor(async_db_engine.engine)
        await monitor.stop_monitoring()
        logger.info("✅ Database monitoring stopped")
    except Exception:
        pass
    
    # Close database connections
    try:
        from database.core.async_engine import async_db_engine
        await async_db_engine.close()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"Database cleanup error: {e}")
    
    # Cleanup resources
    resource_manager = get_resource_manager()
    await resource_manager.cleanup_all()
    
    logger.info("✅ Shutdown complete")

