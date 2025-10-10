"""
User Models

User authentication and profile models for the grading system.
"""

from .base import (
    Base, Column, String, DateTime, Boolean, UUID,
    relationship, datetime, uuid, Index
)


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
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    grading_sessions = relationship("GradingSession", back_populates="professor", foreign_keys="GradingSession.professor_id")
    rubric_templates = relationship("RubricTemplate", back_populates="professor")
    configurations = relationship("ProfessorConfiguration", back_populates="professor", uselist=False)
    
    def __repr__(self):
        return f"<User(id={self.user_id}, role={self.role}, name={self.name})>"


__all__ = ['User']

