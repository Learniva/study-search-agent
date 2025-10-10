"""
API Request/Response Models.

Pydantic models for API request validation and response serialization.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# Request Models
# ============================================================================

class QueryRequest(BaseModel):
    """Query request model."""
    
    question: str = Field(
        ...,
        description="User question or request",
        min_length=1,
        max_length=5000
    )
    thread_id: str = Field(
        default="default",
        description="Conversation thread ID for context"
    )
    user_role: str = Field(
        default="student",
        description="User role: student, teacher, or admin"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for ML features"
    )
    professor_id: Optional[str] = Field(
        default=None,
        description="Professor ID for grading"
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Student ID for grading"
    )
    student_name: Optional[str] = Field(
        default=None,
        description="Student name for grading"
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Course ID for grading"
    )
    assignment_id: Optional[str] = Field(
        default=None,
        description="Assignment ID for grading"
    )
    assignment_name: Optional[str] = Field(
        default=None,
        description="Assignment name for grading"
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming response"
    )
    
    @validator('user_role')
    def validate_role(cls, v):
        """Validate user role."""
        if v not in ['student', 'teacher', 'admin']:
            raise ValueError('Role must be student, teacher, or admin')
        return v


class FeedbackRequest(BaseModel):
    """User feedback request."""
    
    thread_id: str = Field(..., description="Thread ID")
    question: str = Field(..., description="Original question")
    response: str = Field(..., description="Agent response")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    helpful: bool = Field(..., description="Was response helpful?")
    comment: Optional[str] = Field(None, description="Optional comment")
    user_id: Optional[str] = Field(None, description="User ID")


class ProfessorFeedbackRequest(BaseModel):
    """Professor grading feedback request."""
    
    session_id: str = Field(..., description="Grading session ID")
    original_grade: float = Field(..., description="AI assigned grade")
    actual_grade: float = Field(..., description="Professor's grade")
    rubric_id: str = Field(..., description="Rubric used")
    professor_id: str = Field(..., description="Professor ID")
    student_id: str = Field(..., description="Student ID")
    submission_text: str = Field(..., description="Student submission")
    comments: Optional[str] = Field(None, description="Comments")
    criteria_adjustments: Optional[Dict[str, float]] = Field(
        None,
        description="Criteria score adjustments"
    )


# ============================================================================
# Response Models
# ============================================================================

class QueryResponse(BaseModel):
    """Query response model."""
    
    answer: str = Field(..., description="Agent's answer")
    thread_id: str = Field(..., description="Thread ID")
    agent_used: Optional[str] = Field(None, description="Agent that handled query")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class UploadResponse(BaseModel):
    """Document upload response."""
    
    filename: str = Field(..., description="Uploaded filename")
    message: str = Field(..., description="Status message")
    success: bool = Field(..., description="Upload success")


class DocumentInfo(BaseModel):
    """Document information."""
    
    name: str
    size: int
    type: str


class DocumentsListResponse(BaseModel):
    """Documents list response."""
    
    documents: List[DocumentInfo]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    supervisor_ready: bool
    database_available: bool
    ml_features_available: bool
    documents_loaded: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"


class ConversationHistoryResponse(BaseModel):
    """Conversation history response."""
    
    thread_id: str
    messages: List[Dict[str, Any]]
    total_messages: int


class GradingHistoryItem(BaseModel):
    """Single grading history item."""
    
    id: int
    session_id: str
    student_id: str
    student_name: Optional[str]
    assignment_id: Optional[str]
    assignment_name: Optional[str]
    rubric_id: Optional[str]
    grade: Optional[float]
    feedback: Optional[str]
    created_at: datetime


class GradingHistoryResponse(BaseModel):
    """Grading history response."""
    
    professor_id: str
    history: List[GradingHistoryItem]
    total: int


class RubricTemplate(BaseModel):
    """Rubric template."""
    
    id: Optional[int] = None
    rubric_id: str
    professor_id: str
    rubric_name: str
    rubric_data: Dict[str, Any]
    created_at: Optional[datetime] = None


class RubricListResponse(BaseModel):
    """Rubric list response."""
    
    rubrics: List[RubricTemplate]
    total: int


class MLProfileResponse(BaseModel):
    """ML user profile response."""
    
    user_id: str
    query_count: int
    successful_queries: int
    avg_rating: Optional[float]
    preferences: Dict[str, Any]
    learning_stats: Dict[str, Any]


class MLStatsResponse(BaseModel):
    """ML statistics response."""
    
    total_queries: int
    unique_users: int
    avg_rating: float
    popular_topics: List[str]
    performance_metrics: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

