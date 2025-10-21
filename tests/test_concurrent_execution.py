"""
Tests for Concurrent Execution System
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from utils.concurrent_execution import (
    TaskType,
    TaskStatus,
    BackgroundTask,
    TaskDurationEstimator,
    ConcurrentTaskManager,
    get_task_manager,
    reset_task_manager
)


class TestTaskDurationEstimator:
    """Test task duration estimation."""
    
    def test_detect_manim_task_type(self):
        """Test Manim animation detection."""
        estimator = TaskDurationEstimator()
        
        # Should detect Manim from question
        task_type = estimator.detect_task_type("Create an animation of sorting")
        assert task_type == TaskType.MANIM_ANIMATION
        
        task_type = estimator.detect_task_type("Visualize neural network")
        assert task_type == TaskType.MANIM_ANIMATION
        
        # Should detect from tool name
        task_type = estimator.detect_task_type("test", tool_name="render_manim_video")
        assert task_type == TaskType.MANIM_ANIMATION
    
    def test_detect_web_search_task_type(self):
        """Test web search detection."""
        estimator = TaskDurationEstimator()
        
        task_type = estimator.detect_task_type("Search web for Python tutorials")
        assert task_type == TaskType.WEB_SEARCH
        
        task_type = estimator.detect_task_type("test", tool_name="Web_Search")
        assert task_type == TaskType.WEB_SEARCH
    
    def test_is_long_running_manim(self):
        """Test long-running detection for Manim."""
        estimator = TaskDurationEstimator()
        
        # Manim should be detected as long-running
        assert estimator.is_long_running(TaskType.MANIM_ANIMATION, "animate sorting")
    
    def test_is_not_long_running_web_search(self):
        """Test that web search is not long-running."""
        estimator = TaskDurationEstimator()
        
        # Web search should not be long-running
        assert not estimator.is_long_running(TaskType.WEB_SEARCH, "search google")
    
    def test_estimate_duration_defaults(self):
        """Test default duration estimates."""
        estimator = TaskDurationEstimator()
        
        # Check default durations
        assert estimator.estimate_duration(TaskType.MANIM_ANIMATION) == 45.0
        assert estimator.estimate_duration(TaskType.WEB_SEARCH) == 3.0
        assert estimator.estimate_duration(TaskType.DOCUMENT_QA) == 2.0
        assert estimator.estimate_duration(TaskType.PYTHON_REPL) == 1.0
    
    def test_record_and_learn_duration(self):
        """Test that estimator learns from historical data."""
        estimator = TaskDurationEstimator()
        
        # Record some durations
        estimator.record_duration(TaskType.MANIM_ANIMATION, 30.0)
        estimator.record_duration(TaskType.MANIM_ANIMATION, 40.0)
        estimator.record_duration(TaskType.MANIM_ANIMATION, 50.0)
        
        # Estimate should now use average
        estimate = estimator.estimate_duration(TaskType.MANIM_ANIMATION)
        assert estimate == 40.0  # Average of 30, 40, 50


class TestBackgroundTask:
    """Test BackgroundTask class."""
    
    @pytest.mark.asyncio
    async def test_task_execution_success(self):
        """Test successful task execution."""
        # Create a simple async task
        async def sample_task(value: int) -> int:
            await asyncio.sleep(0.1)
            return value * 2
        
        # Create background task
        task = BackgroundTask(
            task_id="test-123",
            task_type=TaskType.PYTHON_REPL,
            task_function=sample_task,
            task_args={"value": 5},
            thread_id="test-thread"
        )
        
        # Execute
        result = await task.execute()
        
        # Verify
        assert result == 10
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 10
        assert task.error is None
    
    @pytest.mark.asyncio
    async def test_task_execution_failure(self):
        """Test task execution with error."""
        # Create a failing task
        async def failing_task():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        task = BackgroundTask(
            task_id="test-456",
            task_type=TaskType.MANIM_ANIMATION,
            task_function=failing_task,
            task_args={},
            thread_id="test-thread"
        )
        
        # Execute (should raise)
        with pytest.raises(ValueError):
            await task.execute()
        
        # Verify error state
        assert task.status == TaskStatus.FAILED
        assert task.error == "Test error"
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test task cancellation."""
        # Create a long-running task
        async def long_task():
            await asyncio.sleep(10.0)
            return "should not complete"
        
        task = BackgroundTask(
            task_id="test-789",
            task_type=TaskType.MANIM_ANIMATION,
            task_function=long_task,
            task_args={},
            thread_id="test-thread"
        )
        
        # Start task
        task._task = asyncio.create_task(task.execute())
        
        # Cancel immediately
        task._task.cancel()
        
        # Wait and verify cancellation
        with pytest.raises(asyncio.CancelledError):
            await task._task
        
        assert task.status == TaskStatus.CANCELLED
    
    def test_task_progress_update(self):
        """Test progress tracking."""
        task = BackgroundTask(
            task_id="test-progress",
            task_type=TaskType.MANIM_ANIMATION,
            task_function=Mock(),
            task_args={},
            thread_id="test-thread"
        )
        
        # Update progress
        task.update_progress(0.5, "Half complete")
        
        assert task.progress == 0.5
        assert task.progress_message == "Half complete"
        
        # Test clamping
        task.update_progress(1.5, "Over 100%")
        assert task.progress == 1.0
        
        task.update_progress(-0.5, "Negative")
        assert task.progress == 0.0
    
    def test_task_to_dict(self):
        """Test task serialization."""
        task = BackgroundTask(
            task_id="test-dict",
            task_type=TaskType.WEB_SEARCH,
            task_function=Mock(),
            task_args={},
            expected_duration=5.0,
            thread_id="test-thread"
        )
        
        task.status = TaskStatus.RUNNING
        task.progress = 0.75
        
        # Convert to dict
        task_dict = task.to_dict()
        
        # Verify structure
        assert task_dict["task_id"] == "test-dict"
        assert task_dict["task_type"] == "web_search"
        assert task_dict["status"] == "running"
        assert task_dict["progress"] == 0.75
        assert task_dict["expected_duration"] == 5.0
        assert task_dict["thread_id"] == "test-thread"


class TestConcurrentTaskManager:
    """Test ConcurrentTaskManager class."""
    
    def setup_method(self):
        """Reset task manager before each test."""
        reset_task_manager()
    
    @pytest.mark.asyncio
    async def test_short_task_direct_execution(self):
        """Test that short tasks execute directly."""
        manager = get_task_manager()
        
        # Create a short task
        async def short_task(value: int) -> int:
            await asyncio.sleep(0.05)
            return value * 3
        
        # Execute with concurrency (should execute directly)
        results = []
        async for update in manager.execute_with_concurrency(
            task_type=TaskType.WEB_SEARCH,  # Short task
            task_function=short_task,
            task_args={"value": 7},
            question="test",
            thread_id="test-thread"
        ):
            results.append(update)
        
        # Should only have result (no fork/prompt)
        assert len(results) == 1
        assert results[0]["type"] == "result"
        assert results[0]["content"] == 21
    
    @pytest.mark.asyncio
    async def test_long_task_background_execution(self):
        """Test that long tasks execute in background."""
        manager = get_task_manager()
        
        # Create a long task
        async def long_task() -> str:
            await asyncio.sleep(0.2)
            return "completed"
        
        # Execute with concurrency (should fork)
        results = []
        async for update in manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,  # Long task
            task_function=long_task,
            task_args={},
            question="animate test",
            thread_id="test-thread"
        ):
            results.append(update)
        
        # Should have fork, prompt, and result
        update_types = [r["type"] for r in results]
        assert "fork" in update_types
        assert "prompt" in update_types
        assert "task_complete" in update_types
        assert "result" in update_types
        
        # Verify final result
        result_updates = [r for r in results if r["type"] == "result"]
        assert len(result_updates) == 1
        assert result_updates[0]["content"] == "completed"
    
    @pytest.mark.asyncio
    async def test_get_active_tasks(self):
        """Test getting active tasks."""
        manager = get_task_manager()
        
        # Create a long-running task
        async def slow_task():
            await asyncio.sleep(1.0)
            return "done"
        
        # Start task
        task_gen = manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,
            task_function=slow_task,
            task_args={},
            question="test",
            thread_id="test-thread"
        )
        
        # Get first update (fork)
        await task_gen.__anext__()
        
        # Check active tasks
        active = manager.get_active_tasks(thread_id="test-thread")
        assert len(active) == 1
        assert active[0]["thread_id"] == "test-thread"
        assert active[0]["status"] == "running"
    
    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test task cancellation."""
        manager = get_task_manager()
        
        # Create a long task
        async def long_task():
            await asyncio.sleep(5.0)
            return "should not complete"
        
        # Start task
        task_gen = manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,
            task_function=long_task,
            task_args={},
            question="test",
            thread_id="test-thread"
        )
        
        # Get fork update
        fork_update = await task_gen.__anext__()
        task_id = fork_update["task_id"]
        
        # Cancel task
        success = await manager.cancel_task(task_id)
        assert success is True
        
        # Verify task is cancelled
        task_status = manager.get_task_status(task_id)
        assert task_status["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_wait_for_task(self):
        """Test waiting for task completion."""
        manager = get_task_manager()
        
        # Create a task
        async def timed_task():
            await asyncio.sleep(0.2)
            return "finished"
        
        # Start task
        task_gen = manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,
            task_function=timed_task,
            task_args={},
            question="test",
            thread_id="test-thread"
        )
        
        # Get fork update
        fork_update = await task_gen.__anext__()
        task_id = fork_update["task_id"]
        
        # Wait for completion
        result = await manager.wait_for_task(task_id, timeout=1.0)
        assert result == "finished"
    
    @pytest.mark.asyncio
    async def test_wait_for_task_timeout(self):
        """Test waiting for task with timeout."""
        manager = get_task_manager()
        
        # Create a very long task
        async def very_long_task():
            await asyncio.sleep(10.0)
            return "too long"
        
        # Start task
        task_gen = manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,
            task_function=very_long_task,
            task_args={},
            question="test",
            thread_id="test-thread"
        )
        
        # Get fork update
        fork_update = await task_gen.__anext__()
        task_id = fork_update["task_id"]
        
        # Wait with short timeout
        result = await manager.wait_for_task(task_id, timeout=0.1)
        assert result is None  # Should timeout


@pytest.mark.asyncio
async def test_concurrent_query_handling():
    """Test handling concurrent queries while task runs."""
    manager = get_task_manager()
    
    # Simulate main task
    async def main_task():
        await asyncio.sleep(0.5)
        return "main result"
    
    # Start main task
    task_gen = manager.execute_with_concurrency(
        task_type=TaskType.MANIM_ANIMATION,
        task_function=main_task,
        task_args={},
        question="main question",
        thread_id="test-thread"
    )
    
    # Get fork update
    fork_update = await task_gen.__anext__()
    task_id = fork_update["task_id"]
    
    # Simulate concurrent query (using mock agent)
    mock_agent = Mock()
    mock_agent.aquery_stream = AsyncMock(return_value=iter(["concurrent answer"]))
    
    # Handle concurrent query
    concurrent_results = []
    async for chunk in manager.handle_concurrent_query(
        question="concurrent question",
        thread_id="test-thread",
        agent=mock_agent,
        background_task_id=task_id
    ):
        concurrent_results.append(chunk)
    
    # Verify concurrent query was handled
    assert len(concurrent_results) > 0


@pytest.mark.asyncio
async def test_task_duration_learning():
    """Test that estimator learns from actual durations."""
    manager = get_task_manager()
    
    # Execute tasks and record durations
    for i in range(3):
        async def quick_task():
            await asyncio.sleep(0.05)
            return "done"
        
        async for update in manager.execute_with_concurrency(
            task_type=TaskType.WEB_SEARCH,
            task_function=quick_task,
            task_args={},
            question="test",
            thread_id="test-thread"
        ):
            pass
    
    # Check that estimator has recorded the durations
    assert len(manager.estimator.historical_durations[TaskType.WEB_SEARCH]) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_concurrent_workflow():
    """
    Integration test for full concurrent execution workflow.
    
    Simulates:
    1. User requests Manim animation (long task)
    2. System detects and forks execution
    3. User asks concurrent question
    4. System handles concurrent query
    5. Main task completes
    6. Both results delivered
    """
    manager = get_task_manager()
    
    # Step 1: Start long task (Manim animation)
    async def animation_task():
        await asyncio.sleep(0.5)
        return "Animation: bubble_sort.mp4"
    
    main_updates = []
    task_gen = manager.execute_with_concurrency(
        task_type=TaskType.MANIM_ANIMATION,
        task_function=animation_task,
        task_args={},
        question="Create animation of bubble sort",
        thread_id="user123"
    )
    
    # Step 2: Get fork and prompt
    fork_update = await task_gen.__anext__()
    assert fork_update["type"] == "fork"
    task_id = fork_update["task_id"]
    
    prompt_update = await task_gen.__anext__()
    assert prompt_update["type"] == "prompt"
    assert "what else can I help" in prompt_update["message"].lower()
    
    # Step 3: Handle concurrent query
    mock_agent = Mock()
    
    async def mock_stream(question, thread_id):
        yield "Bubble sort is a simple sorting algorithm..."
        yield "[DONE]"
    
    mock_agent.aquery_stream = mock_stream
    
    concurrent_answer = []
    async for chunk in manager.handle_concurrent_query(
        question="What is bubble sort?",
        thread_id="user123",
        agent=mock_agent,
        background_task_id=task_id
    ):
        if chunk != "[DONE]":
            concurrent_answer.append(chunk)
    
    assert len(concurrent_answer) > 0
    
    # Step 4: Wait for main task completion
    remaining_updates = []
    async for update in task_gen:
        remaining_updates.append(update)
    
    # Verify completion
    assert any(u["type"] == "task_complete" for u in remaining_updates)
    assert any(u["type"] == "result" for u in remaining_updates)
    
    # Get final result
    result_update = next(u for u in remaining_updates if u["type"] == "result")
    assert "bubble_sort.mp4" in result_update["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

