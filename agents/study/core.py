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
        """
        Build initial state for study workflow.
        
        Uses shared StateManager.create_study_agent_state() to eliminate duplication.
        """
        existing_messages = existing_messages or []
        max_iterations = ConfigManager.get_max_iterations("study")
        
        return StateManager.create_study_agent_state(
            question=question,
            existing_messages=existing_messages,
            max_iterations=max_iterations,
            **kwargs
        )

