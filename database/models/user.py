"""
User Models

User authentication and profile models for the grading system.
"""

from .base import (
    Base, Column, String, DateTime, Boolean, UUID, JSONB, Float, Integer,
    relationship, datetime, uuid, Index
)
from datetime import timezone


class User(Base):
    """
    User model for professors, students, and admins.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), unique=True, nullable=False, index=True)  # External ID (from LMS)
    role = Column(String(50), nullable=False, index=True)  # student, teacher, admin
    email = Column(String(255), unique=True, index=True)
    name = Column(String(255))
    lms_type = Column(String(50))  # canvas, google_classroom, None
    course_id = Column(String(255), index=True)
    
    # Profile information
    username = Column(String(255), unique=True, index=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    display_name = Column(String(255))
    profile_picture = Column(String(512))
    location = Column(String(255))
    website = Column(String(512))
    
    # Settings (stored as JSONB for flexibility)
    settings = Column(JSONB, default=dict)  # Notification, preference, and appearance settings
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    grading_sessions = relationship("GradingSession", back_populates="professor", foreign_keys="GradingSession.professor_id")
    rubric_templates = relationship("RubricTemplate", back_populates="professor")
    configurations = relationship("ProfessorConfiguration", back_populates="professor", uselist=False)
    
    def __repr__(self):
        return f"<User(id={self.user_id}, role={self.role}, name={self.name})>"


class UserLearningProfile(Base):
    """
    User Learning Profile - ML-enhanced user preferences and patterns.
    
    Stores learned preferences, interaction patterns, and performance metrics
    for personalized agent behavior adaptation.
    """
    __tablename__ = "user_learning_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(String(50), nullable=False)  # student, teacher, professor
    
    # Learning preferences (JSONB for flexibility)
    preferred_explanation_depth = Column(String(50), default="moderate")  # brief, moderate, detailed
    preferred_citation_style = Column(String(20), nullable=True)  # APA, MLA, Chicago
    typical_subject_areas = Column(JSONB, default=list)  # List of topics
    education_level = Column(String(50), nullable=True)  # high_school, undergraduate, graduate
    
    # Interaction patterns (learned over time)
    average_question_length = Column(Float, default=50.0)
    common_tools_used = Column(JSONB, default=dict)  # Dict of tool: count
    typical_session_duration = Column(Float, default=600.0)  # seconds
    queries_per_session = Column(Float, default=5.0)
    
    # Feedback history
    positive_feedback_count = Column(Integer, default=0)
    negative_feedback_count = Column(Integer, default=0)
    neutral_feedback_count = Column(Integer, default=0)
    correction_patterns = Column(JSONB, default=list)  # List of correction events
    
    # Performance metrics (0-1 scale)
    satisfaction_score = Column(Float, default=0.5)
    response_relevance_score = Column(Float, default=0.5)
    tool_selection_accuracy = Column(Float, default=0.5)
    
    # Adaptation weights (learned preferences)
    routing_preferences = Column(JSONB, default=dict)  # Dict of tool: weight
    temperature_preference = Column(Float, default=0.7)  # LLM creativity
    context_window_preference = Column(Integer, default=2)  # Messages to include
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    interactions_count = Column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        Index("idx_user_learning_updated", "user_id", "last_updated"),
        Index("idx_user_learning_satisfaction", "satisfaction_score", "interactions_count"),
    )
    
    def __repr__(self):
        return f"<UserLearningProfile(user={self.user_id}, interactions={self.interactions_count})>"


__all__ = ['User', 'UserLearningProfile']

