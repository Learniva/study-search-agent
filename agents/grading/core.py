"""Grading Agent - Clean, modular implementation."""

from typing import Optional, Dict, Any, List
import time
from tools.grading import get_all_grading_tools
from utils.patterns import BaseAgent, StateManager
from utils.config_integration import ConfigManager
from .workflow import build_grading_workflow


class GradingAgent(BaseAgent):
    """
    AI Grading Agent with LangGraph workflows.
    
    Features:
    - Essay grading with rubrics
    - Code review
    - MCQ auto-grading
    - Multi-step planning
    - Self-reflection
    - Quality control
    
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
        """Initialize Grading Agent."""
        # Initialize base agent with grading use case
        super().__init__(
            llm_provider=llm_provider,
            model_name=model_name,
            use_case="grading"
        )
        
        # Grading-specific setup
        self.tools = get_all_grading_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Build and compile workflow
        workflow = build_grading_workflow(self.llm, self.tool_map)
        self.app = workflow.compile(checkpointer=self.memory)
    
    def _build_initial_state(
        self,
        question: str,
        existing_messages: List[Any] = None,
        professor_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build initial state for grading workflow.
        
        Uses shared StateManager.create_grading_agent_state() to eliminate duplication
        and ensure consistency across grading workflows.
        """
        existing_messages = existing_messages or []
        max_iterations = ConfigManager.get_max_iterations("grading")
        
        return StateManager.create_grading_agent_state(
            question=question,
            existing_messages=existing_messages,
            max_iterations=max_iterations,
            professor_id=professor_id,
            student_id=student_id,
            student_name=student_name,
            course_id=course_id,
            assignment_id=assignment_id,
            assignment_name=assignment_name,
            **kwargs
        )

