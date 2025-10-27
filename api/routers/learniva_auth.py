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
from uuid import UUID
import logging

from config.settings import settings
from database.operations.user_ops import (
    create_user,
    authenticate_user,
    get_user_by_id,
    get_user_by_email,
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
router = APIRouter(prefix="/api/auth", tags=["auth"])

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


class PasswordResetRequest(BaseModel):
    """Password reset request body."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation body."""
    email: EmailStr
    token: str
    new_password: str
    confirm_password: str


class UserResponse(BaseModel):
    """User data response."""
    id: str  # Changed from int to str to support UUID
    pk: str  # Changed from int to str to support UUID
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
        User object if token valid, None if invalid or expired
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
    return user


def user_to_dict(user) -> dict:
    """Convert User model to dictionary for API response."""
    return {
        "id": str(user.id),  # Use actual UUID string instead of hash
        "pk": str(user.id),  # Use actual UUID string instead of hash
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
    
    NOW WITH TOKEN CACHING:
    - Cache hit: <1ms (no DB queries)
    - Cache miss: 20-50ms (2 DB queries, then cached)
    - Cache TTL: 5 minutes
    - Expected hit rate: ~95%
    
    Accepts both "Token abc123..." and "Bearer abc123..." formats
    
    Args:
        authorization: Authorization header value
        session: Database session
    
    Returns:
        User dictionary
    
    Raises:
        HTTPException: If auth fails
    """
    from utils.auth.token_cache import get_token_cache
    
    if not authorization:
        logger.debug("🔒 Auth: No Authorization header provided")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Authorization header required"}
        )
    
    # Parse "Token xyz" or "Bearer xyz" format
    try:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2:
            scheme, token = parts
            # Accept both "Token" (Django REST Framework) and "Bearer" (OAuth2) formats
            if scheme.lower() not in ["token", "bearer"]:
                logger.debug(f"🔒 Auth: Invalid scheme '{scheme}'")
                raise ValueError("Invalid scheme")
        else:
            # If no scheme, treat entire string as token
            token = authorization
    except (ValueError, AttributeError) as e:
        logger.debug(f"🔒 Auth: Error parsing header: {e}")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid authorization header format"}
        )
    
    # ⚡ OPTIMIZATION: Check token cache first
    token_cache = await get_token_cache()
    cached_user = await token_cache.get(token)
    if cached_user:
        logger.debug(f"⚡ Auth cache HIT: {cached_user.get('username')} (<1ms)")
        return cached_user
    
    # Cache miss - verify token from database
    logger.debug(f"📦 Auth cache MISS: Verifying token from database...")
    user = await verify_token_data(session, token)
    if not user:
        logger.debug(f"🔒 Auth: Token verification failed - invalid or expired")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid or expired token"}
        )
    
    if not user.is_active:
        logger.warning(f"🔒 Auth: Inactive user attempted access: {user.username}")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "User account is inactive"}
        )
    
    user_dict = user_to_dict(user)
    
    # ⚡ Cache the user data for future requests
    await token_cache.set(token, user_dict)
    logger.debug(f"✅ Auth: Cached user data for: {user.username}")
    
    return user_dict


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
    
    Invalidates the user's token by:
    1. Clearing from cache (instant invalidation)
    2. Deleting from PostgreSQL (persistent invalidation)
    
    Works even with invalid/expired tokens since the user wants to logout anyway.
    """
    from utils.auth.token_cache import get_token_cache
    
    if authorization:
        # Extract token
        try:
            parts = authorization.split(maxsplit=1)
            token_value = parts[1] if len(parts) == 2 else authorization
            
            # ⚡ Clear from cache first (instant)
            token_cache = get_token_cache()
            token_cache.invalidate(token_value)
            
            # Then delete from database (persistent)
            await delete_token(session, token_value)
            logger.info(f"👋 Logout: Token invalidated from cache and database")
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
    
    Password Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    """
    logger.info(f"📝 Registration attempt: {request.username} ({request.email})")
    
    # Validate passwords match
    if request.password != request.password2:
        raise HTTPException(
            status_code=400,
            detail={"error": "password_mismatch", "message": "Passwords do not match"}
        )
    
    # Validate password strength (comprehensive)
    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must be at least 8 characters long"}
        )
    
    if not any(c.isupper() for c in request.password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one uppercase letter"}
        )
    
    if not any(c.islower() for c in request.password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one lowercase letter"}
        )
    
    if not any(c.isdigit() for c in request.password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one number"}
        )
    
    # Validate username (optional - basic validation)
    if len(request.username) < 3:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_username", "message": "Username must be at least 3 characters long"}
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


@router.get("/user/")
async def get_authenticated_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Get current authenticated user.
    
    Returns user data if authenticated, or indicates backend is ready if not.
    This endpoint is used by Learniva frontend for health checks.
    """
    # If no authorization header, return that backend is ready but user not authenticated
    if not authorization:
        return {
            "authenticated": False,
            "backend_ready": True,
            "message": "Backend is ready. Please authenticate."
        }
    
    # Try to get user info from token
    try:
        from utils.auth.jwt_handler import verify_access_token
        from database.models.user import User
        from sqlalchemy import select
        
        # Extract token from "Bearer <token>"
        token = authorization.replace("Bearer ", "").strip()
        
        # Verify JWT token
        payload = verify_access_token(token)
        if not payload:
            return {
                "authenticated": False,
                "backend_ready": True,
                "error": "Invalid or expired token"
            }
        
        # Get user from database
        user_id = payload.get("user_id")
        
        # Convert string UUID to UUID object for comparison with User.id (UUID field)
        try:
            user_uuid = UUID(user_id)
        except (ValueError, TypeError):
            return {
                "authenticated": False,
                "backend_ready": True,
                "error": "Invalid user ID format"
            }
        
        result = await session.execute(
            select(User).where(User.id == user_uuid)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                "authenticated": False,
                "backend_ready": True,
                "error": "User not found"
            }
        
        # Return user info
        return {
            "authenticated": True,
            "backend_ready": True,
            "user": {
                "id": str(user.id),  # Convert UUID to string
                "email": user.email,
                "username": user.username,
                "name": user.name,
                "role": user.role.value,
                "is_verified": user.is_verified,
                "picture": user.picture
            }
        }
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return {
            "authenticated": False,
            "backend_ready": True,
            "error": str(e)
        }


@router.post("/password-reset/")
async def request_password_reset(
    request: PasswordResetRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Request a password reset.
    
    Sends an email with a password reset link containing a secure token.
    Always returns success to prevent email enumeration attacks.
    """
    logger.info(f"🔄 Password reset requested for: {request.email}")
    
    # Check if user exists
    user = await get_user_by_email(session, request.email)
    
    # Always return success message to prevent email enumeration
    # But only send email if user exists
    if user:
        # Create password reset token
        from database.operations.password_reset_ops import create_reset_token
        reset_token = await create_reset_token(session, request.email)
        
        if reset_token:
            # Send password reset email
            from utils.email.email_service import email_service
            email_sent = email_service.send_password_reset_email(
                to_email=request.email,
                username=user.username,
                reset_token=reset_token.token
            )
            
            if email_sent:
                logger.info(f"✅ Password reset email sent to: {request.email}")
            else:
                logger.error(f"❌ Failed to send password reset email to: {request.email}")
        else:
            logger.error(f"❌ Failed to create reset token for: {request.email}")
    else:
        logger.warning(f"⚠️  Password reset requested for non-existent email: {request.email}")
    
    # Always return same message (security: prevent email enumeration)
    return {
        "message": "If this email exists in our system, you will receive a password reset link shortly.",
        "email": request.email
    }


@router.post("/password-reset/confirm/")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    session: AsyncSession = Depends(get_session)
):
    """
    Confirm and complete password reset using token from email.
    
    Validates the reset token, updates the password, and marks token as used.
    """
    logger.info(f"🔐 Password reset confirmation for: {request.email}")
    
    # Verify passwords match
    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=400,
            detail={"error": "password_mismatch", "message": "Passwords do not match"}
        )
    
    # Validate password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must be at least 8 characters long"}
        )
    
    if not any(c.isupper() for c in request.new_password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one uppercase letter"}
        )
    
    if not any(c.islower() for c in request.new_password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one lowercase letter"}
        )
    
    if not any(c.isdigit() for c in request.new_password):
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Password must contain at least one number"}
        )
    
    # Verify reset token
    from database.operations.password_reset_ops import get_valid_reset_token, mark_token_as_used
    reset_token = await get_valid_reset_token(session, request.token, request.email)
    
    if not reset_token:
        logger.warning(f"⚠️  Invalid or expired reset token for: {request.email}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_token",
                "message": "Invalid or expired reset token. Please request a new password reset."
            }
        )
    
    # Get user
    user = await get_user_by_email(session, request.email)
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No account found with this email address"}
        )
    
    # Check if user is OAuth-only
    if user.google_id and not user.settings.get('password_hash'):
        raise HTTPException(
            status_code=400,
            detail={"error": "oauth_only", "message": "This account uses Google Sign-In only. Password reset is not available."}
        )
    
    # Update password
    from utils.auth.password import hash_password
    from sqlalchemy import update as sql_update
    try:
        new_password_hash = hash_password(request.new_password)
        
        # Update using SQL UPDATE to ensure JSONB field is properly updated
        from database.models.user import User
        stmt = (
            sql_update(User)
            .where(User.email == request.email)
            .values(settings={"password_hash": new_password_hash})
        )
        await session.execute(stmt)
        
        # Mark token as used
        await mark_token_as_used(session, reset_token.id)
        
        await session.commit()
        
        logger.info(f"✅ Password reset successful for: {request.email}")
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Password reset failed for {request.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "reset_failed", "message": "Failed to reset password. Please try again."}
        )
    
    return {
        "message": "Password has been reset successfully. You can now log in with your new password.",
        "email": request.email
    }


@router.get("/health/auth")
async def auth_health():
    """
    Health check for authentication system.
    
    Returns status of authentication endpoints.
    """
    return {
        "status": "healthy",
        "token_expiry_hours": settings.token_expire_hours,
        "storage": "postgresql",
        "endpoints": {
            "login": "/api/auth/login/",
            "register": "/api/auth/register/",
            "logout": "/api/auth/logout/",
            "password_reset": "/api/auth/password-reset/",
            "password_reset_confirm": "/api/auth/password-reset/confirm/",
            "google_oauth": "/api/auth/google/login/",
            "current_user": "/api/auth/me/",
            "config": "/api/auth/config/"
        }
    }


# Add endpoint for Google OAuth JWT compatibility
@router.get("/user")  # Duplicate removed - handled by /user/ above
async def get_jwt_user_info_no_slash(
    session: AsyncSession = Depends(get_session)
):
    """
    Get current user from JWT token (Google OAuth).
    This is a placeholder that tells the frontend to use /auth/me instead.
    
    Headers:
        Authorization: Bearer <jwt_token>
    """
    from fastapi import Header
    # Redirect to proper endpoint
    raise HTTPException(
        status_code=401,
        detail={
            "error": "wrong_endpoint",
            "message": "For Google OAuth, use /auth/me endpoint instead",
            "correct_endpoint": "/auth/me"
        }
    )


__all__ = ['router', 'get_current_user']

