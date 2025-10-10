"""State management utilities for agents."""

from typing import Dict, Any, List, Optional
from datetime import datetime


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
            "timestamp": datetime.utcnow().isoformat()
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
                "timestamp": datetime.utcnow().isoformat()
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

