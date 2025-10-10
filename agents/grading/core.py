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
        """Build initial state for grading workflow."""
        existing_messages = existing_messages or []
        max_iterations = ConfigManager.get_max_iterations("grading")
        
        # Build comprehensive grading agent state
        state = StateManager.create_base_state(
            question=question,
            existing_messages=existing_messages,
            **kwargs
        )
        
        # Add grading-specific fields
        grading_fields = {
            "professor_id": professor_id,
            "student_id": student_id,
            "student_name": student_name,
            "course_id": course_id,
            "assignment_id": assignment_id,
            "assignment_name": assignment_name,
            "grading_type": None,
            "submission_data": {"question": question},
            "ai_feedback_data": {},
            "processing_start_time": time.time(),
            "grading_confidence": None,
            "consistency_score": None,
            "detected_issues": [],
            "needs_human_review": False,
            "review_reasons": [],
            "rubric_used": None,
            "adapted_rubric": False,
            "criterion_scores": None,
            "feedback_quality": None,
            "suggested_improvements": [],
            "positive_highlights": [],
            "potential_errors": [],
            "auto_corrections": [],
            "compared_to_average": None,
            "percentile_rank": None,
            "is_complex_grading": False,
            "grading_plan": None,
            "current_grading_step": 0,
            "completed_grading_steps": [],
            "intermediate_grading_results": [],
            "max_iterations": max_iterations
        }
        
        return {**state, **grading_fields}

