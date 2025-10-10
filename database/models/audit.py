"""
Audit Models

Audit logging and compliance tracking for the grading system.
"""

from .base import (
    Base, Column, String, Text, DateTime, Boolean,
    UUID, JSONB, Index, datetime, uuid
)


class AuditLog(Base):
    """
    Audit log for all grading actions.
    
    Important for compliance, accountability, and debugging.
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who did what
    user_id = Column(String(255), index=True, nullable=False)
    user_role = Column(String(50))
    
    # Action details
    action_type = Column(String(100), nullable=False, index=True)  # grade_essay, review_code, etc.
    resource_type = Column(String(50))  # grading_session, rubric, configuration
    resource_id = Column(UUID(as_uuid=True))
    
    # What changed
    action_details = Column(JSONB)  # Detailed information about the action
    old_value = Column(JSONB, nullable=True)  # For updates
    new_value = Column(JSONB, nullable=True)  # For updates
    
    # Context
    course_id = Column(String(255), index=True)
    student_id = Column(String(255), index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    # Success/failure
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Index for common audit queries
    __table_args__ = (
        Index("idx_user_action_time", "user_id", "action_type", "created_at"),
        Index("idx_resource", "resource_type", "resource_id"),
    )
    
    def __repr__(self):
        return f"<AuditLog(user={self.user_id}, action={self.action_type}, time={self.created_at})>"


__all__ = ['AuditLog']

