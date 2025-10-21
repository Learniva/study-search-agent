"""
Streaming graph architecture for agent workflows.

This module provides a comprehensive implementation of streaming capabilities
throughout the entire agent workflow, enabling token-by-token streaming for
all stages of processing.

Key components:
- StreamingState: State container with streaming capabilities
- StreamingCallbackHandler: Manages streaming callbacks from LLMs
- StreamingStateGraph: Graph implementation supporting streaming operations
"""

import asyncio
import inspect
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable, Union, TypeVar, Generic
from datetime import datetime
from enum import Enum

from langchain.callbacks.base import BaseCallbackHandler
from langgraph.graph import StateGraph, END

# Type variables for generic typing
T = TypeVar('T')
StateType = Dict[str, Any]


class StreamingIndicator(Enum):
    """
    Indicators for different streaming events and workflow stages.
    
    These provide visual feedback to users during agent execution.
    """
    THINKING = "thinking"              # 🤔 Initial analysis
    ANALYZING = "analyzing"            # 🔍 Query analysis
    PLANNING = "planning"              # 📋 Multi-step planning
    SEARCHING = "searching"            # 🔎 Tool search/retrieval
    EXECUTING = "executing"            # ⚙️ Tool execution
    PROCESSING = "processing"          # ⚙️ Processing (alias for executing)
    SYNTHESIZING = "synthesizing"      # ✨ Combining results
    GENERATING = "generating"          # 📝 Final response generation
    COMPLETE = "complete"              # ✅ Task complete
    ERROR = "error"                    # ❌ Error occurred


class StreamingState(Generic[T]):
    """
    State container with streaming capabilities.
    
    Wraps a regular state dictionary and adds streaming functionality,
    allowing updates to be streamed in real-time.
    """
    
    def __init__(self, initial_state: T):
        """
        Initialize streaming state.
        
        Args:
            initial_state: Initial state dictionary
        """
        self.state = initial_state
        self.stream_queue = asyncio.Queue()
        self.is_streaming = True
        self.history: List[Dict[str, Any]] = []
        self._start_time = datetime.now()
    
    async def update(self, key: str, value: Any, stream: bool = True) -> None:
        """
        Update state and optionally stream the update.
        
        Args:
            key: State key to update
            value: New value
            stream: Whether to stream this update
        """
        # Update the state
        if isinstance(self.state, dict):
            self.state[key] = value
        else:
            setattr(self.state, key, value)
        
        # Record in history
        self.history.append({
            "timestamp": datetime.now(),
            "key": key,
            "value_type": type(value).__name__,
            "streamed": stream
        })
        
        # Stream if appropriate
        if stream and self.is_streaming:
            if key == "current_reasoning" or key == "partial_response":
                await self.stream_queue.put({"type": "content", "content": value})
            elif key == "ui_indicator":
                await self.stream_queue.put({"type": "indicator", "indicator": value})
            elif key == "error":
                await self.stream_queue.put({"type": "error", "error": value})
    
    async def add_indicator(self, indicator_type: StreamingIndicator, message: str = None) -> None:
        """
        Add a UI indicator to the stream.
        
        Args:
            indicator_type: Type of indicator
            message: Optional message
        """
        await self.update("ui_indicator", {
            "type": indicator_type.value,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }, stream=True)
    
    async def get_stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Get streaming updates from the state.
        
        Yields:
            Stream chunks as they become available
        """
        while True:
            try:
                chunk = await self.stream_queue.get()
                yield chunk
                self.stream_queue.task_done()
                
                # Check for end marker
                if chunk.get("type") == "end":
                    self.is_streaming = False
                    break
            except asyncio.CancelledError:
                self.is_streaming = False
                break
    
    async def end_stream(self) -> None:
        """End the stream."""
        self.is_streaming = False
        await self.stream_queue.put({"type": "end"})
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the state."""
        if isinstance(self.state, dict):
            return self.state.get(key, default)
        return getattr(self.state, key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get a value from the state using dictionary syntax."""
        if isinstance(self.state, dict):
            return self.state[key]
        return getattr(self.state, key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value in the state using dictionary syntax."""
        if isinstance(self.state, dict):
            self.state[key] = value
        else:
            setattr(self.state, key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the state."""
        if isinstance(self.state, dict):
            return key in self.state
        return hasattr(self.state, key)
    
    def get_state(self) -> T:
        """Get the underlying state."""
        return self.state
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since state creation in seconds."""
        return (datetime.now() - self._start_time).total_seconds()


class StreamingCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for streaming LLM responses.
    
    Captures tokens from the LLM and forwards them to the streaming state.
    """
    
    def __init__(self, streaming_state: StreamingState):
        """
        Initialize streaming callback handler.
        
        Args:
            streaming_state: StreamingState to update with tokens
        """
        super().__init__()
        self.streaming_state = streaming_state
        self.tokens = []
        self.start_time = datetime.now()
        self.token_count = 0
        self.is_streaming = True
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Process new token from LLM.
        
        Args:
            token: The token received from the LLM
            **kwargs: Additional arguments
        """
        if not self.is_streaming:
            return
            
        self.tokens.append(token)
        self.token_count += 1
        
        # Update streaming state with new token
        await self.streaming_state.update("current_reasoning", token, stream=True)
        
        # Also accumulate for final answer
        current = self.streaming_state.get("partial_response", "")
        await self.streaming_state.update("partial_response", current + token, stream=False)
    
    async def on_llm_end(self, response, **kwargs) -> None:
        """Handle LLM completion."""
        # Calculate stats
        elapsed = (datetime.now() - self.start_time).total_seconds()
        tokens_per_second = self.token_count / elapsed if elapsed > 0 else 0
        
        # Update state with completion info
        await self.streaming_state.update("llm_stats", {
            "tokens": self.token_count,
            "elapsed_seconds": elapsed,
            "tokens_per_second": tokens_per_second
        }, stream=False)
    
    async def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Handle LLM error."""
        await self.streaming_state.update("error", str(error), stream=True)
        self.is_streaming = False


class AdaptiveStreamingController:
    """
    Controls streaming rate based on task complexity and progress.
    
    Adjusts the streaming speed dynamically based on various factors
    to provide a natural reading experience.
    """
    
    def __init__(self, initial_rate: float = 1.0):
        """
        Initialize the controller.
        
        Args:
            initial_rate: Base streaming rate multiplier
        """
        self.base_rate = initial_rate
        self.current_rate = initial_rate
        self.complexity_factor = 1.0
        self.progress_factor = 1.0
        self.user_preference_factor = 1.0
    
    async def throttle_stream(self, token: str, complexity: float = 1.0) -> str:
        """
        Throttle streaming based on complexity.
        
        Args:
            token: The token to stream
            complexity: Complexity factor (higher = slower)
            
        Returns:
            The original token after appropriate delay
        """
        # Update complexity factor
        self.complexity_factor = max(0.5, min(2.0, complexity))
        
        # Calculate delay
        delay = 0.01 * self.current_rate * self.complexity_factor * self.progress_factor * self.user_preference_factor
        
        # Apply throttling
        await asyncio.sleep(delay)
        
        return token
    
    def update_progress_factor(self, progress: float) -> None:
        """
        Update progress factor (0.0 to 1.0).
        
        Speed up slightly as we make progress.
        """
        self.progress_factor = max(0.8, min(1.2, 1.0 + (progress - 0.5) * 0.4))
    
    def set_user_preference(self, speed: float) -> None:
        """
        Set user preference for streaming speed.
        
        Args:
            speed: Speed preference (0.5 = slower, 1.0 = normal, 2.0 = faster)
        """
        self.user_preference_factor = max(0.5, min(2.0, speed))


class StreamingCheckpointer:
    """
    Manages checkpoints for streaming graph execution.
    
    Allows saving and resuming execution state.
    """
    
    def __init__(self, storage_backend: Optional[Any] = None):
        """
        Initialize checkpointer.
        
        Args:
            storage_backend: Optional storage backend for checkpoints
        """
        self.storage = storage_backend or {}
        self.checkpoints: Dict[str, Any] = {}
    
    async def save_checkpoint(self, streaming_state: StreamingState, checkpoint_id: str) -> None:
        """
        Save current state as a checkpoint.
        
        Args:
            streaming_state: Current streaming state
            checkpoint_id: Unique identifier for the checkpoint
        """
        # Store state
        self.checkpoints[checkpoint_id] = {
            "state": streaming_state.get_state(),
            "timestamp": datetime.now(),
            "history": streaming_state.history.copy()
        }
        
        # Signal checkpoint in stream
        await streaming_state.add_indicator(
            StreamingIndicator.COMPLETE, 
            f"Checkpoint saved: {checkpoint_id}"
        )
        
        # Store in backend if available
        if hasattr(self.storage, "save_checkpoint"):
            await self.storage.save_checkpoint(checkpoint_id, streaming_state.get_state())
    
    async def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint identifier
            
        Returns:
            Checkpoint state if found, None otherwise
        """
        # Try in-memory first
        if checkpoint_id in self.checkpoints:
            return self.checkpoints[checkpoint_id]["state"]
        
        # Try backend
        if hasattr(self.storage, "load_checkpoint"):
            return await self.storage.load_checkpoint(checkpoint_id)
        
        return None
    
    async def resume_from_checkpoint(self, streaming_state: StreamingState, checkpoint_id: str) -> bool:
        """
        Resume execution from a checkpoint.
        
        Args:
            streaming_state: Current streaming state to update
            checkpoint_id: Checkpoint to resume from
            
        Returns:
            True if successful, False otherwise
        """
        checkpoint_data = await self.load_checkpoint(checkpoint_id)
        
        if not checkpoint_data:
            return False
        
        # Restore state
        if isinstance(streaming_state.state, dict) and isinstance(checkpoint_data, dict):
            streaming_state.state.update(checkpoint_data)
        else:
            streaming_state.state = checkpoint_data
        
        # Signal resumption
        await streaming_state.add_indicator(
            StreamingIndicator.THINKING,
            f"Resumed from checkpoint: {checkpoint_id}"
        )
        
        return True


class StreamingErrorHandler:
    """
    Handles errors in a streaming-friendly way.
    
    Provides error recovery and graceful degradation.
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Initialize error handler.
        
        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries
        self.retry_count: Dict[str, int] = {}
    
    async def handle_error(
        self, 
        streaming_state: StreamingState,
        error: Exception,
        error_id: str,
        recovery_func: Optional[Callable] = None
    ) -> bool:
        """
        Handle error while maintaining the stream.
        
        Args:
            streaming_state: Current streaming state
            error: The exception that occurred
            error_id: Unique identifier for this error type
            recovery_func: Optional recovery function
            
        Returns:
            True if recovered, False otherwise
        """
        # Update retry count
        self.retry_count[error_id] = self.retry_count.get(error_id, 0) + 1
        
        # Stream error notification
        await streaming_state.update(
            "error",
            f"Error: {str(error)}",
            stream=True
        )
        
        # Check if we can retry
        if self.retry_count[error_id] <= self.max_retries and recovery_func:
            # Attempt recovery
            await streaming_state.add_indicator(
                StreamingIndicator.EXECUTING,
                f"Attempting recovery (try {self.retry_count[error_id]}/{self.max_retries})..."
            )
            
            try:
                # Call recovery function
                await recovery_func(streaming_state)
                return True
            except Exception as recovery_error:
                # Recovery failed
                await streaming_state.update(
                    "error", 
                    f"Recovery failed: {str(recovery_error)}", 
                    stream=True
                )
        
        # If unrecoverable or max retries exceeded, provide helpful message
        partial = streaming_state.get("partial_response", "")
        await streaming_state.update(
            "final_answer",
            f"I encountered an error: {str(error)}. Here's what I know so far: {partial}",
            stream=True
        )
        
        return False


class StreamingStateGraph(Generic[T]):
    """
    Graph implementation supporting streaming operations.
    
    A wrapper around LangGraph's StateGraph that adds streaming capabilities,
    allowing nodes to stream their processing in real-time.
    """
    
    def __init__(self, state_type: T):
        """
        Initialize streaming state graph.
        
        Args:
            state_type: Type of state (dict or class)
        """
        self.state_type = state_type
        self.graph = StateGraph(state_type)
        self.streaming_nodes: Dict[str, Callable] = {}
        self.streaming_edges: Dict[str, Dict[str, str]] = {}
        self.node_metadata: Dict[str, Dict[str, Any]] = {}
        self.streaming_handlers: Dict[str, StreamingCallbackHandler] = {}
    
    def add_node(self, name: str, node: Callable, streaming: bool = False, **metadata) -> None:
        """
        Add a node to the graph.
        
        Args:
            name: Node name
            node: Node function
            streaming: Whether this node supports streaming
            **metadata: Additional node metadata
        """
        # Store node metadata
        self.node_metadata[name] = {
            "streaming": streaming,
            "metadata": metadata
        }
        
        # If streaming node, store original function
        if streaming:
            self.streaming_nodes[name] = node
            
            # Extract indicator from metadata
            node_indicator = metadata.get('indicator', StreamingIndicator.EXECUTING)
            
            # Store the indicator for this node
            self.node_metadata[name]['indicator'] = node_indicator
            
            # Just add the regular node - indicators will be managed by ainvoke
            self.graph.add_node(name, node)
        else:
            # Add regular node to graph
            self.graph.add_node(name, node)
    
    def add_edge(self, source: str, target: str, stream_key: Optional[str] = None) -> None:
        """
        Add an edge between nodes.
        
        Args:
            source: Source node name
            target: Target node name
            stream_key: Optional key to stream during transition
        """
        # Store streaming metadata
        if stream_key:
            if source not in self.streaming_edges:
                self.streaming_edges[source] = {}
            self.streaming_edges[source][target] = stream_key
        
        # Add edge to graph
        self.graph.add_edge(source, target)
    
    def add_conditional_edges(
        self,
        source: str,
        condition_fn: Callable,
        edge_map: Dict[str, str],
        stream_keys: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Add conditional edges.
        
        Args:
            source: Source node name
            condition_fn: Function that returns the edge to follow
            edge_map: Mapping from condition result to target node
            stream_keys: Optional mapping from condition result to stream key
        """
        # Store streaming metadata
        if stream_keys:
            if source not in self.streaming_edges:
                self.streaming_edges[source] = {}
            for condition, target in edge_map.items():
                if condition in stream_keys:
                    self.streaming_edges[source][target] = stream_keys[condition]
        
        # Add conditional edges to graph
        self.graph.add_conditional_edges(source, condition_fn, edge_map)
    
    def set_entry_point(self, node_name: str) -> None:
        """
        Set the entry point for the graph.
        
        Args:
            node_name: Name of entry node
        """
        self.graph.set_entry_point(node_name)
    
    def compile(self, checkpointer=None) -> Any:
        """
        Compile the graph.
        
        Args:
            checkpointer: Optional checkpointer for state persistence
            
        Returns:
            Compiled graph
        """
        # Store the compiled graph for ainvoke
        self._compiled_graph = self.graph.compile(checkpointer=checkpointer)
        return self._compiled_graph
    
    async def ainvoke(
        self,
        initial_state: Union[T, StreamingState[T]],
        config: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Invoke the graph asynchronously with streaming.
        
        Args:
            initial_state: Initial state
            config: Optional configuration
            stream: Whether to stream results
            
        Yields:
            Streaming updates from the graph execution
        """
        # Ensure graph is compiled
        if not hasattr(self, '_compiled_graph') or self._compiled_graph is None:
            raise RuntimeError("Graph must be compiled before invoking. Call compile() first.")
        
        # Extract the underlying state dict
        if isinstance(initial_state, StreamingState):
            state_dict = initial_state.get_state()
            streaming_state = initial_state
        else:
            state_dict = initial_state
            streaming_state = StreamingState(initial_state)
        
        # Set up streaming flag in state
        state_dict["is_streaming"] = stream
        
        if stream:
            # Add streaming state to config so nodes can access it
            if config is None:
                config = {}
            config["configurable"] = config.get("configurable", {})
            config["configurable"]["streaming_state"] = streaming_state
            
            # Run graph and stream updates
            async def run_graph():
                """Run the graph and signal completion."""
                try:
                    result = await self._compiled_graph.ainvoke(state_dict, config)
                    # Store final result in streaming state
                    if result and "final_answer" in result:
                        await streaming_state.update("final_answer", result["final_answer"], stream=True)
                    await streaming_state.end_stream()
                except Exception as e:
                    await streaming_state.update("error", str(e), stream=True)
                    await streaming_state.end_stream()
            
            # Start graph execution in background
            graph_task = asyncio.create_task(run_graph())
            
            # Stream chunks as they become available
            try:
                async for chunk in streaming_state.get_stream():
                    yield chunk
            except asyncio.CancelledError:
                graph_task.cancel()
                raise
            finally:
                # Ensure graph completes
                try:
                    await graph_task
                except asyncio.CancelledError:
                    pass
        else:
            # Just run without streaming
            result = await self._compiled_graph.ainvoke(state_dict, config)
            yield {"type": "complete", "result": result}
    
    def invoke(
        self,
        initial_state: Union[T, StreamingState[T]],
        config: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Invoke the graph synchronously (no streaming).
        
        Args:
            initial_state: Initial state
            config: Optional configuration
            
        Returns:
            Final state after graph execution
        """
        # Ensure graph is compiled
        if not hasattr(self, '_compiled_graph') or self._compiled_graph is None:
            raise RuntimeError("Graph must be compiled before invoking. Call compile() first.")
        
        # Extract state if wrapped
        state = initial_state.get_state() if isinstance(initial_state, StreamingState) else initial_state
        
        # Run compiled graph
        result = self._compiled_graph.invoke(state, config)
        
        return result
