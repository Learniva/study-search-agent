"""
Application lifespan management with full agent initialization.

This module handles the startup and shutdown of the FastAPI application,
including database initialization, supervisor agent setup, and all ML components.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.settings import settings
from utils.monitoring import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Full application lifespan manager with complete AI/ML initialization.
    
    This version initializes all system components including:
    - Database connections
    - Supervisor agent with study and grading capabilities
    - Vector store for RAG
    - Caching systems
    - Performance monitoring
    """
    logger.info("🚀 Starting Multi-Agent Study & Grading System")
    
    # =========================================================================
    # Database Initialization
    # =========================================================================
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
    
    # =========================================================================
    # Vector Store Initialization (for RAG)
    # =========================================================================
    try:
        from database.operations.document_processing import get_document_processor
        doc_processor = get_document_processor()
        logger.info("✅ Vector store initialized for document Q&A")
    except Exception as e:
        logger.warning(f"⚠️  Vector store initialization failed: {e}")
    
    # =========================================================================
    # Supervisor Agent Initialization
    # =========================================================================
    try:
        # Workaround for LangChain tracing import issue
        import os
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        
        logger.info("🔄 Importing SupervisorAgent...")
        from agents.supervisor.core import SupervisorAgent
        from api.dependencies import get_supervisor
        
        # Get LLM provider from environment
        llm_provider = os.getenv("LLM_PROVIDER", "gemini")
        logger.info(f"🤖 Initializing Supervisor Agent with {llm_provider.upper()}")
        
        # Initialize supervisor
        logger.info("🔄 Creating SupervisorAgent instance...")
        supervisor = SupervisorAgent(llm_provider=llm_provider)
        
        logger.info("🔄 Setting supervisor in dependency...")
        # Set supervisor in dependency
        get_supervisor.set_supervisor(supervisor)
        
        logger.info("✅ Supervisor Agent initialized successfully")
        logger.info("   → Study Agent: Ready for research, Q&A, and animations")
        logger.info("   → Grading Agent: Ready for essay grading, code review")
        
    except ImportError as e:
        import traceback
        if "tracing_enabled" in str(e):
            logger.error("❌ LangChain version incompatibility detected")
            logger.error(f"   → Error: {e}")
            logger.error(f"   → Traceback: {traceback.format_exc()}")
            logger.error("   → Try: pip install --upgrade langchain-core langgraph")
            logger.error("   → Or set: LANGCHAIN_TRACING_V2=false in .env")
        else:
            logger.error(f"❌ Supervisor Agent initialization failed: {e}")
            logger.error(f"   → Traceback: {traceback.format_exc()}")
        logger.error("   Application will start but AI features will be unavailable")
    except Exception as e:
        import traceback
        logger.error(f"❌ Supervisor Agent initialization failed: {e}")
        logger.error(f"   → Traceback: {traceback.format_exc()}")
        logger.error("   Application will start but AI features will be unavailable")
    
    # =========================================================================
    # Cache Initialization
    # =========================================================================
    try:
        if settings.cache_enabled:
            from utils.cache import get_cache_optimizer
            cache_optimizer = get_cache_optimizer()
            logger.info("✅ Query caching enabled")
    except Exception as e:
        logger.warning(f"⚠️  Cache initialization failed: {e}")
    
    # =========================================================================
    # Performance Monitoring
    # =========================================================================
    try:
        from utils.routing.performance import get_performance_monitor
        perf_monitor = get_performance_monitor()
        logger.info("✅ Performance monitoring initialized")
    except Exception as e:
        logger.warning(f"⚠️  Performance monitoring initialization failed: {e}")
    
    logger.info("✅ Multi-Agent Study & Grading System ready")
    logger.info("📚 Document upload: POST /documents/upload")
    logger.info("💬 Query endpoint: POST /query/")
    logger.info("📝 Grading endpoint: POST /grading/grade")
    
    yield
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    logger.info("🛑 Shutting down Multi-Agent Study & Grading System")
    
    # Database cleanup
    try:
        from database import close_db
        close_db()
        logger.info("✅ Database connections closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Database cleanup warning: {e}")
    
    # Agent cleanup
    try:
        get_supervisor.supervisor = None
        logger.info("✅ Agents cleaned up")
    except Exception as e:
        logger.warning(f"Agent cleanup warning: {e}")
    
    logger.info("✅ Shutdown complete")

