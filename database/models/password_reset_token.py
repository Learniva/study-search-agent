"""
Password Reset Token Model

Stores password reset tokens for email-based password reset flow.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Index
from sqlalchemy.sql import func
from database.models.base import Base


class PasswordResetToken(Base):
    """Password reset token model."""
    
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_token_email', 'token', 'email'),
        Index('idx_email_created', 'email', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PasswordResetToken(email={self.email}, is_used={self.is_used})>"

