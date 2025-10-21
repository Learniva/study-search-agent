"""
Concurrent Task Execution System

Enables parallel execution of long-running tasks while handling
concurrent user queries. Supports:
- Background task execution
- Task duration detection
- Task completion notifications
- Real-time concurrent query handling
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, Callable, List
from datetime import datetime
from enum import Enum
import json

from utils.monitoring import get_logger

logger = get_logger(__name__)


class TaskType(Enum):
    """Types of tasks that can be executed."""
    MANIM_ANIMATION = "manim_animation"
    WEB_SEARCH = "web_search"
    DOCUMENT_QA = "document_qa"
    PYTHON_REPL = "python_repl"
    GRADING = "grading"
    UNKNOWN = "unknown"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTask:
    """
    Represents a background task with metadata and execution tracking.
    """
    
    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        task_function: Callable,
        task_args: Dict[str, Any],
        expected_duration: float = None,
        thread_id: str = None
    ):
        """
        Initialize background task.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task
            task_function: Async function to execute
            task_args: Arguments for the task function
            expected_duration: Expected duration in seconds
            thread_id: Conversation thread ID
        """
        self.task_id = task_id
        self.task_type = task_type
        self.task_function = task_function
        self.task_args = task_args
        self.expected_duration = expected_duration
        self.thread_id = thread_id
        
        # Execution state
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None
        self.progress = 0.0
        self.progress_message = ""
        
        # Asyncio task
        self._task: Optional[asyncio.Task] = None
    
    async def execute(self) -> Any:
        """Execute the task and track completion."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        
        try:
            logger.info(f"🚀 Starting background task: {self.task_id} ({self.task_type.value})")
            
            # Execute the task function
            self.result = await self.task_function(**self.task_args)
            
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()
            self.progress = 1.0
            
            logger.info(f"✅ Background task completed: {self.task_id}")
            
            return self.result
            
        except asyncio.CancelledError:
            self.status = TaskStatus.CANCELLED
            logger.warning(f"🛑 Background task cancelled: {self.task_id}")
            raise
            
        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.now()
            
            logger.error(f"❌ Background task failed: {self.task_id} - {str(e)}")
            raise
    
    def update_progress(self, progress: float, message: str = ""):
        """Update task progress."""
        self.progress = min(1.0, max(0.0, progress))
        self.progress_message = message
    
    def get_elapsed_time(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.get_elapsed_time(),
            "expected_duration": self.expected_duration,
            "thread_id": self.thread_id,
            "result_available": self.result is not None,
            "error": self.error
        }


class TaskDurationEstimator:
    """
    Estimates task duration based on task type and historical data.
    """
    
    # Default expected durations in seconds
    DEFAULT_DURATIONS = {
        TaskType.MANIM_ANIMATION: 45.0,  # Manim typically takes 30-60 seconds
        TaskType.WEB_SEARCH: 3.0,
        TaskType.DOCUMENT_QA: 2.0,
        TaskType.PYTHON_REPL: 1.0,
        TaskType.GRADING: 10.0,
        TaskType.UNKNOWN: 5.0
    }
    
    # Threshold for considering a task "long-running"
    LONG_RUNNING_THRESHOLD = 15.0  # seconds
    
    def __init__(self):
        """Initialize estimator."""
        self.historical_durations: Dict[TaskType, List[float]] = {
            task_type: [] for task_type in TaskType
        }
    
    def is_long_running(self, task_type: TaskType, question: str = "") -> bool:
        """
        Determine if a task is long-running.
        
        Args:
            task_type: Type of task
            question: User question (for context)
            
        Returns:
            True if task is expected to be long-running
        """
        expected = self.estimate_duration(task_type, question)
        return expected >= self.LONG_RUNNING_THRESHOLD
    
    def estimate_duration(self, task_type: TaskType, question: str = "") -> float:
        """
        Estimate task duration in seconds.
        
        Args:
            task_type: Type of task
            question: User question (for context)
            
        Returns:
            Estimated duration in seconds
        """
        # Use historical average if available
        if self.historical_durations[task_type]:
            avg_duration = sum(self.historical_durations[task_type]) / len(self.historical_durations[task_type])
            return avg_duration
        
        # Fall back to default
        return self.DEFAULT_DURATIONS.get(task_type, self.DEFAULT_DURATIONS[TaskType.UNKNOWN])
    
    def record_duration(self, task_type: TaskType, duration: float):
        """
        Record actual task duration for learning.
        
        Args:
            task_type: Type of task
            duration: Actual duration in seconds
        """
        self.historical_durations[task_type].append(duration)
        
        # Keep only last 100 entries per type
        if len(self.historical_durations[task_type]) > 100:
            self.historical_durations[task_type] = self.historical_durations[task_type][-100:]
    
    @staticmethod
    def detect_task_type(question: str, tool_name: str = None) -> TaskType:
        """
        Detect task type from question and tool name.
        
        Args:
            question: User question
            tool_name: Tool being used
            
        Returns:
            Detected task type
        """
        question_lower = question.lower()
        
        # Manim animation detection
        if tool_name and "manim" in tool_name.lower():
            return TaskType.MANIM_ANIMATION
        if any(keyword in question_lower for keyword in ["animate", "animation", "visualize", "video"]):
            return TaskType.MANIM_ANIMATION
        
        # Web search detection
        if tool_name and "web" in tool_name.lower():
            return TaskType.WEB_SEARCH
        if any(keyword in question_lower for keyword in ["search web", "google", "internet"]):
            return TaskType.WEB_SEARCH
        
        # Document QA detection
        if tool_name and "document" in tool_name.lower():
            return TaskType.DOCUMENT_QA
        if any(keyword in question_lower for keyword in ["document", "notes", "my files"]):
            return TaskType.DOCUMENT_QA
        
        # Python REPL detection
        if tool_name and "python" in tool_name.lower() or tool_name and "repl" in tool_name.lower():
            return TaskType.PYTHON_REPL
        if any(keyword in question_lower for keyword in ["calculate", "execute", "run code"]):
            return TaskType.PYTHON_REPL
        
        # Grading detection
        if tool_name and "grad" in tool_name.lower():
            return TaskType.GRADING
        if any(keyword in question_lower for keyword in ["grade", "feedback", "rubric"]):
            return TaskType.GRADING
        
        return TaskType.UNKNOWN


class ConcurrentTaskManager:
    """
    Manages concurrent execution of tasks and queries.
    
    Handles:
    - Background task execution
    - Concurrent query processing
    - Task completion notifications
    - Task status tracking
    """
    
    def __init__(self):
        """Initialize task manager."""
        self.active_tasks: Dict[str, BackgroundTask] = {}
        self.completed_tasks: Dict[str, BackgroundTask] = {}
        self.task_queues: Dict[str, asyncio.Queue] = {}  # Per-thread queues
        self.estimator = TaskDurationEstimator()
        
        # Notification subscribers
        self.notification_subscribers: Dict[str, List[Callable]] = {}
    
    async def execute_with_concurrency(
        self,
        task_type: TaskType,
        task_function: Callable,
        task_args: Dict[str, Any],
        question: str,
        thread_id: str,
        stream_callback: Optional[Callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a task with concurrency support.
        
        If task is long-running, it will be executed in the background
        and the user will be prompted for a concurrent query.
        
        Args:
            task_type: Type of task
            task_function: Async function to execute
            task_args: Arguments for the task
            question: Original user question
            thread_id: Conversation thread ID
            stream_callback: Optional callback for streaming updates
            
        Yields:
            Streaming updates including prompts and results
        """
        # Check if task is long-running
        is_long = self.estimator.is_long_running(task_type, question)
        expected_duration = self.estimator.estimate_duration(task_type, question)
        
        if not is_long:
            # Execute normally without background processing
            logger.info(f"⚡ Task is short-running ({expected_duration:.1f}s), executing directly")
            
            try:
                start_time = datetime.now()
                result = await task_function(**task_args)
                duration = (datetime.now() - start_time).total_seconds()
                
                # Record duration for learning
                self.estimator.record_duration(task_type, duration)
                
                yield {
                    "type": "result",
                    "content": result,
                    "task_type": task_type.value,
                    "duration": duration
                }
                
            except Exception as e:
                yield {
                    "type": "error",
                    "error": str(e),
                    "task_type": task_type.value
                }
        
        else:
            # Execute in background
            logger.info(f"🔄 Task is long-running ({expected_duration:.1f}s), forking execution")
            
            # Create background task
            task_id = str(uuid.uuid4())
            background_task = BackgroundTask(
                task_id=task_id,
                task_type=task_type,
                task_function=task_function,
                task_args=task_args,
                expected_duration=expected_duration,
                thread_id=thread_id
            )
            
            self.active_tasks[task_id] = background_task
            
            # Start task in background
            background_task._task = asyncio.create_task(background_task.execute())
            
            # Yield immediate prompt to user
            yield {
                "type": "fork",
                "message": f"🎬 I'm generating the {task_type.value.replace('_', ' ')} in the background (this will take about {int(expected_duration)} seconds).",
                "task_id": task_id,
                "task_type": task_type.value,
                "expected_duration": expected_duration
            }
            
            yield {
                "type": "prompt",
                "message": "\n\n💡 **While I work on that, what else can I help you with?**\n\nYou can:\n- Ask me another question\n- Request a different task\n- Or just say 'wait' to see the animation when it's ready",
                "awaiting_input": True
            }
            
            # Monitor task progress and yield updates
            last_progress_update = 0.0
            while background_task.status == TaskStatus.RUNNING:
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
                # Yield progress updates
                if background_task.progress > last_progress_update + 0.1:
                    yield {
                        "type": "progress",
                        "task_id": task_id,
                        "progress": background_task.progress,
                        "message": background_task.progress_message or f"Progress: {int(background_task.progress * 100)}%"
                    }
                    last_progress_update = background_task.progress
            
            # Task completed - yield result
            if background_task.status == TaskStatus.COMPLETED:
                duration = background_task.get_elapsed_time()
                self.estimator.record_duration(task_type, duration)
                
                yield {
                    "type": "task_complete",
                    "task_id": task_id,
                    "message": f"✅ **{task_type.value.replace('_', ' ').title()} is ready!**",
                    "duration": duration
                }
                
                yield {
                    "type": "result",
                    "content": background_task.result,
                    "task_type": task_type.value,
                    "duration": duration
                }
                
                # Move to completed tasks
                self.completed_tasks[task_id] = background_task
                del self.active_tasks[task_id]
                
            elif background_task.status == TaskStatus.FAILED:
                yield {
                    "type": "task_failed",
                    "task_id": task_id,
                    "error": background_task.error,
                    "message": f"❌ {task_type.value.replace('_', ' ').title()} failed: {background_task.error}"
                }
                
                # Move to completed tasks
                self.completed_tasks[task_id] = background_task
                del self.active_tasks[task_id]
    
    async def handle_concurrent_query(
        self,
        question: str,
        thread_id: str,
        agent: Any,
        background_task_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Handle a concurrent query while a background task is running.
        
        Args:
            question: User's concurrent question
            thread_id: Conversation thread ID
            agent: Agent to handle the query
            background_task_id: Optional ID of the background task
            
        Yields:
            Streaming response chunks
        """
        logger.info(f"🔀 Handling concurrent query while task {background_task_id} runs")
        
        # Stream the agent response
        if hasattr(agent, 'aquery_stream'):
            async for chunk in agent.aquery_stream(question=question, thread_id=thread_id):
                yield chunk
        else:
            # Fallback to non-streaming
            result = await asyncio.to_thread(agent.query, question=question, thread_id=thread_id)
            yield str(result.get("answer", result))
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task."""
        task = self.active_tasks.get(task_id) or self.completed_tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def get_active_tasks(self, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active tasks, optionally filtered by thread."""
        tasks = self.active_tasks.values()
        if thread_id:
            tasks = [t for t in tasks if t.thread_id == thread_id]
        return [t.to_dict() for t in tasks]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a background task."""
        task = self.active_tasks.get(task_id)
        if task and task._task:
            task._task.cancel()
            task.status = TaskStatus.CANCELLED
            logger.info(f"🛑 Cancelled task: {task_id}")
            return True
        return False
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Wait for a background task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Optional timeout in seconds
            
        Returns:
            Task result if completed, None if timeout/not found
        """
        task = self.active_tasks.get(task_id)
        if not task or not task._task:
            # Check if already completed
            completed = self.completed_tasks.get(task_id)
            if completed:
                return completed.result
            return None
        
        try:
            await asyncio.wait_for(task._task, timeout=timeout)
            return task.result
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout waiting for task: {task_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Error waiting for task {task_id}: {e}")
            return None


# Global task manager instance
_task_manager: Optional[ConcurrentTaskManager] = None


def get_task_manager() -> ConcurrentTaskManager:
    """Get or create the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = ConcurrentTaskManager()
    return _task_manager


def reset_task_manager():
    """Reset the task manager (for testing)."""
    global _task_manager
    _task_manager = None

