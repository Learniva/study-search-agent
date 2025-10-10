"""Grading Router - Grading history and session endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from api.models import (
    GradingHistoryResponse,
    GradingHistoryItem,
    RubricTemplate,
    RubricListResponse,
    ProfessorFeedbackRequest
)
from api.dependencies import require_teacher_role, get_optional_db, pagination_params
from utils.monitoring import get_logger
from config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/grading", tags=["Grading"])


@router.get("/history/{professor_id}", response_model=GradingHistoryResponse)
async def get_grading_history(
    professor_id: str,
    _: str = Depends(require_teacher_role),
    db=Depends(get_optional_db),
    pagination: dict = Depends(pagination_params)
):
    """
    Get grading history for a professor.
    
    **Requires:** Teacher or Admin role
    """
    if not db:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )
    
    try:
        from database.operations import get_grading_history
        
        history_items = get_grading_history(
            db,
            professor_id,
            limit=pagination["page_size"],
            offset=pagination["offset"]
        )
        
        history = [
            GradingHistoryItem(
                id=item.id,
                session_id=item.session_id,
                student_id=item.student_id,
                student_name=item.student_name,
                assignment_id=item.assignment_id,
                assignment_name=item.assignment_name,
                rubric_id=item.rubric_id,
                grade=item.grade,
                feedback=item.feedback,
                created_at=item.created_at
            )
            for item in history_items
        ]
        
        return GradingHistoryResponse(
            professor_id=professor_id,
            history=history,
            total=len(history)
        )
        
    except Exception as e:
        logger.error(f"Failed to get grading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_grading_session(
    session_id: str,
    _: str = Depends(require_teacher_role),
    db=Depends(get_optional_db)
):
    """
    Get details of a specific grading session.
    
    **Requires:** Teacher or Admin role
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        from database.operations import get_grading_by_session
        
        session = get_grading_by_session(db, session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session.session_id,
            "student_id": session.student_id,
            "student_name": session.student_name,
            "assignment_id": session.assignment_id,
            "assignment_name": session.assignment_name,
            "rubric_id": session.rubric_id,
            "grade": session.grade,
            "feedback": session.feedback,
            "created_at": session.created_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rubrics/{professor_id}", response_model=RubricListResponse)
async def get_rubrics(
    professor_id: str,
    _: str = Depends(require_teacher_role),
    db=Depends(get_optional_db)
):
    """
    Get rubric templates for a professor.
    
    **Requires:** Teacher or Admin role
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        from database.operations import get_rubric_templates
        
        templates = get_rubric_templates(db, professor_id)
        
        rubrics = [
            RubricTemplate(
                id=t.id,
                rubric_id=t.rubric_id,
                professor_id=t.professor_id,
                rubric_name=t.rubric_name,
                rubric_data=t.rubric_data,
                created_at=t.created_at
            )
            for t in templates
        ]
        
        return RubricListResponse(
            rubrics=rubrics,
            total=len(rubrics)
        )
        
    except Exception as e:
        logger.error(f"Failed to get rubrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rubrics")
async def create_rubric(
    rubric: RubricTemplate,
    _: str = Depends(require_teacher_role),
    db=Depends(get_optional_db)
):
    """
    Create a new rubric template.
    
    **Requires:** Teacher or Admin role
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        from database.operations import save_rubric_template
        
        saved = save_rubric_template(
            db,
            rubric.rubric_id,
            rubric.professor_id,
            rubric.rubric_name,
            rubric.rubric_data
        )
        
        return {
            "message": "Rubric created successfully",
            "rubric_id": rubric.rubric_id
        }
        
    except Exception as e:
        logger.error(f"Failed to create rubric: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_grading_feedback(
    feedback: ProfessorFeedbackRequest,
    _: str = Depends(require_teacher_role),
    db=Depends(get_optional_db)
):
    """
    Submit professor feedback on AI grading.
    
    Used to improve grading accuracy through ML.
    
    **Requires:** Teacher or Admin role
    """
    try:
        # Try to use ML features if available
        from utils.ml import get_adaptive_rubric_manager
        
        manager = get_adaptive_rubric_manager()
        
        # Record feedback for learning
        manager.record_grading_feedback(
            rubric_id=feedback.rubric_id,
            ai_grade=feedback.original_grade,
            actual_grade=feedback.actual_grade,
            submission_text=feedback.submission_text,
            criteria_adjustments=feedback.criteria_adjustments or {}
        )
        
        logger.info(f"Grading feedback recorded for session {feedback.session_id}")
        
        return {
            "message": "Feedback recorded successfully",
            "will_improve": "yes"
        }
        
    except ImportError:
        # ML features not available
        logger.warning("ML features not available for feedback")
        return {
            "message": "Feedback received but ML features not available",
            "will_improve": "no"
        }
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

