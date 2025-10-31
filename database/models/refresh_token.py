"""
Refresh Token Model for Token Rotation with Server-Side Revocation.

Implements secure refresh token rotation with chain tracking and revocation.
Key features:
- Each refresh creates a new token and links to parent
- Rotation chain tracking for detecting misuse
- Entire chain revocation on first misuse
- Supports httpOnly cookie storage
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from database.models.base import Base
from config import settings


class RefreshToken(Base):
    """
    Refresh token model for secure token rotation.
    
    Implements the refresh token rotation pattern where:
    1. Each refresh token can only be used once
    2. Using a token generates a new token (rotation)
    3. All tokens in a chain are linked via parent_token_id
    4. First misuse (reuse of old token) → revoke entire chain
    5. Tokens stored as httpOnly cookies for XSS protection
    """
    __tablename__ = "refresh_tokens"
    
    # Primary key - unique token identifier
    token_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # The actual refresh token value (JWT or random string)
    token = Column(String(512), unique=True, nullable=False, index=True)
    
    # Foreign key to user
    user_id = Column(String(255), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Rotation chain tracking
    parent_token_id = Column(String(36), ForeignKey("refresh_tokens.token_id"), nullable=True, index=True)
    rotation_chain_id = Column(String(36), nullable=False, index=True)  # All tokens in rotation chain share this
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)  # When token was used for rotation
    
    # Revocation tracking
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(255), nullable=True)  # e.g., "logout", "misuse_detected", "expired"
    
    # Security metadata
    device_info = Column(String(500), nullable=True)  # User agent string
    ip_address = Column(String(45), nullable=True)    # IPv4 or IPv6
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_refresh_token_chain', 'rotation_chain_id', 'is_revoked'),
        Index('idx_refresh_token_user_active', 'user_id', 'is_revoked', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<RefreshToken {self.token_id[:8]}... for user {self.user_id}>"
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_valid(self) -> bool:
        """
        Check if token is valid for use.
        
        A token is valid if:
        - Not revoked
        - Not expired
        - Not already used (used_at is None)
        """
        return (
            not self.is_revoked 
            and not self.is_expired() 
            and self.used_at is None
        )
    
    def is_reused(self) -> bool:
        """Check if token has been used before (reuse = potential attack)."""
        return self.used_at is not None
    
    @classmethod
    def create_expiry(cls, days: Optional[int] = None) -> datetime:
        """
        Create expiry datetime for refresh token.
        
        Args:
            days: Optional custom expiry in days (default from settings)
        
        Returns:
            Expiry datetime in UTC
        """
        days = days or int(settings.refresh_token_expire_days) if hasattr(settings, 'refresh_token_expire_days') else 7
        return datetime.now(timezone.utc) + timedelta(days=days)
    
    @classmethod
    def generate_chain_id(cls) -> str:
        """Generate a new rotation chain ID."""
        return str(uuid.uuid4())
