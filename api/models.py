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
        description="User role: student, teacher, professor, instructor, or admin"
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
        valid_roles = ['student', 'teacher', 'professor', 'instructor', 'admin']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
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


# ============================================================================
# Profile Models
# ============================================================================

class ProfileInformation(BaseModel):
    """Profile information model."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: str
    email: str
    display_name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    profile_picture: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """Update profile request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


class ProfileResponse(BaseModel):
    """Profile response."""
    id: str  # Changed from int to str for UUID compatibility
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    location: Optional[str]
    website: Optional[str]
    profile_picture: Optional[str]
    role: str


# ============================================================================
# Settings Models
# ============================================================================

class NotificationSettings(BaseModel):
    """Notification settings model."""
    email_notifications: bool = True
    push_notifications: bool = False
    weekly_digest: bool = True
    product_updates: bool = False
    study_reminders: bool = True


class PreferencesSettings(BaseModel):
    """Preferences settings model."""
    language: str = "English"
    timezone: str = "UTC"
    date_format: str = "MM/DD/YYYY"


class AppearanceSettings(BaseModel):
    """Appearance settings model."""
    theme: str = "system"  # system, light, dark
    compact_mode: bool = False
    animations: bool = True


class UserSettings(BaseModel):
    """Complete user settings model."""
    notifications: NotificationSettings
    preferences: PreferencesSettings
    appearance: AppearanceSettings


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str
    confirm_password: str


# ============================================================================
# Help & Support Models
# ============================================================================

class FAQItem(BaseModel):
    """FAQ item model."""
    id: int
    question: str
    answer: str
    category: str
    helpful_count: int = 0


class SupportTicketRequest(BaseModel):
    """Support ticket request."""
    subject: str
    message: str
    category: str
    priority: str = "normal"  # low, normal, high, urgent


class SupportTicketResponse(BaseModel):
    """Support ticket response."""
    ticket_id: str
    subject: str
    status: str
    created_at: datetime
    last_updated: datetime


class ContactRequest(BaseModel):
    """Contact form request."""
    name: str
    email: str
    subject: str
    message: str

