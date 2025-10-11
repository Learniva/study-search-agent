"""State definitions for Study Agent."""

from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langgraph.graph.message import add_messages


class StudyAgentState(TypedDict):
    """State schema for Study Agent with agentic capabilities."""
    
    # Core message and question
    messages: Annotated[List[Any], add_messages]
    question: str
    original_question: str
    
    # Tool execution
    tool_used: Optional[str]
    tool_result: Optional[str]
    tools_used_history: List[str]
    
    # Results
    final_answer: Optional[str]
    
    # Fallback tracking
    tried_document_qa: bool
    document_qa_failed: bool
    iteration: int
    
    # Multi-step planning
    is_complex_task: bool
    task_plan: Optional[List[Dict[str, Any]]]
    current_step: int
    completed_steps: List[str]
    intermediate_answers: List[Dict[str, Any]]
    
    # Self-reflection
    response_confidence: Optional[float]
    quality_issues: List[str]
    needs_clarification: bool
    clarification_question: Optional[str]
    
    # Adaptive behavior
    fallback_attempts: int
    max_iterations: int
    suggested_followups: List[str]
    alternative_approaches: List[str]
    error_context: Optional[Dict[str, Any]]
    needs_retry: bool
    
    # User choice handling (for web search permission)
    awaiting_user_choice: bool
    user_choice_web_search: bool
    user_choice_upload: bool

