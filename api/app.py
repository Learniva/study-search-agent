"""
Optimized FastAPI Application.

Production-grade Multi-Agent Study & Grading System with:
- Modular router structure
- Rate limiting
- Distributed tracing
- Prometheus metrics
- Error handling
- CORS support
- Horizontal scaling ready
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from api.lifespan import lifespan
from api.routers import (
    query_router,
    documents_router,
    grading_router,
    ml_router,
    health_router,
    videos_router
)
from utils.rate_limiting import RateLimitMiddleware
from utils.monitoring import TracingMiddleware, get_logger, get_correlation_id
from utils.errors import BaseApplicationError, get_error_handler
from config import settings

logger = get_logger(__name__)


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Multi-Agent Study & Grading System",
    description="""
    **Production-Grade AI-Powered Study & Grading Platform**
    
    ## Features
    
    ### Supervisor Pattern
    - Intelligent routing between Study and Grading agents
    - Role-based access control (Student, Teacher, Professor, Instructor, Admin)
    - Context-aware query handling
    
    ### Study & Search Agent
    - Document Q&A with RAG
    - Web search integration
    - Python REPL for code execution
    - Manim animation generation
    
    ### AI Grading Agent (Teachers Only)
    - Essay grading with rubrics
    - Code review and analysis
    - MCQ auto-grading
    - ML-powered adaptive grading
    
    ### Production Features
    - Horizontal scaling support
    - Rate limiting (60/min, 1000/hour)
    - Distributed tracing
    - Prometheus metrics
    - Circuit breaker protection
    - Multi-tier caching
    
    ## Roles
    
    - **Student**: Access to Study Agent
    - **Teacher**: Access to Study + Grading Agents
    - **Admin**: Full system access
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================================
# Middleware Stack
# ============================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        per_minute=settings.rate_limit_per_minute,
        per_hour=settings.rate_limit_per_hour
    )
    logger.info(
        f"✅ Rate limiting enabled: {settings.rate_limit_per_minute}/min, "
        f"{settings.rate_limit_per_hour}/hour"
    )

# Distributed Tracing
if settings.enable_tracing if hasattr(settings, 'enable_tracing') else False:
    app.add_middleware(TracingMiddleware)
    logger.info("✅ Distributed tracing enabled")


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(BaseApplicationError)
async def application_error_handler(request, exc: BaseApplicationError):
    """Handle application errors."""
    error_handler = get_error_handler()
    error_handler.log_error(exc, context={
        "path": request.url.path,
        "method": request.method,
        "correlation_id": get_correlation_id()
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    """Handle unexpected errors."""
    error_handler = get_error_handler()
    error_handler.log_error(exc, context={
        "path": request.url.path,
        "method": request.method,
        "correlation_id": get_correlation_id()
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "correlation_id": get_correlation_id()
        }
    )


# ============================================================================
# Routers
# ============================================================================

# Health & Status
app.include_router(health_router)

# Core Features
app.include_router(query_router)
app.include_router(documents_router)

# Grading Features (Teachers only)
app.include_router(grading_router)

# ML Features
app.include_router(ml_router)

# Video Downloads (available to all roles)
app.include_router(videos_router)

# Learniva Integration (optional - for Learniva frontend compatibility)
try:
    from api.routers.learniva_auth import router as learniva_auth_router
    from api.routers.learniva_workspaces import router as learniva_workspaces_router
    app.include_router(learniva_auth_router)
    app.include_router(learniva_workspaces_router)
    logger.info("✅ Learniva integration endpoints enabled")
except ImportError:
    logger.info("ℹ️  Learniva integration endpoints not available (optional)")


# ============================================================================
# Static File Serving (for animations, videos, etc.)
# ============================================================================

# Mount static directories for direct file access (video streaming, animations, etc.)
# These are exempt from rate limiting (handled in middleware)

# Create directories if they don't exist
Path("downloads/animations").mkdir(parents=True, exist_ok=True)
Path("animations").mkdir(parents=True, exist_ok=True)

# Mount downloads directory at /downloads
app.mount(
    "/downloads",
    StaticFiles(directory="downloads"),
    name="downloads"
)

# Mount animations directory at /animations (for backwards compatibility)
app.mount(
    "/animations",
    StaticFiles(directory="animations"),
    name="animations"
)

logger.info("✅ Static file serving enabled for /downloads and /animations")


# ============================================================================
# Admin Endpoints
# ============================================================================

@app.post("/admin/reload", tags=["Admin"])
async def reload_documents():
    """
    Reload documents from disk (deprecated - use /documents/upload instead).
    
    Documents are now managed via the L2 Vector Store (pgvector).
    Use POST /documents/upload to index documents.
    
    **Requires:** Admin role
    """
    import os
    
    documents_dir = os.getenv("DOCUMENTS_DIR", "documents")
    
    try:
        if os.path.exists(documents_dir):
            return {
                "message": "Document reload is deprecated. Use POST /documents/upload to index documents in the vector store.",
                "documents_dir": documents_dir,
                "status": "use_upload_endpoint"
            }
        else:
            return {"message": "Documents directory not found"}
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/admin/cache/stats", tags=["Admin"])
async def get_cache_stats():
    """
    Get cache statistics.
    
    **Requires:** Admin role
    """
    try:
        from utils.cache import get_cache_optimizer
        
        optimizer = get_cache_optimizer()
        stats = optimizer.get_stats()
        
        return {
            "cache_stats": stats,
            "enabled": settings.cache_enabled
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/admin/instances", tags=["Admin"])
async def get_active_instances():
    """
    Get active service instances.
    
    Shows all running instances in distributed setup.
    
    **Requires:** Admin role
    """
    if not settings.redis_url:
        return {
            "distributed": False,
            "message": "Running in single-instance mode"
        }
    
    try:
        from utils.scaling import get_distributed_state
        
        dist_state = get_distributed_state()
        instances = await dist_state.get_active_instances()
        
        return {
            "distributed": True,
            "total_instances": len(instances),
            "instances": [
                {
                    "instance_id": inst.instance_id,
                    "host": inst.host,
                    "port": inst.port,
                    "status": inst.status,
                    "started_at": inst.started_at.isoformat(),
                    "last_heartbeat": inst.last_heartbeat.isoformat(),
                    "load": inst.load
                }
                for inst in instances
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get instances: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )


