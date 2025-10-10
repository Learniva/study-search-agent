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

