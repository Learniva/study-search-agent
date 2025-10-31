"""
Token Model for PostgreSQL-based session management.
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime, timedelta

from database.models.base import Base
from config import settings


class Token(Base):
    """
    Authentication token model for persistent session management.
    
    Stores tokens in PostgreSQL instead of Redis for reliability.
    """
    __tablename__ = "tokens"
    
    # Primary key
    token = Column(String(128), primary_key=True, index=True)  # Increased from 64 to 128 to accommodate full token
    
    # Foreign key to user
    user_id = Column(String(255), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Token metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Token status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Optional: Track device/IP for security
    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    def __repr__(self):
        return f"<Token {self.token[:8]}... for user {self.user_id}>"
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        from datetime import timezone as tz
        return datetime.now(tz.utc) > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and active)."""
        return self.is_active and not self.is_expired()
    
    @classmethod
    def create_expiry(cls) -> datetime:
        """Create expiry datetime based on settings."""
        from datetime import timezone as tz
        hours = getattr(settings, 'token_expire_hours', 24)
        return datetime.now(tz.utc) + timedelta(hours=hours)

