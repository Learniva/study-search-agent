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

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Depends
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
    videos_router,
    profile_router,
    settings_router,
    help_router,
    integrations_router,
    billing_router,
    payments_router,
    auth_router,
    legacy_auth_router,
    concurrent_query_router,
)
from utils.rate_limiting import RateLimitMiddleware
from utils.monitoring import TracingMiddleware, get_logger, get_correlation_id
from utils.errors import BaseApplicationError, get_error_handler
from utils.auth import get_current_user
from api.dependencies import require_admin_role
from config import settings

from middleware.auth_gateway import AuthGatewayMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.csrf_protection import CSRFProtectionMiddleware

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
    redirect_slashes=False,  # Disable automatic redirect for trailing slashes
)


# ============================================================================
# Middleware Stack
# ============================================================================

# CORS - Enhanced security configuration for cookie-based authentication
# SECURITY: Never use ["*"] in production with allow_credentials=True
ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,https://localhost:3000"
).split(",")

# Filter out empty strings and validate origins
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

# Additional security headers for CORS (cookie-based auth)
CORS_HEADERS = [
    "Content-Type",
    "Authorization",  # Keep for backward compatibility during migration
    "X-Correlation-ID",
    "X-Trace-ID",
    "X-Tenant-ID",
    "X-CSP-Nonce",
    # CSRF protection (required for cookie-based auth)
    "X-CSRF-Token",
    # Frontend custom headers
    "X-User-Role",
    "X-User-ID", 
    "X-Thread-ID",
]

# Expose headers that client can read
CORS_EXPOSE_HEADERS = [
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-Total-Count",
    "X-CSRF-Token",  # Allow client to read CSRF token
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # REQUIRED for cookie-based auth
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=CORS_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Security Headers Middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    strict_mode=not settings.is_development,
    hsts_max_age=31536000,  # 1 year
    csp_report_uri="/api/security/csp-report" if not settings.is_development else None
)

# CSRF Protection Middleware (for cookie-based authentication)
app.add_middleware(
    CSRFProtectionMiddleware,
    exempt_paths={
        # Auth endpoints that don't need CSRF (login/register create new sessions)
        "/api/auth/login/",
        "/auth/login/",
        "/api/auth/register/",
        "/auth/register/",
        "/api/auth/google/callback",
        "/api/auth/google/callback/",
        "/auth/google/callback",
        "/auth/google/callback/",
    }
)

# Authentication Gateway Middleware
app.add_middleware(
    AuthGatewayMiddleware,
    exempt_paths=[
        # Health and docs
        "/health", "/", "/docs", "/redoc", "/openapi.json",
        # Auth endpoints (both prefixes)
        "/auth/google/callback", "/auth/google/callback/", "/auth/health", "/auth/error",
        "/api/auth/google/callback", "/api/auth/google/callback/",
        "/api/auth/google/login/", "/auth/google/login/",  # OAuth login initiation
        "/api/auth/login/", "/api/auth/register/", "/api/auth/validate-password/", "/api/auth/config/",
        "/auth/login/", "/auth/register/", "/auth/validate-password/", "/auth/config/"
    ]
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
app.include_router(concurrent_query_router)
app.include_router(documents_router)

# Grading Features (Teachers only)
app.include_router(grading_router)

# ML Features
app.include_router(ml_router)

# Video Downloads (available to all roles)
app.include_router(videos_router)

# Authentication (Public - no auth required)
app.include_router(auth_router)  # Comprehensive authentication with security features
app.include_router(legacy_auth_router)  # Legacy /auth prefix for backward compatibility

# User Management & Settings
app.include_router(profile_router)
app.include_router(settings_router)
app.include_router(help_router)
app.include_router(integrations_router)
app.include_router(billing_router)
app.include_router(payments_router)

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
# OAuth Test Page (for testing authentication)
# ============================================================================

from fastapi.responses import FileResponse

@app.get("/test-oauth", include_in_schema=False)
async def oauth_test_page():
    """Serve OAuth test page for testing Google authentication."""
    return FileResponse("test_oauth.html")


# ============================================================================
# Admin Endpoints
# ============================================================================

@app.post("/admin/reload", tags=["Admin"])
async def reload_documents(
    current_user: dict = Depends(get_current_user),
    _: str = Depends(require_admin_role)
):
    """
    Reload documents from disk (deprecated - use /documents/upload instead).
    
    Documents are now managed via the L2 Vector Store (pgvector).
    Use POST /documents/upload to index documents.
    
    **Requires:** Admin role (JWT authentication)
    """
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
async def get_cache_stats(
    current_user: dict = Depends(get_current_user),
    _: str = Depends(require_admin_role)
):
    """
    Get cache statistics.
    
    **Requires:** Admin role (JWT authentication)
    """
    try:
        stats = {}
        
        # Query cache stats
        try:
            from utils.cache import get_cache_optimizer
            optimizer = get_cache_optimizer()
            stats["query_cache"] = optimizer.get_stats()
            stats["query_cache_enabled"] = settings.cache_enabled
        except Exception as e:
            stats["query_cache_error"] = str(e)
        
        # Token cache stats
        try:
            from utils.auth.token_cache import get_token_cache
            token_cache = get_token_cache()
            stats["token_cache"] = token_cache.get_stats()
            stats["token_cache_enabled"] = True
        except Exception as e:
            stats["token_cache_error"] = str(e)
        
        # Response cache stats
        try:
            from utils.api.response_cache import get_response_cache
            response_cache = get_response_cache()
            stats["response_cache"] = response_cache.get_stats()
            stats["response_cache_enabled"] = True
        except Exception as e:
            stats["response_cache_error"] = str(e)
        
        return {
            "cache_stats": stats,
            "timestamp": get_correlation_id()
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/admin/instances", tags=["Admin"])
async def get_active_instances(
    current_user: dict = Depends(get_current_user),
    _: str = Depends(require_admin_role)
):
    """
    Get active service instances.
    
    Shows all running instances in distributed setup.
    
    **Requires:** Admin role (JWT authentication)
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


