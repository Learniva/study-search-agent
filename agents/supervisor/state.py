"""State definitions for Supervisor Agent."""

from typing import TypedDict, Optional, List, Dict, Any


class SupervisorState(TypedDict):
    """State schema for Supervisor Agent with learning capabilities."""
    
    # Core request data
    question: str
    user_role: str
    user_id: Optional[str]
    student_id: Optional[str]
    student_name: Optional[str]
    course_id: Optional[str]
    assignment_id: Optional[str]
    assignment_name: Optional[str]
    
    # Routing state
    intent: Optional[str]
    agent_choice: Optional[str]
    access_denied: bool
    routing_confidence: Optional[float]
    
    # Results
    agent_result: Optional[str]
    agent_used: Optional[str]
    final_answer: Optional[str]
    
    # Performance tracking
    routing_time: Optional[float]
    agent_execution_time: Optional[float]
    total_time: Optional[float]
    
    # Learning and adaptation
    routing_success: Optional[bool]
    routing_alternatives: List[str]
    learned_from_history: bool
    
    # Quality metrics
    result_quality: Optional[float]
    user_satisfaction_predicted: Optional[float]
    
    # Context enrichment
    context_used: Optional[Dict[str, Any]]
    similar_past_queries: List[Dict[str, Any]]

