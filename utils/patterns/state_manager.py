"""State management utilities for agents."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class StateManager:
    """Utility class for managing agent state."""
    
    @staticmethod
    def create_base_state(
        question: str,
        existing_messages: List[Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create base state with common fields.
        
        Args:
            question: User question
            existing_messages: Existing conversation messages
            **kwargs: Additional state fields
            
        Returns:
            Base state dictionary
        """
        base_state = {
            "messages": existing_messages,
            "question": question,
            "original_question": question,
            "tool_used": None,
            "tool_result": None,
            "tools_used_history": [],
            "final_answer": None,
            "iteration": 0,
        }
        
        base_state.update(kwargs)
        return base_state
    
    @staticmethod
    def add_timestamp(state: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp to state."""
        return {
            **state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def increment_iteration(state: Dict[str, Any]) -> Dict[str, Any]:
        """Increment iteration counter."""
        return {
            **state,
            "iteration": state.get("iteration", 0) + 1
        }
    
    @staticmethod
    def add_to_history(
        state: Dict[str, Any],
        item: Any,
        history_key: str = "tools_used_history"
    ) -> Dict[str, Any]:
        """Add item to history list in state."""
        history = state.get(history_key, [])
        history.append(item)
        return {**state, history_key: history}
    
    @staticmethod
    def check_max_iterations(
        state: Dict[str, Any],
        max_iterations: int = 5
    ) -> bool:
        """Check if max iterations reached."""
        return state.get("iteration", 0) >= max_iterations
    
    @staticmethod
    def merge_state_updates(
        base_state: Dict[str, Any],
        *updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge multiple state updates."""
        result = base_state.copy()
        for update in updates:
            result.update(update)
        return result
    
    @staticmethod
    def extract_result(
        state: Dict[str, Any],
        result_key: str = "final_answer",
        default: str = "No result generated"
    ) -> str:
        """Extract result from state."""
        return state.get(result_key, default)
    
    @staticmethod
    def create_error_state(
        state: Dict[str, Any],
        error: Exception,
        error_key: str = "error_context"
    ) -> Dict[str, Any]:
        """Create state with error information."""
        return {
            **state,
            error_key: {
                "type": type(error).__name__,
                "message": str(error),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
    
    @staticmethod
    def update_metrics(
        state: Dict[str, Any],
        **metrics: Any
    ) -> Dict[str, Any]:
        """Update performance metrics in state."""
        current_metrics = state.get("metrics", {})
        current_metrics.update(metrics)
        return {**state, "metrics": current_metrics}
    
    @staticmethod
    def create_study_agent_state(
        question: str,
        existing_messages: List[Any],
        max_iterations: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create initial state for study agent with all required fields.
        
        This method eliminates code duplication between StudySearchAgent
        and StreamingStudyAgent by providing a shared state builder.
        
        Args:
            question: User's question
            existing_messages: Existing conversation messages
            max_iterations: Maximum allowed iterations
            **kwargs: Additional state fields
            
        Returns:
            Complete study agent state dictionary
        """
        base_state = StateManager.create_base_state(
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
        
        return {**base_state, **study_fields}
    
    @staticmethod
    def create_grading_agent_state(
        question: str,
        existing_messages: List[Any],
        max_iterations: int = 3,
        professor_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create initial state for grading agent with all required fields.
        
        This method provides a centralized way to build grading agent state,
        ensuring consistency and reducing duplication.
        
        Args:
            question: User's question/submission
            existing_messages: Existing conversation messages
            max_iterations: Maximum allowed iterations
            professor_id: Professor/teacher ID
            student_id: Student ID
            student_name: Student name
            course_id: Course ID
            assignment_id: Assignment ID
            assignment_name: Assignment name
            **kwargs: Additional state fields
            
        Returns:
            Complete grading agent state dictionary
        """
        from time import time
        
        base_state = StateManager.create_base_state(
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
            "processing_start_time": time(),
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
        
        return {**base_state, **grading_fields}


