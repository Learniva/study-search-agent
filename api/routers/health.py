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
    supervisor=Depends(get_supervisor),
    db=Depends(get_optional_db)
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
    
    return HealthResponse(
        status="healthy",
        supervisor_ready=supervisor is not None,
        database_available=db is not None,
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

