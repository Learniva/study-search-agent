"""Query Router - Supervisor Agent endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import asyncio
import json

from api.models import QueryRequest, QueryResponse, ConversationHistoryResponse
from api.dependencies import get_supervisor, get_or_create_correlation_id
from utils.monitoring import get_logger, track_query, get_metrics
from utils.errors import handle_errors
from utils.api.streaming import format_supervisor_sse_stream, get_sse_headers
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
    
    # Query supervisor
    try:
        answer = await asyncio.to_thread(
            supervisor.query,
            question=request.question,
            thread_id=request.thread_id,
            user_role=request.user_role,
            user_id=request.user_id,
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
        
        # Extract answer from response dict
        answer_text = answer.get("answer", str(answer)) if isinstance(answer, dict) else str(answer)
        agent_used = answer.get("agent", None) if isinstance(answer, dict) else None
        
        return QueryResponse(
            answer=answer_text,
            thread_id=request.thread_id,
            agent_used=agent_used,
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
    
    NOW WITH RESPONSE CACHING:
    - Cache hit: <100ms (no agent execution)
    - Cache miss: 5-10s (agent execution, then cached)
    - Cache TTL: 10 minutes
    - Expected hit rate: ~30-50% for repeated queries
    
    Returns Server-Sent Events (SSE) stream for real-time responses.
    """
    from utils.api.response_cache import get_response_cache
    
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
    
    # ⚡ OPTIMIZATION 1: Check response cache first (< 100ms for cached)
    response_cache = get_response_cache()
    cached_response = response_cache.get(
        question=request.question,
        user_role=request.user_role,
        thread_id=request.thread_id,
        user_id=request.user_id,
        student_id=request.student_id,
        course_id=request.course_id,
        assignment_id=request.assignment_id
    )
    
    if cached_response:
        logger.info(f"⚡ Response cache HIT - returning cached result (<100ms)")
        
        # Return cached response as SSE stream
        async def cached_stream():
            yield f"data: {json.dumps({'type': 'status', 'data': '⚡ Cached Result'})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'data': cached_response})}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream",
            headers=get_sse_headers()
        )
    
    logger.info(f"📦 Response cache MISS - executing agent...")
    
    # Cache miss - execute agent and cache result
    async def cached_supervisor_stream():
        # Instant response - yield immediately for user feedback
        yield f"data: {json.dumps({'type': 'status', 'data': '🔄 Processing...'})}\n\n"
        
        collected_response = []
        
        # Create supervisor stream generator
        supervisor_stream = supervisor.aquery_stream(
            question=request.question,
            thread_id=request.thread_id,
            user_role=request.user_role,
            user_id=request.user_id,
            student_id=request.student_id,
            student_name=request.student_name,
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            assignment_name=request.assignment_name
        )
        
        # Stream and collect response
        async for chunk in format_supervisor_sse_stream(
            supervisor_stream,
            logger,
            stream_type="regular"
        ):
            # Collect response content for caching
            if "data:" in chunk and "[DONE]" not in chunk:
                try:
                    import json
                    data = json.loads(chunk.replace("data: ", ""))
                    if data.get("type") == "content":
                        collected_response.append(data.get("data", ""))
                except:
                    pass
            
            yield chunk
        
        # Cache the complete response
        if collected_response:
            full_response = "".join(collected_response)
            response_cache.set(
                question=request.question,
                user_role=request.user_role,
                thread_id=request.thread_id,
                response=full_response,
                user_id=request.user_id,
                student_id=request.student_id,
                course_id=request.course_id,
                assignment_id=request.assignment_id
            )
            logger.info(f"✅ Response cached for future requests")
    
    return StreamingResponse(
        cached_supervisor_stream(),
        media_type="text/event-stream",
        headers=get_sse_headers()
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
    valid_roles = ["student", "teacher", "professor", "instructor", "admin"]
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(valid_roles)}"
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
    
    # Map professor and instructor to teacher capabilities
    normalized_role = role
    if role in ["professor", "instructor"]:
        normalized_role = "teacher"
    
    return {
        "role": role,
        "capabilities": capabilities[normalized_role]
    }

