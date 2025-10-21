"""
API Dependencies.

FastAPI dependencies for authentication, database access, and common utilities.
"""

from typing import Optional, Generator
from fastapi import Header, HTTPException, Depends, status

from utils.monitoring import get_correlation_id, set_correlation_id
from config import settings

# Try to import database
try:
    from database.core.async_engine import get_async_db
    from sqlalchemy.ext.asyncio import AsyncSession
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    AsyncSession = None


# ============================================================================
# Correlation ID Dependency
# ============================================================================

async def get_or_create_correlation_id(
    x_correlation_id: Optional[str] = Header(None)
) -> str:
    """
    Get or create correlation ID from request header.
    
    Args:
        x_correlation_id: Correlation ID from X-Correlation-ID header
        
    Returns:
        Correlation ID
    """
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
        return x_correlation_id
    return get_correlation_id()


# ============================================================================
# User Role Dependencies (JWT-Based - SECURE)
# ============================================================================

async def get_current_user_role(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Get user role from JWT token (SECURE).
    
    SECURITY NOTE: This function extracts the role from the JWT token,
    NOT from headers. This prevents role escalation attacks.
    
    Args:
        authorization: Authorization header with JWT token
        
    Returns:
        User role from JWT token
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    from utils.auth import get_current_user
    
    # Get authenticated user from JWT token
    user = await get_current_user(authorization)
    
    # Extract role from JWT token payload
    role = user.role.lower() if hasattr(user, 'role') else "student"
    
    valid_roles = ["student", "teacher", "professor", "instructor", "admin"]
    if role not in valid_roles:
        role = "student"  # Fallback to student for invalid roles
    
    return role


async def require_teacher_role(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Require teacher or admin role (JWT-based authentication).
    
    Args:
        authorization: Authorization header with JWT token
        
    Returns:
        User role from JWT
        
    Raises:
        HTTPException: If user is not teacher or admin
    """
    role = await get_current_user_role(authorization)
    
    if role not in ["teacher", "professor", "instructor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires teacher/professor or admin privileges"
        )
    return role


async def require_admin_role(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Require admin role (JWT-based authentication).
    
    Args:
        authorization: Authorization header with JWT token
        
    Returns:
        User role from JWT
        
    Raises:
        HTTPException: If user is not admin
    """
    role = await get_current_user_role(authorization)
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin privileges"
        )
    return role


# ============================================================================
# Database Dependencies
# ============================================================================

async def get_db() -> AsyncSession:
    """
    Get database session.
    
    Yields:
        Database session
        
    Raises:
        HTTPException: If database is not available
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available"
        )
    
    async for session in get_async_db():
        yield session


async def get_optional_db() -> Optional[AsyncSession]:
    """
    Get optional database session.
    
    Returns None if database is not available instead of raising error.
    
    Yields:
        Database session or None
    """
    if not DATABASE_AVAILABLE:
        yield None
        return
    
    async for session in get_async_db():
        yield session


# ============================================================================
# User ID Dependencies
# ============================================================================

async def get_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Optional[str]:
    """
    Get user ID from header.
    
    Args:
        x_user_id: User ID from X-User-ID header
        
    Returns:
        User ID or None
    """
    return x_user_id


async def require_user_id(
    user_id: Optional[str] = Depends(get_user_id)
) -> str:
    """
    Require user ID to be present.
    
    Args:
        user_id: User ID from dependency
        
    Returns:
        User ID
        
    Raises:
        HTTPException: If user ID is not provided
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID is required. Provide X-User-ID header"
        )
    return user_id


# ============================================================================
# Agent Dependencies
# ============================================================================

class AgentDependency:
    """Dependency for accessing global supervisor agent."""
    
    def __init__(self):
        self.supervisor = None
    
    def set_supervisor(self, supervisor):
        """Set supervisor agent instance."""
        self.supervisor = supervisor
    
    async def __call__(self):
        """Get supervisor agent instance."""
        if self.supervisor is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supervisor agent is not initialized"
            )
        return self.supervisor


# Global agent dependency instance
get_supervisor = AgentDependency()


# ============================================================================
# Pagination Dependencies
# ============================================================================

async def pagination_params(
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100
) -> dict:
    """
    Get pagination parameters.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size
        
    Returns:
        Pagination parameters dict
        
    Raises:
        HTTPException: If parameters are invalid
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1"
        )
    
    if page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be >= 1"
        )
    
    if page_size > max_page_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page size must be <= {max_page_size}"
        )
    
    return {
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size
    }

