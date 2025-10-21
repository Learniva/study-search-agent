"""
Authentication and Authorization utilities for the Multi-Agent System.

Provides:
- JWT token generation and validation
- Role-based access control decorators
- User authentication helpers
- LMS integration authentication (Canvas, Google Classroom)
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from functools import wraps

from fastapi import HTTPException, Header, Depends
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
# SECURITY: Secret key is required and must be secure
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError(
        "JWT_SECRET_KEY environment variable is required and must be at least 32 characters long. "
        "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


class TokenData(BaseModel):
    """JWT token data structure."""
    user_id: str
    role: str  # student, teacher, admin
    email: Optional[str] = None
    name: Optional[str] = None
    course_id: Optional[str] = None
    lms: Optional[str] = None  # canvas, google_classroom, None


class User(BaseModel):
    """User model."""
    user_id: str
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    course_id: Optional[str] = None


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing user data (user_id, role, etc.)
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    
    Example:
        token = create_access_token({"user_id": "123", "role": "teacher"})
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData object with user information
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id: str = payload.get("user_id")
        role: str = payload.get("role", "student")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing user_id")
        
        return TokenData(
            user_id=user_id,
            role=role,
            email=payload.get("email"),
            name=payload.get("name"),
            course_id=payload.get("course_id"),
            lms=payload.get("lms")
        )
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(authorization: str = Header(None)) -> User:
    """
    Dependency to get current user from JWT token in Authorization header.
    
    Usage in FastAPI endpoint:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.user_id, "role": user.role}
    
    Args:
        authorization: Authorization header (format: "Bearer <token>")
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Use 'Bearer <token>'"
            )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use 'Bearer <token>'"
        )
    
    # Decode token
    token_data = decode_access_token(token)
    
    return User(
        user_id=token_data.user_id,
        role=token_data.role,
        email=token_data.email,
        name=token_data.name,
        course_id=token_data.course_id
    )


async def get_current_teacher(user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require teacher/admin role.
    
    Usage:
        @app.post("/grade")
        async def grade_essay(user: User = Depends(get_current_teacher)):
            # Only teachers can access this endpoint
            ...
    
    Args:
        user: Current user from get_current_user dependency
        
    Returns:
        User object (only if role is teacher/admin)
        
    Raises:
        HTTPException: If user is not a teacher or admin
    """
    allowed_roles = ["teacher", "admin", "instructor", "professor"]
    
    if user.role.lower() not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. This endpoint requires teacher/admin role. Your role: {user.role}"
        )
    
    return user


def require_role(*allowed_roles: str):
    """
    Decorator to require specific roles for an endpoint.
    
    Usage:
        @app.post("/admin")
        @require_role("admin")
        async def admin_only(user: User = Depends(get_current_user)):
            ...
    
    Args:
        allowed_roles: Variable number of allowed role strings
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = Depends(get_current_user), **kwargs):
            if user.role.lower() not in [r.lower() for r in allowed_roles]:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Required roles: {', '.join(allowed_roles)}. Your role: {user.role}"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# DEPRECATED: Test authentication functions removed for security
# =============================================================================
# 
# The test authentication functions (authenticate_user, create_token_for_user)
# have been REMOVED due to security concerns.
#
# For authentication, use:
# - Production: database.operations.user_ops.authenticate_user() with hashed passwords
# - Testing: Create proper test fixtures with hashed passwords
# - OAuth: api/routers/auth.py for Google OAuth
#
# DO NOT re-add hardcoded credentials to this codebase.
# =============================================================================


# LMS Integration helpers

def validate_canvas_token(canvas_token: str, canvas_url: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Canvas LMS access token and get user info.
    
    Args:
        canvas_token: Canvas API token
        canvas_url: Canvas instance URL (e.g., "https://canvas.instructure.com")
        
    Returns:
        User data dict if valid, None otherwise
    
    Note: Requires canvasapi package: pip install canvasapi
    """
    try:
        from canvasapi import Canvas
        
        canvas = Canvas(canvas_url, canvas_token)
        user = canvas.get_current_user()
        
        # Determine role (simplified - Canvas has more complex role system)
        # In production, check enrollments for current course
        is_teacher = hasattr(user, 'enrollments') and any(
            e.role in ['TeacherEnrollment', 'TaEnrollment', 'DesignerEnrollment'] 
            for e in user.enrollments
        )
        
        return {
            "user_id": str(user.id),
            "role": "teacher" if is_teacher else "student",
            "email": getattr(user, 'email', None),
            "name": user.name,
            "lms": "canvas"
        }
    except Exception as e:
        print(f"Canvas token validation error: {e}")
        return None


def validate_google_classroom_token(google_token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Google Classroom OAuth token and get user info.
    
    Args:
        google_token: Google OAuth 2.0 access token
        
    Returns:
        User data dict if valid, None otherwise
    
    Note: Requires google-api-python-client and google-auth
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        credentials = Credentials(token=google_token)
        service = build('classroom', 'v1', credentials=credentials)
        
        # Get user profile
        profile = service.userProfiles().get(userId='me').execute()
        
        # Determine role by checking if user is teacher in any course
        courses = service.courses().list(teacherId='me', pageSize=1).execute()
        is_teacher = len(courses.get('courses', [])) > 0
        
        return {
            "user_id": profile['id'],
            "role": "teacher" if is_teacher else "student",
            "email": profile.get('emailAddress'),
            "name": profile.get('name', {}).get('fullName'),
            "lms": "google_classroom"
        }
    except Exception as e:
        print(f"Google Classroom token validation error: {e}")
        return None


# Rate limiting helper

class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    In production, use Redis or similar for distributed rate limiting.
    """
    def __init__(self):
        self.requests = {}  # {user_id: [timestamp1, timestamp2, ...]}
    
    def check_rate_limit(self, user_id: str, max_requests: int = 60, window_minutes: int = 60) -> bool:
        """
        Check if user is within rate limit.
        
        Args:
            user_id: User identifier
            max_requests: Maximum requests allowed in window
            window_minutes: Time window in minutes
            
        Returns:
            True if within limit, False if exceeded
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        # Get user's request history
        user_requests = self.requests.get(user_id, [])
        
        # Filter to current window
        user_requests = [ts for ts in user_requests if ts > window_start]
        
        # Check if within limit
        if len(user_requests) >= max_requests:
            return False
        
        # Add current request
        user_requests.append(now)
        self.requests[user_id] = user_requests
        
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()

