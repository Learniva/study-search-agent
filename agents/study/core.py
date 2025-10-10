"""Study Agent - Clean, modular implementation."""

from typing import Optional, Dict, Any, List
from tools.base import get_all_tools
from utils.patterns import BaseAgent, StateManager
from utils.config_integration import ConfigManager
from .workflow import build_study_workflow


class StudySearchAgent(BaseAgent):
    """
    Study and Search Agent with LangGraph workflows.
    
    Features:
    - Intelligent tool routing
    - Multi-step task planning
    - Self-reflection and quality checks
    - Conversation memory
    - Result caching
    
    Inherits from BaseAgent for shared functionality:
    - LLM initialization
    - Caching
    - Memory management
    - Async/sync query handling
    """
    
    def __init__(
        self,
        llm_provider: str = "gemini",
        model_name: Optional[str] = None
    ):
        """Initialize Study Agent."""
        # Initialize base agent
        super().__init__(
            llm_provider=llm_provider,
            model_name=model_name,
            use_case="study"
        )
        
        # Study-specific setup
        self.tools = get_all_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Build and compile workflow
        workflow = build_study_workflow(self.llm, self.tool_map)
        self.app = workflow.compile(checkpointer=self.memory)
    
    def _build_initial_state(
        self,
        question: str,
        existing_messages: List[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Build initial state for study workflow."""
        existing_messages = existing_messages or []
        max_iterations = ConfigManager.get_max_iterations("study")
        
        # Build comprehensive study agent state
        state = StateManager.create_base_state(
            question=question,
            existing_messages=existing_messages,
            **kwargs
        )
        
        # Add study-specific fields
        study_fields = {
            "tried_document_qa": False,
            "document_qa_failed": False,
            "is_complex_task": False,
            "task_plan": None,
            "current_step": 0,
            "completed_steps": [],
            "intermediate_answers": [],
            "response_confidence": None,
            "quality_issues": [],
            "needs_clarification": False,
            "clarification_question": None,
            "fallback_attempts": 0,
            "max_iterations": max_iterations,
            "suggested_followups": [],
            "alternative_approaches": [],
            "error_context": None,
            "needs_retry": False
        }
        
        return {**state, **study_fields}

