"""State definitions for Grading Agent."""

from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langgraph.graph.message import add_messages


class GradingAgentState(TypedDict):
    """State schema for Grading Agent with agentic capabilities."""
    
    # Core messages and question
    messages: Annotated[List[Any], add_messages]
    question: str
    original_question: Optional[str]
    
    # Tool execution tracking
    tool_used: Optional[str]
    tool_result: Optional[str]
    tools_used_history: List[str]
    final_answer: Optional[str]
    
    # Database context
    professor_id: Optional[str]
    student_id: Optional[str]
    student_name: Optional[str]
    course_id: Optional[str]
    assignment_id: Optional[str]
    assignment_name: Optional[str]
    
    # Grading metadata
    grading_type: Optional[str]
    submission_data: Optional[Dict[str, Any]]
    ai_feedback_data: Optional[Dict[str, Any]]
    processing_start_time: Optional[float]
    
    # Self-reflection & quality control
    grading_confidence: Optional[float]
    consistency_score: Optional[float]
    detected_issues: List[str]
    needs_human_review: bool
    review_reasons: List[str]
    
    # Adaptive rubric
    rubric_used: Optional[Dict[str, Any]]
    adapted_rubric: bool
    criterion_scores: Optional[Dict[str, float]]
    
    # Intelligent feedback
    feedback_quality: Optional[float]
    suggested_improvements: List[str]
    positive_highlights: List[str]
    
    # Error detection
    potential_errors: List[Dict[str, Any]]
    auto_corrections: List[Dict[str, Any]]
    
    # Comparative analysis
    compared_to_average: Optional[bool]
    percentile_rank: Optional[float]
    
    # Multi-step planning
    is_complex_grading: bool
    grading_plan: Optional[List[Dict[str, Any]]]
    current_grading_step: int
    completed_grading_steps: List[str]
    intermediate_grading_results: List[Dict[str, Any]]
    
    # Iteration tracking
    iteration: int
    max_iterations: int

