"""
RBAC Middleware

Middleware for role-based access control enforcement at the route level.
Provides decorators and dependencies for protecting routes with role and permission checks.
"""

from typing import List, Optional, Callable, Union
from functools import wraps
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.auth.permissions import Permission, PermissionChecker
from utils.auth.jwt_handler import verify_access_token
from utils.monitoring import get_logger

logger = get_logger(__name__)
security = HTTPBearer()


# ============================================================================
# Token Extraction and User Info
# ============================================================================

async def get_current_user_from_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Extract and verify user information from JWT token.
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        
    Returns:
        User data from token including role and permissions
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        # Verify and decode token
        payload = verify_access_token(token)
        
        # Extract user info
        user_id = payload.get("user_id")
        email = payload.get("email")
        role = payload.get("role", "student").lower()
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Build user object
        user_data = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "name": payload.get("name"),
            "permissions": list(PermissionChecker(role=role).get_permissions()),
        }
        
        logger.debug(f"Authenticated user: {user_id} with role: {role}")
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# Role-Based Dependencies
# ============================================================================

def require_role(allowed_roles: Union[str, List[str]]):
    """
    Dependency factory for requiring specific roles.
    
    Args:
        allowed_roles: Single role or list of allowed roles
        
    Returns:
        Dependency function
        
    Example:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint():
            return {"message": "Admin access granted"}
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    
    # Normalize roles
    normalized_roles = [role.lower() for role in allowed_roles]
    
    async def role_checker(
        current_user: dict = Depends(get_current_user_from_token)
    ) -> dict:
        """Check if user has required role."""
        user_role = current_user.get("role", "").lower()
        
        # Normalize professor/instructor to teacher
        if user_role in ["professor", "instructor"]:
            user_role = "teacher"
        
        # Check if user has any of the allowed roles
        checker = PermissionChecker(role=user_role)
        if not checker.has_any_role(normalized_roles):
            logger.warning(
                f"Access denied: User {current_user.get('user_id')} with role "
                f"'{user_role}' attempted to access endpoint requiring roles: {normalized_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of the following roles: {', '.join(normalized_roles)}"
            )
        
        logger.debug(f"Role check passed for user {current_user.get('user_id')}")
        return current_user
    
    return role_checker


def require_permission(required_permissions: Union[Permission, List[Permission]]):
    """
    Dependency factory for requiring specific permissions.
    
    Args:
        required_permissions: Single permission or list of required permissions
        
    Returns:
        Dependency function
        
    Example:
        @router.post("/grade", dependencies=[Depends(require_permission(Permission.GRADING_WRITE))])
        async def create_grade():
            return {"message": "Grade created"}
    """
    if isinstance(required_permissions, Permission):
        required_permissions = [required_permissions]
    
    async def permission_checker(
        current_user: dict = Depends(get_current_user_from_token)
    ) -> dict:
        """Check if user has required permissions."""
        user_role = current_user.get("role", "student")
        checker = PermissionChecker(role=user_role)
        
        if not checker.has_all_permissions(required_permissions):
            logger.warning(
                f"Access denied: User {current_user.get('user_id')} with role "
                f"'{user_role}' lacks required permissions: {required_permissions}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {', '.join([p.value for p in required_permissions])}"
            )
        
        logger.debug(f"Permission check passed for user {current_user.get('user_id')}")
        return current_user
    
    return permission_checker


def require_any_permission(required_permissions: List[Permission]):
    """
    Dependency factory for requiring at least one of the specified permissions.
    
    Args:
        required_permissions: List of permissions (user needs at least one)
        
    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: dict = Depends(get_current_user_from_token)
    ) -> dict:
        """Check if user has at least one required permission."""
        user_role = current_user.get("role", "student")
        checker = PermissionChecker(role=user_role)
        
        if not checker.has_any_permission(required_permissions):
            logger.warning(
                f"Access denied: User {current_user.get('user_id')} with role "
                f"'{user_role}' lacks any of required permissions: {required_permissions}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required at least one of: {', '.join([p.value for p in required_permissions])}"
            )
        
        logger.debug(f"Permission check passed for user {current_user.get('user_id')}")
        return current_user
    
    return permission_checker


# ============================================================================
# Convenience Dependencies (Backward Compatible)
# ============================================================================

async def require_student(
    current_user: dict = Depends(require_role(["student", "teacher", "admin"]))
) -> dict:
    """
    Require student role or higher.
    
    Returns:
        Current user data
    """
    return current_user


async def require_teacher(
    current_user: dict = Depends(require_role(["teacher", "professor", "instructor", "admin"]))
) -> dict:
    """
    Require teacher role or higher.
    
    Returns:
        Current user data
    """
    return current_user


async def require_admin(
    current_user: dict = Depends(require_role("admin"))
) -> dict:
    """
    Require admin role.
    
    Returns:
        Current user data
    """
    return current_user


# ============================================================================
# Route Decorators (Alternative to Dependencies)
# ============================================================================

def protected_route(
    roles: Optional[List[str]] = None,
    permissions: Optional[List[Permission]] = None,
    require_all_permissions: bool = True
):
    """
    Decorator for protecting routes with role and/or permission checks.
    
    Args:
        roles: List of allowed roles
        permissions: List of required permissions
        require_all_permissions: If True, user needs all permissions. If False, needs at least one.
        
    Example:
        @router.get("/protected")
        @protected_route(roles=["admin"], permissions=[Permission.SYSTEM_ADMIN])
        async def protected_endpoint(current_user: dict):
            return {"message": "Access granted"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs (should be injected by dependency)
            current_user = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_role = current_user.get("role", "student")
            checker = PermissionChecker(role=user_role)
            
            # Check roles if specified
            if roles and not checker.has_any_role(roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join(roles)}"
                )
            
            # Check permissions if specified
            if permissions:
                if require_all_permissions:
                    if not checker.has_all_permissions(permissions):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Required permissions: {', '.join([p.value for p in permissions])}"
                        )
                else:
                    if not checker.has_any_permission(permissions):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Required at least one permission: {', '.join([p.value for p in permissions])}"
                        )
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# Utility Functions
# ============================================================================

async def get_current_user_role(
    current_user: dict = Depends(get_current_user_from_token)
) -> str:
    """
    Get the current user's role.
    
    Args:
        current_user: Current user data from token
        
    Returns:
        User role
    """
    return current_user.get("role", "student")


async def get_current_user_permissions(
    current_user: dict = Depends(get_current_user_from_token)
) -> List[str]:
    """
    Get the current user's permissions.
    
    Args:
        current_user: Current user data from token
        
    Returns:
        List of permission strings
    """
    return current_user.get("permissions", [])


def check_user_permission(user_role: str, permission: Permission) -> bool:
    """
    Check if a user role has a specific permission.
    
    Args:
        user_role: User's role
        permission: Permission to check
        
    Returns:
        True if user has permission
    """
    checker = PermissionChecker(role=user_role)
    return checker.has_permission(permission)
