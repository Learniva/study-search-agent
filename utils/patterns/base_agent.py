"""Base agent pattern with shared functionality."""

from typing import Optional, List, Any, Dict
from abc import ABC, abstractmethod
import asyncio
from langgraph.checkpoint.memory import MemorySaver

from utils.core.advanced_cache import MultiTierCache
from utils import initialize_llm
from config import settings


class BaseAgent(ABC):
    """
    Base class for all agents with shared functionality.
    
    Provides:
    - LLM initialization
    - Caching support
    - Memory management
    - Async/sync query handling
    - Conversation history
    """
    
    def __init__(
        self,
        llm_provider: str = "gemini",
        model_name: Optional[str] = None,
        use_case: str = "study"
    ):
        """
        Initialize base agent.
        
        Args:
            llm_provider: LLM provider (gemini, openai, etc.)
            model_name: Optional model name override
            use_case: Use case for temperature settings
        """
        self.llm_provider = llm_provider.lower()
        self.model_name = model_name
        self.llm = initialize_llm(
            model_name=model_name,
            use_case=use_case
        )
        
        # Memory for conversation history
        self.memory = MemorySaver()
        
        # Multi-tier caching
        self.cache = MultiTierCache(
            ttl=settings.cache_ttl,
            enable_redis=settings.redis_url is not None
        )
        
        # Graph will be set by subclass
        self.app = None
    
    @abstractmethod
    def _build_initial_state(self, question: str, **kwargs) -> Dict[str, Any]:
        """Build initial state for graph execution. Must be implemented by subclass."""
        pass
    
    async def aquery(
        self,
        question: str,
        thread_id: str = "default",
        **kwargs
    ) -> str:
        """
        Async query processing with caching.
        
        Args:
            question: User question
            thread_id: Conversation thread ID
            **kwargs: Additional arguments for state
            
        Returns:
            Answer string
        """
        if not self.app:
            raise RuntimeError("Graph not compiled. Call _compile_graph() in __init__")
        
        try:
            # Check cache
            cache_key = f"{thread_id}:{question}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
            
            # Get existing messages
            config = {"configurable": {"thread_id": thread_id}}
            existing_messages = []
            
            try:
                state = self.app.get_state(config)
                if state and state.values:
                    existing_messages = state.values.get("messages", [])
            except Exception:
                pass
            
            # Build initial state
            initial_state = self._build_initial_state(
                question=question,
                existing_messages=existing_messages,
                **kwargs
            )
            
            # Execute graph
            result = self.app.invoke(initial_state, config)
            answer = result.get("final_answer", "No answer generated")
            
            # Cache result
            await self.cache.set(cache_key, answer)
            
            return answer
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def query(
        self,
        question: str,
        thread_id: str = "default",
        **kwargs
    ) -> str:
        """
        Synchronous query (wraps async).
        
        Args:
            question: User question
            thread_id: Conversation thread ID
            **kwargs: Additional arguments
            
        Returns:
            Answer string
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.aquery(question, thread_id, **kwargs)
        )
    
    def get_conversation_history(
        self,
        thread_id: str = "default"
    ) -> List[Any]:
        """
        Get conversation history for a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of messages
        """
        if not self.app:
            return []
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.app.get_state(config)
            return state.values.get("messages", []) if state else []
        except Exception:
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    async def clear_cache(self):
        """Clear agent cache."""
        await self.cache.clear()
    
    async def aquery_stream(
        self,
        question: str,
        thread_id: str = "default",
        **kwargs
    ):
        """
        Streaming version of aquery that yields chunks of the response.
        
        Args:
            question: User question
            thread_id: Conversation thread ID
            **kwargs: Additional arguments for state
            
        Yields:
            Chunks of the answer as they become available
        """
        if not self.app:
            yield "Error: Graph not compiled"
            return
            
        try:
            # Get existing messages
            config = {"configurable": {"thread_id": thread_id}}
            existing_messages = self._get_existing_messages(config)
            
            # Build initial state with streaming flag
            initial_state = self._build_initial_state(
                question=question,
                existing_messages=existing_messages,
                streaming=True,
                **kwargs
            )
            
            # Get LLM with streaming enabled
            streaming_llm = initialize_llm(
                model_name=self.model_name,
                use_case=initial_state.get("use_case", "study"),
                streaming=True
            )
            
            # Create a streaming callback handler
            from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
            
            class StreamingCallbackHandler(StreamingStdOutCallbackHandler):
                """Custom streaming callback handler that yields chunks."""
                
                def __init__(self):
                    super().__init__()
                    self.chunks = []
                    self.queue = asyncio.Queue()
                
                def on_llm_new_token(self, token: str, **kwargs) -> None:
                    """Run on new LLM token. Only available when streaming is enabled."""
                    self.chunks.append(token)
                    self.queue.put_nowait(token)
                
                async def get_chunks(self):
                    """Get chunks as they become available."""
                    while True:
                        chunk = await self.queue.get()
                        yield chunk
                        self.queue.task_done()
                        # If we receive a special end token, break the loop
                        if chunk == "[DONE]":
                            break
            
            # Create the streaming handler
            streaming_handler = StreamingCallbackHandler()
            
            # Create a streaming-enabled LLM for final nodes
            streaming_llm = initialize_llm(
                model_name=self.model_name,
                use_case=initial_state.get("use_case", "study"),
                streaming=True
            )
            
            # Create a modified version of the graph with streaming LLM for final nodes
            # We'll replace the self-reflection and synthesis nodes with streaming versions
            
            # Execute graph up to the final node
            # This is a simplified approach - in a production system, you would 
            # create a more sophisticated streaming graph
            
            # First, run the graph normally but stop before the final nodes
            initial_state["stop_before_final"] = True
            result = self.app.invoke(initial_state, config)
            
            # Now, use streaming LLM for the final answer generation
            if result.get("is_complex_task") and result.get("intermediate_answers"):
                # For complex tasks, use streaming synthesis
                intermediate = result.get("intermediate_answers", [])
                question = result["question"]
                
                steps_context = "\n\n".join([
                    f"Step {r['step']} ({r['tool']}): {r['result']}"
                    for r in intermediate
                ])
                
                synthesis_prompt = f"""Synthesize these step-by-step results:

Question: {question}

Results:
{steps_context}

Provide a complete answer."""
                
                # Stream the synthesis response
                from langchain_core.messages import HumanMessage
                await streaming_llm.agenerate(
                    [[HumanMessage(content=synthesis_prompt)]],
                    callbacks=[streaming_handler]
                )
                
                # Signal end of streaming
                await streaming_handler.queue.put("[DONE]")
                
            else:
                # For simple tasks, stream the final answer directly
                tool_result = result.get("tool_result", "No result")
                
                # If we need to format the answer in a special way
                if result.get("document_qa_failed") and result.get("tried_document_qa"):
                    final_answer = f"Note: Document not found, searched web instead.\n\n{tool_result}"
                else:
                    final_answer = tool_result
                
                # For simple answers, we can just yield the chunks directly
                # This simulates what would happen with a streaming LLM
                for i in range(0, len(final_answer), 20):
                    chunk = final_answer[i:i+20]
                    await streaming_handler.queue.put(chunk)
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                
                # Signal end of streaming
                await streaming_handler.queue.put("[DONE]")
            
            # Yield chunks from the queue
            async for chunk in streaming_handler.get_chunks():
                if chunk != "[DONE]":
                    yield chunk
            
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def _get_existing_messages(self, config: Dict[str, Any]) -> List[Any]:
        """Helper to get existing messages from state."""
        if not self.app:
            return []
        
        try:
            state = self.app.get_state(config)
            if state and state.values:
                return state.values.get("messages", [])
        except Exception:
            pass
        
        return []


