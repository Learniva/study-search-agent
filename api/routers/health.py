"""Health Check Router - System status endpoints."""

from fastapi import APIRouter, Depends
from datetime import datetime
import os

from api.models import HealthResponse
from api.dependencies import get_supervisor, get_optional_db
from utils.monitoring import get_metrics
from config import settings

router = APIRouter(prefix="", tags=["Health"])


@router.get("/", include_in_schema=True)
async def root():
    """API root endpoint with welcome message."""
    return {
        "message": "Multi-Agent Study & Grading System API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "Supervisor Pattern",
            "Study & Search Agent",
            "AI Grading Agent",
            "ML-Powered Features",
            "Horizontal Scaling",
            "Advanced Monitoring"
        ]
    }


@router.get("/health", response_model=HealthResponse)
async def health_check(
    supervisor=Depends(get_supervisor)
):
    """
    Health check endpoint.
    
    Returns system status and component availability.
    """
    documents_dir = os.getenv("DOCUMENTS_DIR", "documents")
    documents_loaded = os.path.exists(documents_dir) and bool(os.listdir(documents_dir))
    
    # Check ML features
    ml_available = False
    try:
        from utils.ml import get_query_learner
        ml_available = True
    except ImportError:
        pass
    
    # Check database availability without triggering connection
    database_available = False
    try:
        from database.core.async_engine import async_db_engine
        # Just check if the engine exists, don't try to connect
        database_available = async_db_engine is not None
    except ImportError:
        pass


@router.get("/health/database", tags=["Monitoring"])
async def database_health():
    """
    Database connection pool health check.
    
    Returns detailed information about the database connection pool:
    - Current utilization
    - Pool configuration
    - Connection statistics
    - Health status
    """
    try:
        from database.core.async_engine import async_db_engine
        from database.monitoring.pool_monitor import get_pool_monitor, monitor_pool_health
        
        # Get pool monitor
        pool_monitor = get_pool_monitor(async_db_engine.engine)
        
        # Get current pool stats
        stats = pool_monitor.get_stats()
        
        # Perform health check
        health_status = await monitor_pool_health(async_db_engine.engine)
        
        # Get utilization trend (last 5 minutes)
        trend = pool_monitor.get_utilization_trend(minutes=5)
        
        return {
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "pool_stats": stats,
            "health_check": health_status,
            "utilization_trend": trend,
            "configuration": {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_recycle": settings.db_pool_recycle,
                "pool_timeout": settings.db_pool_timeout,
                "statement_timeout": settings.db_statement_timeout,
                "connection_retries": settings.db_connection_retries,
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check database health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception:
        # Database module exists but has issues
        database_available = False
    
    return HealthResponse(
        status="healthy",
        supervisor_ready=supervisor is not None,
        database_available=database_available,
        ml_features_available=ml_available,
        documents_loaded=documents_loaded,
        timestamp=datetime.utcnow(),
        version="2.0.0"
    )


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    """
    if not settings.enable_metrics:
        return {"error": "Metrics not enabled"}
    
    metrics = get_metrics()
    return metrics.get_metrics()


@router.get("/ready")
async def readiness_check(supervisor=Depends(get_supervisor)):
    """
    Kubernetes readiness probe.
    
    Returns 200 if service is ready to accept traffic.
    """
    if supervisor is None:
        return {"ready": False}, 503
    
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe.
    
    Returns 200 if service is alive (even if not ready).
    """
    return {"alive": True}

