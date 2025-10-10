"""ML Features Router - Machine learning and adaptive features endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from api.models import (
    FeedbackRequest,
    MLProfileResponse,
    MLStatsResponse
)
from api.dependencies import get_optional_db
from utils.monitoring import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ml", tags=["ML Features"])


@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit user feedback on a response.
    
    Used to improve query routing and response quality.
    """
    try:
        from utils.ml import get_query_learner
        
        learner = get_query_learner()
        
        # Record feedback
        learner.record_query(
            query=feedback.question,
            response=feedback.response,
            rating=feedback.rating,
            helpful=feedback.helpful,
            user_id=feedback.user_id
        )
        
        logger.info(
            f"Feedback recorded",
            thread_id=feedback.thread_id,
            rating=feedback.rating
        )
        
        return {
            "message": "Feedback recorded successfully",
            "thank_you": True
        }
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ML features not available"
        )
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/{user_id}", response_model=MLProfileResponse)
async def get_user_profile(user_id: str):
    """
    Get ML-based user profile.
    
    Returns learning preferences and usage statistics.
    """
    try:
        from utils.ml import get_user_profile_manager
        
        manager = get_user_profile_manager()
        profile = manager.get_profile(user_id)
        
        if not profile:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
        return MLProfileResponse(
            user_id=user_id,
            query_count=profile.get("query_count", 0),
            successful_queries=profile.get("successful_queries", 0),
            avg_rating=profile.get("avg_rating"),
            preferences=profile.get("preferences", {}),
            learning_stats=profile.get("learning_stats", {})
        )
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ML features not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=MLStatsResponse)
async def get_ml_stats():
    """
    Get ML system statistics.
    
    Returns overall system performance and usage metrics.
    """
    try:
        from utils.ml import get_query_learner
        from utils.routing import get_performance_monitor
        
        learner = get_query_learner()
        monitor = get_performance_monitor()
        
        stats = learner.get_stats()
        perf_stats = monitor.get_stats()
        
        return MLStatsResponse(
            total_queries=stats.get("total_queries", 0),
            unique_users=stats.get("unique_users", 0),
            avg_rating=stats.get("avg_rating", 0.0),
            popular_topics=stats.get("popular_topics", []),
            performance_metrics=perf_stats
        )
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ML features not available"
        )
    except Exception as e:
        logger.error(f"Failed to get ML stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_metrics():
    """
    Get tool performance metrics.
    
    Returns performance-based routing statistics.
    """
    try:
        from utils.routing import get_performance_router
        
        router = get_performance_router()
        stats = router.get_stats()
        
        return {
            "tool_performance": stats.get("tool_stats", {}),
            "routing_decisions": stats.get("routing_stats", {}),
            "recommendations": stats.get("recommendations", [])
        }
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Performance routing not available"
        )
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consistency/{professor_id}")
async def get_grading_consistency(professor_id: str):
    """
    Get grading consistency metrics for a professor.
    
    Shows how consistent the professor's grading is over time.
    """
    try:
        from utils.ml import get_adaptive_rubric_manager
        
        manager = get_adaptive_rubric_manager()
        stats = manager.get_professor_consistency(professor_id)
        
        return {
            "professor_id": professor_id,
            "consistency_score": stats.get("consistency_score", 0.0),
            "total_gradings": stats.get("total_gradings", 0),
            "avg_deviation": stats.get("avg_deviation", 0.0),
            "trending": stats.get("trending", "stable")
        }
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ML features not available"
        )
    except Exception as e:
        logger.error(f"Failed to get consistency: {e}")
        raise HTTPException(status_code=500, detail=str(e))

