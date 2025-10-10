"""
Grading Models

Models for grading sessions, rubrics, configurations, and statistics.
"""

from .base import (
    Base, Column, String, Integer, Float, DateTime, Text, Boolean,
    ForeignKey, UUID, JSONB, Index, relationship, datetime, uuid
)


class GradingSession(Base):
    """
    Grading session record - stores each grading interaction.
    
    This is the core table for professor's grading history.
    """
    __tablename__ = "grading_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Professor information
    professor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Student information
    student_id = Column(String(255), index=True)  # External student ID
    student_name = Column(String(255))
    
    # Assignment information
    course_id = Column(String(255), index=True)
    assignment_id = Column(String(255), index=True)
    assignment_name = Column(String(500))
    
    # Grading type
    grading_type = Column(String(50), nullable=False, index=True)  # essay, code, mcq, rubric, feedback
    
    # Submission content (stored as JSON for flexibility)
    submission = Column(JSONB)  # Original student submission
    
    # Grading results
    score = Column(Float)
    max_score = Column(Float)
    percentage = Column(Float)
    grade_letter = Column(String(10))
    
    # Detailed feedback (JSON format from AI tools)
    ai_feedback = Column(JSONB)  # Raw AI output
    professor_feedback = Column(Text)  # Professor's additional comments
    
    # Rubric used (if applicable)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubric_templates.id"), nullable=True)
    rubric_data = Column(JSONB)  # Snapshot of rubric at grading time
    
    # AI metadata
    agent_used = Column(String(100))  # Which grading tool was used
    ai_confidence = Column(Float)
    processing_time_seconds = Column(Float)
    
    # Professor actions
    reviewed_by_professor = Column(Boolean, default=False)
    professor_adjusted_score = Column(Float, nullable=True)
    posted_to_lms = Column(Boolean, default=False)
    posted_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    professor = relationship("User", back_populates="grading_sessions", foreign_keys=[professor_id])
    rubric = relationship("RubricTemplate", foreign_keys=[rubric_id])
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_professor_created", "professor_id", "created_at"),
        Index("idx_course_assignment", "course_id", "assignment_id"),
        Index("idx_student_course", "student_id", "course_id"),
    )
    
    def __repr__(self):
        return f"<GradingSession(type={self.grading_type}, student={self.student_name}, score={self.score})>"


class RubricTemplate(Base):
    """
    Rubric templates created by professors.
    
    Professors can save and reuse rubrics across assignments.
    """
    __tablename__ = "rubric_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Rubric information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    rubric_type = Column(String(50))  # essay, code, presentation, etc.
    
    # Rubric structure (JSON)
    criteria = Column(JSONB, nullable=False)  # List of criteria with weights and levels
    max_score = Column(Float, nullable=False)
    
    # Metadata
    times_used = Column(Integer, default=0)
    is_public = Column(Boolean, default=False)  # Can other professors use this?
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    professor = relationship("User", back_populates="rubric_templates")
    
    def __repr__(self):
        return f"<RubricTemplate(name={self.name}, type={self.rubric_type})>"


class ProfessorConfiguration(Base):
    """
    Professor-specific configurations and preferences.
    """
    __tablename__ = "professor_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    # Grading preferences
    default_feedback_tone = Column(String(50), default="constructive")  # constructive, encouraging, detailed, concise
    auto_post_to_lms = Column(Boolean, default=False)
    require_manual_review = Column(Boolean, default=True)
    
    # Default rubrics
    default_essay_rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubric_templates.id"), nullable=True)
    default_code_rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubric_templates.id"), nullable=True)
    
    # AI preferences
    ai_confidence_threshold = Column(Float, default=0.7)  # Minimum confidence to show AI grade
    show_ai_explanations = Column(Boolean, default=True)
    
    # Custom settings (JSON for flexibility)
    custom_settings = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    professor = relationship("User", back_populates="configurations")
    
    def __repr__(self):
        return f"<ProfessorConfiguration(professor_id={self.professor_id})>"


class GradingStatistics(Base):
    """
    Aggregated statistics for professors and courses.
    
    Denormalized table for fast analytics queries.
    """
    __tablename__ = "grading_statistics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Scope
    professor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    course_id = Column(String(255), index=True)
    assignment_id = Column(String(255), index=True)
    period = Column(String(50))  # daily, weekly, monthly
    date = Column(DateTime, index=True)
    
    # Statistics
    total_gradings = Column(Integer, default=0)
    avg_score = Column(Float)
    avg_processing_time = Column(Float)
    total_students = Column(Integer)
    
    # Breakdown by type
    essay_count = Column(Integer, default=0)
    code_count = Column(Integer, default=0)
    mcq_count = Column(Integer, default=0)
    
    # AI metrics
    avg_ai_confidence = Column(Float)
    manual_adjustments = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_professor_period", "professor_id", "period", "date"),
    )
    
    def __repr__(self):
        return f"<GradingStatistics(professor={self.professor_id}, date={self.date}, total={self.total_gradings})>"


__all__ = [
    'GradingSession',
    'RubricTemplate',
    'ProfessorConfiguration',
    'GradingStatistics',
]

