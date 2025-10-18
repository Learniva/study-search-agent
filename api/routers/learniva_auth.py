"""
Production-Ready Authentication with PostgreSQL

This module provides Django REST Framework style token authentication
with persistent storage using PostgreSQL for both tokens and users.

Features:
- PostgreSQL for persistent token storage (survives restarts)
- PostgreSQL for user data
- Bcrypt password hashing
- Token expiry and cleanup
- Session management
- Optional Redis caching for performance
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import logging

from config.settings import settings
from database.operations.user_ops import (
    create_user,
    authenticate_user,
    get_user_by_id,
    update_user_activity,
)
from database.operations.token_ops import (
    create_token,
    get_token,
    delete_token,
    delete_user_tokens,
)
from database.core.async_connection import get_session
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

# ============================================================================
# Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request body."""
    username: str  # Can be email or username
    password: str


class LoginResponse(BaseModel):
    """Login response matching Learniva frontend expectations."""
    token: str
    user: dict


class RegisterRequest(BaseModel):
    """Registration request body."""
    username: str
    email: EmailStr
    password: str
    password2: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""


class UserResponse(BaseModel):
    """User data response."""
    id: int
    pk: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    display_name: Optional[str] = None
    profile_picture: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

async def create_token_for_user(
    session: AsyncSession,
    user_id: str,
    role: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str:
    """
    Generate authentication token and store in PostgreSQL.
    
    Args:
        session: Database session
        user_id: User's unique identifier
        role: User role (student, teacher, admin)
        device_info: Optional device information
        ip_address: Optional IP address
    
    Returns:
        Secure random token string
    """
    token_obj = await create_token(
        session,
        user_id,
        device_info=device_info,
        ip_address=ip_address
    )
    
    if not token_obj:
        logger.error(f"❌ Failed to create token for user: {user_id}")
        raise HTTPException(status_code=500, detail="Failed to create authentication token")
    
    logger.info(f"🔑 Token created for user: {user_id} (expires in {settings.token_expire_hours}h)")
    return token_obj.token


async def verify_token_data(session: AsyncSession, token_value: str) -> Optional[dict]:
    """
    Verify token validity and return associated user data.
    
    Args:
        session: Database session
        token_value: Token string to verify
    
    Returns:
        User data if token valid, None if invalid or expired
    """
    token = await get_token(session, token_value)
    if not token:
        logger.debug(f"🔍 Token not found or expired: {token_value[:20]}...")
        return None
    
    # Get user data
    user = await get_user_by_id(session, token.user_id)
    if not user:
        logger.warning(f"⚠️ Token valid but user not found: {token.user_id}")
        return None
    
    logger.debug(f"✅ Token verified for user: {user.username}")
    return {
        "user_id": user.user_id,
        "role": user.role,
        "username": user.username,
        "email": user.email,
    }


def user_to_dict(user) -> dict:
    """Convert User model to dictionary for API response."""
    return {
        "id": hash(user.user_id) % 1000000,  # Generate numeric ID from string
        "pk": hash(user.user_id) % 1000000,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "role": user.role,
        "display_name": user.display_name,
        "profile_picture": user.profile_picture,
        "location": user.location,
        "website": user.website,
    }


# ============================================================================
# Dependencies
# ============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Dependency to extract and validate user from Authorization header.
    
    Accepts both "Token abc123..." and "Bearer abc123..." formats
    
    Args:
        authorization: Authorization header value
        session: Database session
    
    Returns:
        User dictionary
    
    Raises:
        HTTPException: If auth fails
    """
    if not authorization:
        logger.debug("🔒 Auth: No Authorization header provided")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Authorization header required"}
        )
    
    # Parse "Token xyz" or "Bearer xyz" format
    logger.debug(f"🔒 Auth: Authorization header received: {authorization[:50]}...")
    try:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2:
            scheme, token = parts
            logger.debug(f"🔒 Auth: Scheme='{scheme}', Token='{token[:20]}...'")
            # Accept both "Token" (Django REST Framework) and "Bearer" (OAuth2) formats
            if scheme.lower() not in ["token", "bearer"]:
                logger.debug(f"🔒 Auth: Invalid scheme '{scheme}'")
                raise ValueError("Invalid scheme")
        else:
            # If no scheme, treat entire string as token
            token = authorization
            logger.debug(f"🔒 Auth: No scheme, using entire string as token")
    except (ValueError, AttributeError) as e:
        logger.debug(f"🔒 Auth: Error parsing header: {e}")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid authorization header format"}
        )
    
    # Verify token (now returns user data directly from PostgreSQL)
    token_data = await verify_token_data(session, token)
    if not token_data:
        logger.debug(f"🔒 Auth: Token verification failed - invalid or expired")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid or expired token"}
        )
    
    # Get full user object from database
    user = await get_user_by_id(session, token_data["user_id"])
    if not user:
        logger.warning(f"🔒 Auth: User not found in database: {token_data['user_id']}")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "User not found"}
        )
    
    if not user.is_active:
        logger.warning(f"🔒 Auth: Inactive user attempted access: {user.username}")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "User account is inactive"}
        )
    
    logger.debug(f"✅ Auth: Successfully authenticated user: {user.username}")
    return user_to_dict(user)


# ============================================================================
# Auth Endpoints
# ============================================================================

@router.post("/login/", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Login endpoint.
    
    Authenticates user and returns token.
    """
    logger.info(f"🔐 Login attempt: {request.username}")
    
    # Authenticate user
    user = await authenticate_user(session, request.username, request.password)
    
    if not user:
        logger.warning(f"❌ Login failed: {request.username}")
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Invalid username or password"}
        )
    
    # Create token
    token = await create_token_for_user(session, user.user_id, user.role)
    
    logger.info(f"✅ Login successful: {user.username}")
    
    return LoginResponse(
        token=token,
        user=user_to_dict(user)
    )


@router.post("/logout/")
async def logout(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Logout endpoint.
    
    Invalidates the user's token by deleting it from PostgreSQL.
    Works even with invalid/expired tokens since the user wants to logout anyway.
    """
    if authorization:
        # Extract token
        try:
            parts = authorization.split(maxsplit=1)
            token_value = parts[1] if len(parts) == 2 else authorization
            
            # Try to delete token from database (if it exists)
            await delete_token(session, token_value)
            logger.info(f"👋 Logout: Token invalidated")
        except Exception as e:
            logger.debug(f"Logout with invalid token (expected): {e}")
    
    # Always return success - logout should be idempotent
    return {
        "success": True,
        "message": "Logged out successfully"
    }


@router.post("/register/", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Registration endpoint.
    
    Creates new user account and returns token.
    """
    logger.info(f"📝 Registration attempt: {request.username} ({request.email})")
    
    # Validate passwords match
    if request.password != request.password2:
        raise HTTPException(
            status_code=400,
            detail={"error": "password_mismatch", "message": "Passwords do not match"}
        )
    
    # Validate password strength (basic)
    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must be at least 8 characters"}
        )
    
    # Create user
    user = await create_user(
        session,
        email=request.email,
        username=request.username,
        password=request.password,
        role="student",  # Default role
        first_name=request.first_name,
        last_name=request.last_name,
    )
    
    if not user:
        logger.warning(f"❌ Registration failed: {request.username} (duplicate)")
        raise HTTPException(
            status_code=400,
            detail={"error": "duplicate_user", "message": "Username or email already exists"}
        )
    
    # Create token
    token = await create_token_for_user(session, user.user_id, user.role)
    
    logger.info(f"✅ Registration successful: {user.username}")
    
    return LoginResponse(
        token=token,
        user=user_to_dict(user)
    )


@router.get("/auth/user/", response_model=UserResponse)
async def get_authenticated_user(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user.
    
    Returns user data for authenticated user.
    """
    logger.debug(f"👤 User info requested: {current_user['username']}")
    return current_user


@router.get("/health/auth")
async def auth_health():
    """
    Health check for authentication system.
    
    Returns status of Redis and token storage.
    """
    return {
        "status": "healthy",
        "redis_connected": token_store.redis_client is not None,
        "active_tokens": token_store.count(),
        "token_expiry_hours": settings.token_expire_hours,
    }


__all__ = ['router', 'get_current_user']

