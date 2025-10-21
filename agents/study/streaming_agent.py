"""
Streaming Study Agent

Streaming-enabled study agent that processes queries with real-time
token-by-token streaming and supports concurrent execution for long-running tasks.
"""

from typing import Optional, Dict, Any, AsyncGenerator
import json

from tools.base import get_all_tools
from utils.patterns import BaseAgent
from utils.config_integration import ConfigManager
from .streaming_workflow import build_streaming_workflow
from .concurrent_streaming_nodes import ConcurrentStreamingStudyNodes
from utils.patterns.streaming import StreamingState
from utils.monitoring import get_logger

logger = get_logger(__name__)


class StreamingStudyAgent(BaseAgent):
    """
    Streaming Study Agent with concurrent execution support.
    
    Features:
    - Real-time token-by-token streaming
    - Concurrent execution for long-running tasks (Manim animations)
    - Background task management
    - Progress indicators
    - All standard study agent capabilities
    """
    
    def __init__(
        self,
        llm_provider: str = "gemini",
        model_name: Optional[str] = None
    ):
        """
        Initialize Streaming Study Agent.
        
        Args:
            llm_provider: LLM provider (gemini, openai, anthropic)
            model_name: Optional model name override
        """
        # Initialize base agent
        super().__init__(
            llm_provider=llm_provider,
            model_name=model_name,
            use_case="study"
        )
        
        # Initialize streaming LLM
        from utils import initialize_llm
        self.streaming_llm = initialize_llm(
            model_name=model_name,
            use_case="study",
            streaming=True
        )
        
        # Study-specific setup
        self.tools = get_all_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Build streaming workflow with concurrent nodes
        self.workflow = build_streaming_workflow(
            self.llm,
            self.streaming_llm,
            self.tool_map
        )
        
        # Use concurrent streaming nodes
        self.nodes = ConcurrentStreamingStudyNodes(
            self.llm,
            self.streaming_llm,
            self.tool_map
        )
    
    def _build_initial_state(self, question: str, existing_messages: list = None, **kwargs) -> Dict[str, Any]:
        """
        Build initial state for streaming workflow (required by BaseAgent).
        
        Uses shared StateManager.create_study_agent_state() to eliminate duplication.
        
        Args:
            question: User's question
            existing_messages: Existing conversation messages
            **kwargs: Additional state parameters
            
        Returns:
            Initial state dictionary
        """
        from utils.patterns import StateManager
        
        existing_messages = existing_messages or []
        max_iterations = ConfigManager.get_max_iterations("study")
        
        return StateManager.create_study_agent_state(
            question=question,
            existing_messages=existing_messages,
            max_iterations=max_iterations,
            **kwargs
        )
    
    async def aquery_stream(
        self,
        question: str,
        thread_id: str = "default",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream query response with concurrent execution support.
        
        Args:
            question: User's question
            thread_id: Conversation thread ID
            **kwargs: Additional parameters
            
        Yields:
            Response chunks as they become available
        """
        try:
            logger.info(f"🎯 Streaming study query: {question[:100]}...")
            
            # Create streaming state
            state = StreamingState({
                "question": question,
                "thread_id": thread_id,
                "tool_used": None,
                "tool_result": None,
                "final_answer": None,
                **kwargs
            })
            
            # Detect complexity and route to appropriate tool
            question_lower = question.lower()
            
            # Determine which tool to use
            if "document" in question_lower or "uploaded" in question_lower or "notes" in question_lower:
                tool_method = self.nodes._execute_document_qa
                logger.info("📚 Routing to Document Q&A")
            
            elif "code" in question_lower or "calculate" in question_lower or "compute" in question_lower or "python" in question_lower:
                tool_method = self.nodes._execute_python_repl
                logger.info("🐍 Routing to Python REPL")
            
            elif any(keyword in question_lower for keyword in ["animate ", "create animation", "generate animation", "show animation", "create video", "generate video", "make video"]):
                tool_method = self.nodes._execute_manim_animation
                logger.info("🎬 Routing to Manim Animation (with concurrent support)")
            
            else:
                tool_method = self.nodes._execute_web_search
                logger.info("🌐 Routing to Web Search")
            
            # Execute tool with streaming
            logger.info("⚙️ Executing tool...")
            result_state = await tool_method(state)
            
            # Stream the results
            async for chunk in result_state.get_stream():
                # Format chunk based on type
                if isinstance(chunk, dict):
                    # Structured update (indicator, progress, etc.)
                    chunk_type = chunk.get("type")
                    
                    if chunk_type == "indicator":
                        indicator = chunk.get("indicator")
                        message = chunk.get("message", "")
                        
                        if indicator == "processing":
                            yield f"⚙️ {message}\n"
                        elif indicator == "complete":
                            yield f"✅ {message}\n"
                        elif indicator == "error":
                            yield f"❌ {message}\n"
                        else:
                            yield f"{message}\n"
                    
                    elif chunk_type == "state_update":
                        # State update (usually not streamed to user)
                        pass
                    
                    else:
                        # Unknown structured chunk - stream as JSON
                        yield json.dumps(chunk) + "\n"
                
                elif isinstance(chunk, str):
                    # Text chunk - stream directly
                    yield chunk
                
                else:
                    # Other type - convert to string
                    yield str(chunk)
            
            # Stream final answer if available
            final_answer = result_state.get("tool_result")
            if final_answer and isinstance(final_answer, str):
                # Check if we already streamed this content
                if not any(final_answer in str(c) for c in result_state._streamed_chunks):
                    yield f"\n\n{final_answer}\n"
            
            logger.info("✅ Streaming study query complete")
            yield "[DONE]"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"[ERROR] {str(e)}"
    
    def get_conversation_history(self, thread_id: str = "default") -> list:
        """
        Get conversation history for a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of conversation messages
        """
        # This would typically use the memory/checkpointer
        # For now, return empty list
        return []

