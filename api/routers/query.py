"""Query Router - Supervisor Agent endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from api.models import QueryRequest, QueryResponse, ConversationHistoryResponse
from api.dependencies import get_supervisor, get_or_create_correlation_id
from utils.monitoring import get_logger, track_query, get_metrics
from utils.errors import handle_errors
from config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])


@router.post("/", response_model=QueryResponse)
@handle_errors(raise_on_error=True)
async def query_supervisor(
    request: QueryRequest,
    supervisor=Depends(get_supervisor),
    correlation_id: str = Depends(get_or_create_correlation_id)
):
    """
    Query the supervisor agent.
    
    The supervisor intelligently routes between Study and Grading agents
    based on user role and query intent.
    
    **Roles:**
    - **student**: Access to Study Agent only
    - **teacher**: Access to both Study and Grading Agents
    - **admin**: Full access to all features
    """
    logger.info(
        f"Query received",
        user_role=request.user_role,
        thread_id=request.thread_id,
        correlation_id=correlation_id
    )
    
    # Track query
    track_query(request.question, request.user_role)
    
    # Query supervisor
    try:
        answer = await supervisor.aquery(
            question=request.question,
            thread_id=request.thread_id,
            user_role=request.user_role,
            user_id=request.user_id,
            professor_id=request.professor_id,
            student_id=request.student_id,
            student_name=request.student_name,
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            assignment_name=request.assignment_name
        )
        
        # Track metrics
        metrics = get_metrics()
        metrics.track_request(
            method="POST",
            endpoint="/query",
            status_code=200,
            duration=0.0  # Would need to track actual duration
        )
        
        return QueryResponse(
            answer=answer,
            thread_id=request.thread_id,
            metadata={"correlation_id": correlation_id}
        )
        
    except Exception as e:
        logger.error(f"Query failed: {e}", correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def query_supervisor_stream(
    request: QueryRequest,
    supervisor=Depends(get_supervisor),
    correlation_id: str = Depends(get_or_create_correlation_id)
):
    """
    Query supervisor with streaming response.
    
    Returns Server-Sent Events (SSE) stream for real-time responses.
    """
    if not settings.enable_streaming:
        raise HTTPException(
            status_code=503,
            detail="Streaming is not enabled"
        )
    
    logger.info(
        f"Streaming query received",
        user_role=request.user_role,
        thread_id=request.thread_id
    )
    
    async def generate_stream():
        """Generate SSE stream."""
        try:
            # Query supervisor (would need streaming support in agent)
            answer = await supervisor.aquery(
                question=request.question,
                thread_id=request.thread_id,
                user_role=request.user_role,
                user_id=request.user_id
            )
            
            # Stream answer in chunks
            chunk_size = 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i+chunk_size]
                yield f"data: {chunk}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


@router.get("/history/{thread_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    thread_id: str,
    supervisor=Depends(get_supervisor)
):
    """
    Get conversation history for a thread.
    
    Returns all messages in the conversation thread.
    """
    try:
        messages = supervisor.get_conversation_history(thread_id)
        
        return ConversationHistoryResponse(
            thread_id=thread_id,
            messages=messages,
            total_messages=len(messages)
        )
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/{role}")
async def get_capabilities(role: str):
    """
    Get available capabilities for a role.
    
    Returns list of features accessible to the specified role.
    """
    if role not in ["student", "teacher", "admin"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be student, teacher, or admin"
        )
    
    capabilities = {
        "student": {
            "agents": ["Study & Search Agent"],
            "features": [
                "Document Q&A",
                "Web Search",
                "Python REPL",
                "Manim Animations",
                "Conversation Memory"
            ],
            "restrictions": [
                "Cannot access Grading Agent",
                "Cannot grade submissions",
                "Cannot view grading history"
            ]
        },
        "teacher": {
            "agents": ["Study & Search Agent", "AI Grading Agent"],
            "features": [
                "All student features",
                "Essay Grading",
                "Code Review",
                "MCQ Auto-Grading",
                "Grading History",
                "Custom Rubrics",
                "ML-Powered Grading"
            ],
            "restrictions": []
        },
        "admin": {
            "agents": ["All Agents"],
            "features": [
                "All teacher features",
                "System Administration",
                "ML Features Management",
                "Performance Monitoring"
            ],
            "restrictions": []
        }
    }
    
    return {
        "role": role,
        "capabilities": capabilities[role]
    }

