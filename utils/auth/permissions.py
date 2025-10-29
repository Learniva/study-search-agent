"""
RBAC Permissions System

Defines roles, permissions, and permission checking logic for the application.
This module provides a flexible and extensible permission system.
"""

from enum import Enum
from typing import Set, Dict, List, Optional
from dataclasses import dataclass


# ============================================================================
# Permission Definitions
# ============================================================================

class Permission(str, Enum):
    """Application permissions."""
    
    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_ADMIN = "user:admin"
    
    # Content permissions
    CONTENT_READ = "content:read"
    CONTENT_WRITE = "content:write"
    CONTENT_DELETE = "content:delete"
    CONTENT_ADMIN = "content:admin"
    
    # Grading permissions
    GRADING_READ = "grading:read"
    GRADING_WRITE = "grading:write"
    GRADING_DELETE = "grading:delete"
    GRADING_ADMIN = "grading:admin"
    
    # Assignment permissions
    ASSIGNMENT_READ = "assignment:read"
    ASSIGNMENT_WRITE = "assignment:write"
    ASSIGNMENT_DELETE = "assignment:delete"
    ASSIGNMENT_ADMIN = "assignment:admin"
    
    # Query/Search permissions
    QUERY_EXECUTE = "query:execute"
    QUERY_HISTORY = "query:history"
    QUERY_ADMIN = "query:admin"
    
    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_ADMIN = "document:admin"
    
    # Payment/Billing permissions
    PAYMENT_READ = "payment:read"
    PAYMENT_WRITE = "payment:write"
    PAYMENT_ADMIN = "payment:admin"
    
    # Integration permissions
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"
    INTEGRATION_DELETE = "integration:delete"
    INTEGRATION_ADMIN = "integration:admin"
    
    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_WRITE = "analytics:write"
    
    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_ADMIN = "system:admin"


# ============================================================================
# Role Definitions
# ============================================================================

class Role(str, Enum):
    """User roles with hierarchical structure."""
    STUDENT = "student"
    TEACHER = "teacher"
    PROFESSOR = "professor"  # Alias for teacher
    INSTRUCTOR = "instructor"  # Alias for teacher
    ADMIN = "admin"


# ============================================================================
# Role-Permission Mapping
# ============================================================================

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.STUDENT: {
        # Students can read their own data
        Permission.USER_READ,
        Permission.CONTENT_READ,
        
        # Students can execute queries and view history
        Permission.QUERY_EXECUTE,
        Permission.QUERY_HISTORY,
        
        # Students can view assignments and grades
        Permission.ASSIGNMENT_READ,
        Permission.GRADING_READ,
        
        # Students can manage their documents
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_DELETE,
        
        # Students can view payment info
        Permission.PAYMENT_READ,
        
        # Students can view integrations
        Permission.INTEGRATION_READ,
    },
    
    Role.TEACHER: {
        # Teachers inherit all student permissions
        Permission.USER_READ,
        Permission.USER_WRITE,  # Can update their profile
        Permission.CONTENT_READ,
        Permission.CONTENT_WRITE,  # Can create content
        
        # Teachers can execute queries
        Permission.QUERY_EXECUTE,
        Permission.QUERY_HISTORY,
        
        # Teachers have full grading permissions
        Permission.GRADING_READ,
        Permission.GRADING_WRITE,
        Permission.GRADING_DELETE,
        Permission.GRADING_ADMIN,
        
        # Teachers have full assignment permissions
        Permission.ASSIGNMENT_READ,
        Permission.ASSIGNMENT_WRITE,
        Permission.ASSIGNMENT_DELETE,
        Permission.ASSIGNMENT_ADMIN,
        
        # Teachers can manage documents
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_ADMIN,
        
        # Teachers can view analytics
        Permission.ANALYTICS_READ,
        
        # Teachers can view payment info
        Permission.PAYMENT_READ,
        
        # Teachers can manage integrations
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_WRITE,
        Permission.INTEGRATION_DELETE,
    },
    
    Role.ADMIN: {
        # Admins have all permissions
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        Permission.USER_ADMIN,
        
        Permission.CONTENT_READ,
        Permission.CONTENT_WRITE,
        Permission.CONTENT_DELETE,
        Permission.CONTENT_ADMIN,
        
        Permission.GRADING_READ,
        Permission.GRADING_WRITE,
        Permission.GRADING_DELETE,
        Permission.GRADING_ADMIN,
        
        Permission.ASSIGNMENT_READ,
        Permission.ASSIGNMENT_WRITE,
        Permission.ASSIGNMENT_DELETE,
        Permission.ASSIGNMENT_ADMIN,
        
        Permission.QUERY_EXECUTE,
        Permission.QUERY_HISTORY,
        Permission.QUERY_ADMIN,
        
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_ADMIN,
        
        Permission.PAYMENT_READ,
        Permission.PAYMENT_WRITE,
        Permission.PAYMENT_ADMIN,
        
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_WRITE,
        Permission.INTEGRATION_DELETE,
        Permission.INTEGRATION_ADMIN,
        
        Permission.ANALYTICS_READ,
        Permission.ANALYTICS_WRITE,
        
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_ADMIN,
    },
}

# Add aliases for professor and instructor (same as teacher)
ROLE_PERMISSIONS[Role.PROFESSOR] = ROLE_PERMISSIONS[Role.TEACHER]
ROLE_PERMISSIONS[Role.INSTRUCTOR] = ROLE_PERMISSIONS[Role.TEACHER]


# ============================================================================
# Permission Checker
# ============================================================================

@dataclass
class PermissionChecker:
    """Helper class to check permissions for a user."""
    
    role: str
    custom_permissions: Optional[Set[Permission]] = None
    
    def __post_init__(self):
        """Normalize role after initialization."""
        self.role = self.role.lower()
        
        # Normalize professor/instructor to teacher
        if self.role in ["professor", "instructor"]:
            self.role = "teacher"
    
    def get_permissions(self) -> Set[Permission]:
        """
        Get all permissions for the user.
        
        Returns:
            Set of permissions
        """
        try:
            role_enum = Role(self.role)
            base_permissions = ROLE_PERMISSIONS.get(role_enum, set())
        except ValueError:
            # Invalid role, return empty set
            base_permissions = set()
        
        # Merge with custom permissions if provided
        if self.custom_permissions:
            return base_permissions | self.custom_permissions
        
        return base_permissions
    
    def has_permission(self, permission: Permission) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            permission: Permission to check
            
        Returns:
            True if user has permission, False otherwise
        """
        return permission in self.get_permissions()
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """
        Check if user has any of the specified permissions.
        
        Args:
            permissions: List of permissions to check
            
        Returns:
            True if user has at least one permission
        """
        user_permissions = self.get_permissions()
        return any(perm in user_permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """
        Check if user has all of the specified permissions.
        
        Args:
            permissions: List of permissions to check
            
        Returns:
            True if user has all permissions
        """
        user_permissions = self.get_permissions()
        return all(perm in user_permissions for perm in permissions)
    
    def has_role(self, role: str) -> bool:
        """
        Check if user has a specific role.
        
        Args:
            role: Role to check
            
        Returns:
            True if user has role
        """
        normalized_role = role.lower()
        if normalized_role in ["professor", "instructor"]:
            normalized_role = "teacher"
        return self.role == normalized_role
    
    def has_any_role(self, roles: List[str]) -> bool:
        """
        Check if user has any of the specified roles.
        
        Args:
            roles: List of roles to check
            
        Returns:
            True if user has at least one role
        """
        return any(self.has_role(role) for role in roles)


# ============================================================================
# Utility Functions
# ============================================================================

def get_permissions_for_role(role: str) -> Set[Permission]:
    """
    Get all permissions for a given role.
    
    Args:
        role: Role name
        
    Returns:
        Set of permissions for the role
    """
    try:
        role_enum = Role(role.lower())
        return ROLE_PERMISSIONS.get(role_enum, set())
    except ValueError:
        return set()


def check_permission(role: str, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.
    
    Args:
        role: Role name
        permission: Permission to check
        
    Returns:
        True if role has permission
    """
    checker = PermissionChecker(role=role)
    return checker.has_permission(permission)


def get_all_permissions() -> List[Permission]:
    """
    Get all available permissions.
    
    Returns:
        List of all permissions
    """
    return list(Permission)


def get_all_roles() -> List[Role]:
    """
    Get all available roles.
    
    Returns:
        List of all roles
    """
    return list(Role)
