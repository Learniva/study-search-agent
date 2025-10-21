"""
Concurrent Streaming Nodes for Study Agent

Streaming nodes that support parallel execution of long-running tasks
while handling concurrent user queries.

ARCHITECTURE:
- Inherits from StreamingStudyNodes (DRY principle)
- Only overrides _execute_manim_animation to add concurrent execution
- Reuses all other tool execution methods from parent class
"""

import asyncio
from typing import Dict, Any

from .streaming_nodes import StreamingStudyNodes
from utils.patterns.streaming import (
    StreamingState,
    StreamingIndicator
)
from utils.concurrent_execution import (
    get_task_manager,
    TaskType,
    TaskDurationEstimator
)
from utils.monitoring import get_logger

logger = get_logger(__name__)


class ConcurrentStreamingStudyNodes(StreamingStudyNodes):
    """
    Streaming study nodes with concurrent execution support.
    
    Inherits from StreamingStudyNodes and only overrides Manim execution
    to add background processing for long-running animation generation.
    
    All other methods (document_qa, web_search, python_repl) are inherited
    from the parent class - no duplication!
    """
    
    def __init__(self, llm, streaming_llm, tool_map: Dict[str, Any]):
        """
        Initialize concurrent streaming nodes.
        
        Args:
            llm: Regular LLM for non-streaming operations
            streaming_llm: Streaming-enabled LLM
            tool_map: Map of tool names to tool objects
        """
        # Initialize parent class (StreamingStudyNodes)
        super().__init__(llm, streaming_llm, tool_map)
        
        # Add concurrent execution specific attributes
        self.task_manager = get_task_manager()
        self.duration_estimator = TaskDurationEstimator()
    
    async def _execute_manim_animation(self, state: StreamingState) -> StreamingState:
        """
        Execute Manim Animation with concurrent execution support.
        
        OVERRIDES parent class method to add concurrent execution.
        
        This is the primary use case for parallel execution since Manim
        animations take 30-60 seconds to generate.
        """
        tool = self.tool_map.get("render_manim_video")
        if not tool:
            await state.update(
                "tool_result",
                "Manim animation tool not available. Please ensure Manim is installed.",
                stream=True
            )
            return state
        
        question = state.get("question", "")
        thread_id = state.get("thread_id", "default")
        
        # Detect if this is a long-running task
        task_type = TaskType.MANIM_ANIMATION
        is_long_running = self.duration_estimator.is_long_running(task_type, question)
        expected_duration = self.duration_estimator.estimate_duration(task_type, question)
        
        if not is_long_running:
            # Execute directly using parent class implementation for short animations
            logger.info("⚡ Manim task estimated as short, executing directly")
            return await super()._execute_manim_animation(state)
        
        # Long-running task - execute in background with concurrency support
        logger.info(f"🔄 Manim task is long-running ({expected_duration:.1f}s), enabling concurrent execution")
        
        # Signal that we're forking execution
        await state.add_indicator(
            StreamingIndicator.PROCESSING,
            f"🎬 Starting animation generation (estimated: {int(expected_duration)} seconds)..."
        )
        
        # Extract animation topic
        import re
        topic = re.sub(
            r'\b(please|animate|animation|visualize|create|generate|show|me|an?|the|video|of)\b',
            '', question, flags=re.IGNORECASE
        )
        topic = topic.strip() or question
        
        # Create the background task function
        async def manim_task_function(topic: str, tool_func: Any) -> str:
            """Execute Manim animation in background."""
            logger.info(f"🎥 Background Manim generation started for: {topic}")
            result = await asyncio.to_thread(tool_func, topic)
            logger.info(f"✅ Background Manim generation completed")
            return result
        
        # Execute with concurrency support
        async for update in self.task_manager.execute_with_concurrency(
            task_type=TaskType.MANIM_ANIMATION,
            task_function=manim_task_function,
            task_args={"topic": topic, "tool_func": tool.func},
            question=question,
            thread_id=thread_id
        ):
            update_type = update.get("type")
            
            if update_type == "fork":
                # Notify user that task is running in background
                await state.add_indicator(
                    StreamingIndicator.PROCESSING,
                    update["message"]
                )
                # Store task ID for tracking
                await state.update("background_task_id", update["task_id"], stream=False)
                await state.update("background_task_type", update["task_type"], stream=False)
            
            elif update_type == "prompt":
                # Prompt user for concurrent query
                await state.update("concurrent_query_prompt", update["message"], stream=True)
                await state.update("awaiting_concurrent_query", True, stream=False)
                # Signal that user can ask another question
                await state.add_indicator(
                    StreamingIndicator.COMPLETE,
                    "🔀 Ready for your next question while animation generates..."
                )
            
            elif update_type == "progress":
                # Update progress
                progress_pct = int(update["progress"] * 100)
                await state.add_indicator(
                    StreamingIndicator.PROCESSING,
                    f"🎬 Animation progress: {progress_pct}%"
                )
            
            elif update_type == "task_complete":
                # Task completed
                await state.add_indicator(
                    StreamingIndicator.COMPLETE,
                    update["message"]
                )
            
            elif update_type == "result":
                # Final result
                result_content = update["content"]
                
                # Parse JSON result if needed
                try:
                    import json
                    result_data = json.loads(result_content)
                    content = result_data.get("content", "")
                    artifact = result_data.get("artifact")
                    
                    if artifact:
                        final_result = f"{content}\n\n📹 Video saved to: {artifact}"
                        await state.update("video_path", artifact, stream=False)
                    else:
                        final_result = content
                    
                    await state.update("tool_result", final_result, stream=True)
                    
                except json.JSONDecodeError:
                    # Fallback if result is not JSON
                    await state.update("tool_result", result_content, stream=True)
            
            elif update_type == "task_failed":
                # Task failed
                await state.add_indicator(
                    StreamingIndicator.ERROR,
                    update["message"]
                )
                await state.update("tool_result", f"Error: {update['error']}", stream=True)
        
        return state


