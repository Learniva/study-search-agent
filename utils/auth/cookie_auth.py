"""
Cookie-Based Authentication Dependencies.

Provides FastAPI dependency functions to extract and validate
authentication tokens from httpOnly cookies instead of Authorization headers.

This module supports:
- Cookie-based authentication (primary)
- Header-based authentication (fallback for backward compatibility)
- Token validation and user extraction
- Role-based access control
"""

import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from utils.auth.cookie_config import CookieConfig
from utils.auth.jwt_handler import verify_access_token
from utils.auth.token_cache import get_token_cache
from database.core.async_connection import get_session
from database.operations.token_ops import get_token
from database.operations.user_ops import get_user_by_email

logger = logging.getLogger(__name__)


async def get_current_user_from_cookie(
    request: Request,
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Get current authenticated user from cookie or Authorization header.
    
    Priority:
    1. Cookie-based token (preferred)
    2. Authorization header (backward compatibility)
    
    This dependency supports both authentication methods during migration.
    Once all clients migrate to cookies, header support can be removed.
    
    Args:
        request: FastAPI Request object
        authorization: Optional Authorization header (backward compatibility)
        session: Database session
        
    Returns:
        User data dictionary
        
    Raises:
        HTTPException: If authentication fails
    """
    # Try to get token from cookie or header
    token = CookieConfig.get_token_from_cookie_or_header(request, authorization)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check token cache first
    token_cache = await get_token_cache()
    cached_user = await token_cache.get(token)
    if cached_user:
        return cached_user
    
    # Try database token first (custom auth)
    try:
        token_data = await get_token(session, token)
        if token_data:
            # Get user info from database
            user = await session.get(token_data.__class__.__bases__[0], token_data.user_id)
            if user and user.is_active:
                user_dict = {
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                    "last_active": user.last_active.isoformat() if user.last_active else None,
                    "auth_type": "database"
                }
                await token_cache.set(token, user_dict)
                return user_dict
    except Exception as e:
        logger.debug(f"Database token validation failed: {e}")
    
    # Try JWT token (OAuth)
    try:
        payload = verify_access_token(token)
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing email"
            )
        
        # Get user from database
        user = await get_user_by_email(session, email)
        if not user:
            # Auto-create user from JWT data (OAuth user)
            from database.operations.user_ops import create_user
            user = await create_user(
                session=session,
                email=email,
                username=email.split("@")[0],
                name=payload.get("name"),
                google_id=payload.get("sub"),
                picture=payload.get("picture"),
                is_verified=True
            )
        
        if user and user.is_active:
            user_dict = {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "auth_type": "jwt"
            }
            await token_cache.set(token, user_dict)
            return user_dict
    except Exception as e:
        logger.debug(f"JWT token validation failed: {e}")
    
    # Both methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token"
    )


async def get_optional_user_from_cookie(
    request: Request,
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, otherwise return None.
    
    This is useful for endpoints that have optional authentication.
    
    Args:
        request: FastAPI Request object
        authorization: Optional Authorization header
        session: Database session
        
    Returns:
        User data or None
    """
    try:
        return await get_current_user_from_cookie(request, authorization, session)
    except HTTPException:
        return None


async def require_authenticated_user(
    user: Dict[str, Any] = Depends(get_current_user_from_cookie)
) -> Dict[str, Any]:
    """
    Require authenticated user (any role).
    
    Args:
        user: User from cookie authentication
        
    Returns:
        User data
        
    Raises:
        HTTPException: If user is not authenticated
    """
    return user


async def require_teacher_role_from_cookie(
    user: Dict[str, Any] = Depends(get_current_user_from_cookie)
) -> Dict[str, Any]:
    """
    Require teacher or admin role (cookie-based authentication).
    
    Args:
        user: User from cookie authentication
        
    Returns:
        User data
        
    Raises:
        HTTPException: If user is not teacher or admin
    """
    role = user.get("role", "").lower()
    
    if role not in ["teacher", "professor", "instructor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires teacher/professor or admin privileges"
        )
    
    return user


async def require_admin_role_from_cookie(
    user: Dict[str, Any] = Depends(get_current_user_from_cookie)
) -> Dict[str, Any]:
    """
    Require admin role (cookie-based authentication).
    
    Args:
        user: User from cookie authentication
        
    Returns:
        User data
        
    Raises:
        HTTPException: If user is not admin
    """
    role = user.get("role", "").lower()
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin privileges"
        )
    
    return user


__all__ = [
    "get_current_user_from_cookie",
    "get_optional_user_from_cookie",
    "require_authenticated_user",
    "require_teacher_role_from_cookie",
    "require_admin_role_from_cookie",
]
