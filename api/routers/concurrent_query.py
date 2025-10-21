"""
Concurrent Query Router

Query endpoints with concurrent execution support for long-running tasks.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from api.models import QueryRequest
from api.dependencies import get_supervisor, get_or_create_correlation_id
from utils.monitoring import get_logger
from utils.concurrent_execution import get_task_manager
from utils.api.streaming import format_supervisor_sse_stream, get_sse_headers
from config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Concurrent Query"])


@router.post("/stream/concurrent")
async def query_concurrent_stream(
    request: QueryRequest,
    supervisor=Depends(get_supervisor),
    correlation_id: str = Depends(get_or_create_correlation_id),
    concurrent_question: Optional[str] = Query(None, description="Concurrent question while task runs")
):
    """
    Query with concurrent execution support.
    
    This endpoint enables:
    1. Detection of long-running tasks (e.g., Manim animations)
    2. Background execution of those tasks
    3. Real-time prompts for concurrent queries
    4. Handling of concurrent queries while main task runs
    5. Notifications when background tasks complete
    
    **Usage Pattern:**
    
    **Initial Request:**
    ```
    POST /query/stream/concurrent
    {
        "question": "Create an animation of a sorting algorithm",
        "user_role": "student",
        "thread_id": "user123"
    }
    ```
    
    **Response includes:**
    - Initial acknowledgment that task is long-running
    - Prompt for concurrent query
    - Progress updates
    
    **Concurrent Request (while animation generates):**
    ```
    POST /query/stream/concurrent?concurrent_question=What is bubble sort?
    {
        "question": "Create an animation of a sorting algorithm",
        "user_role": "student",
        "thread_id": "user123"
    }
    ```
    
    **Response includes:**
    - Answer to concurrent question
    - Status update on background task
    - Final result when background task completes
    """
    if not settings.enable_streaming:
        raise HTTPException(
            status_code=503,
            detail="Streaming is not enabled"
        )
    
    logger.info(
        f"Concurrent streaming query",
        user_role=request.user_role,
        thread_id=request.thread_id,
        concurrent=bool(concurrent_question)
    )
    
    # Check if supervisor has concurrent capabilities
    if hasattr(supervisor, 'aquery_stream_concurrent'):
        # Use enhanced concurrent streaming
        supervisor_stream = supervisor.aquery_stream_concurrent(
            question=request.question,
            thread_id=request.thread_id,
            user_role=request.user_role,
            user_id=request.user_id,
            student_id=request.student_id,
            student_name=request.student_name,
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            assignment_name=request.assignment_name,
            concurrent_question=concurrent_question
        )
    else:
        # Fall back to regular streaming
        logger.warning("Supervisor doesn't have concurrent capabilities, falling back to regular streaming")
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
    
    # Format as SSE using shared utility (eliminates duplication with query.py)
    sse_stream = format_supervisor_sse_stream(
        supervisor_stream,
        logger,
        stream_type="concurrent"
    )
    
    return StreamingResponse(
        sse_stream,
        media_type="text/event-stream",
        headers=get_sse_headers()
    )


@router.get("/tasks/active")
async def get_active_tasks(
    thread_id: Optional[str] = Query(None, description="Filter by thread ID")
):
    """
    Get active background tasks.
    
    Returns list of currently running background tasks,
    optionally filtered by thread ID.
    """
    task_manager = get_task_manager()
    active_tasks = task_manager.get_active_tasks(thread_id=thread_id)
    
    return {
        "active_tasks": active_tasks,
        "total_active": len(active_tasks)
    }


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Get status of a specific background task.
    
    Returns detailed status including:
    - Task type
    - Progress percentage
    - Elapsed time
    - Estimated completion time
    """
    task_manager = get_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if not task_status:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return task_status


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    Cancel a running background task.
    
    Attempts to gracefully cancel the task and clean up resources.
    """
    task_manager = get_task_manager()
    success = await task_manager.cancel_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found or already completed"
        )
    
    return {
        "message": f"Task {task_id} cancelled successfully",
        "task_id": task_id,
        "cancelled": True
    }


@router.post("/tasks/{task_id}/wait")
async def wait_for_task(
    task_id: str,
    timeout: Optional[float] = Query(60.0, description="Timeout in seconds")
):
    """
    Wait for a background task to complete.
    
    This endpoint blocks until the task completes or timeout is reached.
    Useful for synchronous clients that want to wait for results.
    """
    task_manager = get_task_manager()
    result = await task_manager.wait_for_task(task_id, timeout=timeout)
    
    if result is None:
        # Check if task exists
        task_status = task_manager.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        elif task_status["status"] == "failed":
            raise HTTPException(
                status_code=500,
                detail=f"Task failed: {task_status['error']}"
            )
        else:
            raise HTTPException(status_code=408, detail="Task timed out")
    
    return {
        "task_id": task_id,
        "result": result,
        "completed": True
    }


@router.get("/tasks/stats")
async def get_task_statistics():
    """
    Get statistics about task execution.
    
    Returns:
    - Total active tasks
    - Total completed tasks
    - Average task duration by type
    - Success/failure rates
    """
    task_manager = get_task_manager()
    
    active_tasks = task_manager.get_active_tasks()
    completed_tasks = list(task_manager.completed_tasks.values())
    
    # Calculate statistics
    total_active = len(active_tasks)
    total_completed = len(completed_tasks)
    
    # Calculate success rate
    successful = sum(1 for t in completed_tasks if t.status.value == "completed")
    failed = sum(1 for t in completed_tasks if t.status.value == "failed")
    
    success_rate = successful / total_completed if total_completed > 0 else 0
    
    # Calculate average durations by type
    durations_by_type = {}
    for task in completed_tasks:
        task_type = task.task_type.value
        if task_type not in durations_by_type:
            durations_by_type[task_type] = []
        if task.get_elapsed_time():
            durations_by_type[task_type].append(task.get_elapsed_time())
    
    avg_durations = {
        task_type: sum(durations) / len(durations)
        for task_type, durations in durations_by_type.items()
        if durations
    }
    
    return {
        "active_tasks": total_active,
        "completed_tasks": total_completed,
        "successful_tasks": successful,
        "failed_tasks": failed,
        "success_rate": success_rate,
        "average_duration_by_type": avg_durations
    }

