"""User authentication models."""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum, Text
from sqlalchemy.sql import func
from .base import Base
import enum


class UserRole(str, enum.Enum):
    """User role enum."""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and OAuth."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)  # Profile picture URL
    google_id = Column(String, unique=True, index=True, nullable=True)  # Google OAuth ID
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False, default=UserRole.STUDENT)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)


class UserLearningProfile(Base):
    """User learning profile for personalization."""
    
    __tablename__ = "user_learning_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True)
    learning_style = Column(String, nullable=True)
    preferred_difficulty = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
