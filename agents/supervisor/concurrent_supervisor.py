"""
Concurrent Supervisor Agent

Base supervisor that supports concurrent query handling while
long-running tasks execute in the background.
"""

import asyncio
from typing import Optional, Dict, Any, AsyncGenerator

from utils.concurrent_execution import (
    get_task_manager,
    TaskDurationEstimator,
    TaskType
)
from utils.monitoring import get_logger

logger = get_logger(__name__)


class ConcurrentSupervisorMixin:
    """
    Mixin for SupervisorAgent to add concurrent execution capabilities.
    
    This extends the base SupervisorAgent with:
    - Detection of long-running tasks
    - Background task execution
    - Concurrent query routing
    - Task completion notifications
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize concurrent supervisor."""
        super().__init__(*args, **kwargs)
        self.task_manager = get_task_manager()
        self.duration_estimator = TaskDurationEstimator()
        self._concurrent_mode_enabled = True
    
    async def aquery_stream_concurrent(
        self,
        question: str,
        user_role: str = "student",
        thread_id: str = "default",
        user_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        concurrent_question: Optional[str] = None,
        background_task_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streaming query with concurrent execution support.
        
        This enhanced version of aquery_stream:
        1. Detects long-running tasks (like Manim animations)
        2. Executes them in the background
        3. Prompts user for concurrent queries
        4. Handles concurrent queries while background task runs
        5. Notifies when background task completes
        
        Args:
            question: User's primary question
            user_role: User's role
            thread_id: Conversation thread ID
            user_id: User ID
            student_id: Student ID (for grading)
            student_name: Student name (for grading)
            course_id: Course ID
            assignment_id: Assignment ID
            assignment_name: Assignment name
            concurrent_question: Optional concurrent question while task runs
            background_task_id: Optional ID of running background task
            
        Yields:
            Streaming response chunks with special markers for concurrent execution
        """
        # Check if there's an active background task for this thread
        active_tasks = self.task_manager.get_active_tasks(thread_id=thread_id)
        
        if concurrent_question and active_tasks:
            # This is a concurrent query - handle it while main task runs
            logger.info(f"🔀 Handling concurrent query while {len(active_tasks)} task(s) run")
            
            yield "🔀 **Handling your concurrent question...**\n\n"
            
            # Route concurrent query to study agent
            async for chunk in self.streaming_study_agent.aquery_stream(
                question=concurrent_question,
                thread_id=thread_id
            ):
                if chunk != "[DONE]":
                    yield chunk
            
            # Check status of background tasks
            for task_info in active_tasks:
                task_id = task_info["task_id"]
                task_status = self.task_manager.get_task_status(task_id)
                
                if task_status:
                    if task_status["status"] == "completed":
                        yield f"\n\n✅ **Background task completed:** {task_status['task_type'].replace('_', ' ').title()}\n"
                        
                        # Get the result
                        task = self.task_manager.completed_tasks.get(task_id)
                        if task and task.result:
                            yield f"\n{task.result}\n"
                    
                    elif task_status["status"] == "running":
                        progress = int(task_status["progress"] * 100)
                        yield f"\n\n🎬 **Background task still running:** {progress}% complete\n"
            
            yield "[DONE]"
            return
        
        # Otherwise, proceed with normal streaming (possibly creating background tasks)
        try:
            # Normalize role
            normalized_role = user_role.upper()
            if normalized_role in ["PROFESSOR", "INSTRUCTOR"]:
                normalized_role = "TEACHER"
            
            # Detect task type from question
            task_type = self.duration_estimator.detect_task_type(question)
            is_long_running = self.duration_estimator.is_long_running(task_type, question)
            
            if is_long_running and self._concurrent_mode_enabled:
                # Long-running task detected - enable concurrent execution
                logger.info(f"🔄 Long-running {task_type.value} detected, enabling concurrent mode")
                
                yield f"🎬 **Detected long-running task:** {task_type.value.replace('_', ' ').title()}\n\n"
                yield "⏱️ This will take approximately 30-60 seconds. I'll start working on it in the background.\n\n"
            
            # Route to appropriate agent with streaming
            from .state import SupervisorState
            
            # Create initial state
            initial_state: SupervisorState = {
                "question": question,
                "user_role": normalized_role,
                "user_id": user_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "assignment_name": assignment_name,
                "intent": None,
                "agent_choice": None,
                "access_denied": False,
                "routing_confidence": None,
                "agent_result": None,
                "agent_used": None,
                "final_answer": None,
                "routing_time": None,
                "agent_execution_time": None,
                "total_time": None,
                "routing_success": None,
                "routing_alternatives": [],
                "learned_from_history": False,
                "result_quality": None,
                "user_satisfaction_predicted": None,
                "context_used": None,
                "similar_past_queries": [],
                "streaming": True
            }
            
            # Use async methods for non-blocking routing
            state = await self.nodes.aenrich_context(initial_state)
            state = await self.nodes.aclassify_intent(state)
            state = await self.nodes.acheck_access(state)
            
            # Check access
            if state["access_denied"]:
                yield "⛔ Access Denied. Your role does not have permission to use this feature."
                yield "[DONE]"
                return
            
            # Route to agent
            if state["agent_choice"] == "study_agent":
                # Use streaming study agent with concurrent support
                async for chunk in self.streaming_study_agent.aquery_stream(
                    question=question,
                    thread_id=thread_id
                ):
                    yield chunk
            
            elif state["agent_choice"] == "grading_agent":
                # Grading agent (concurrent support can be added later if needed)
                if hasattr(self.grading_agent, "aquery_stream"):
                    async for chunk in self.grading_agent.aquery_stream(
                        question=question,
                        thread_id=thread_id,
                        professor_id=user_id,
                        student_id=student_id,
                        student_name=student_name,
                        course_id=course_id,
                        assignment_id=assignment_id,
                        assignment_name=assignment_name
                    ):
                        yield chunk
                else:
                    yield "Streaming not supported by grading agent."
            
            # Check for background tasks and prompt for concurrent query
            active_tasks = self.task_manager.get_active_tasks(thread_id=thread_id)
            if active_tasks and is_long_running:
                yield "\n\n💡 **While I work on that, what else can I help you with?**\n\n"
                yield "You can ask me another question, and I'll handle it while the animation generates.\n\n"
                yield "Or just say 'wait' to see the result when it's ready.\n\n"
            
            yield "[DONE]"
            
        except Exception as e:
            logger.error(f"Concurrent streaming error: {e}")
            yield f"[ERROR] {str(e)}"
    
    def enable_concurrent_mode(self, enabled: bool = True):
        """Enable or disable concurrent execution mode."""
        self._concurrent_mode_enabled = enabled
        logger.info(f"Concurrent mode: {'enabled' if enabled else 'disabled'}")
    
    def get_background_tasks(self, thread_id: Optional[str] = None) -> list:
        """Get active background tasks."""
        return self.task_manager.get_active_tasks(thread_id=thread_id)
    
    async def wait_for_background_task(self, task_id: str, timeout: float = None) -> Optional[Any]:
        """Wait for a specific background task to complete."""
        return await self.task_manager.wait_for_task(task_id, timeout=timeout)
    
    async def cancel_background_task(self, task_id: str) -> bool:
        """Cancel a background task."""
        return await self.task_manager.cancel_task(task_id)

