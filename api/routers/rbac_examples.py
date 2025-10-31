"""
Example RBAC-Protected Routes

This module demonstrates how to use the RBAC system to protect API endpoints.
Use this as a reference for implementing RBAC in your own routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# Import RBAC dependencies
from middleware.rbac import (
    require_role,
    require_permission,
    require_any_permission,
    require_student,
    require_teacher,
    require_admin,
)
from utils.auth.permissions import Permission
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/rbac-examples", tags=["RBAC Examples"])


# ============================================================================
# Models
# ============================================================================

class UserInfo(BaseModel):
    """User information response."""
    user_id: str
    email: str
    role: str
    permissions: List[str]


class ContentItem(BaseModel):
    """Content item model."""
    id: str
    title: str
    content: str
    author: str


class GradeItem(BaseModel):
    """Grade item model."""
    id: str
    student_id: str
    assignment_id: str
    score: float
    feedback: str


# ============================================================================
# Example 1: Public Endpoint (No Authentication)
# ============================================================================

@router.get("/public")
async def public_endpoint():
    """
    Public endpoint - no authentication required.
    
    Anyone can access this endpoint.
    """
    return {
        "message": "This is a public endpoint",
        "authentication": "not required"
    }


# ============================================================================
# Example 2: Authenticated Endpoint (Any Role)
# ============================================================================

@router.get("/authenticated", response_model=UserInfo)
async def authenticated_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Authenticated endpoint - requires valid JWT token.
    
    Any authenticated user can access this, regardless of role.
    
    **Required:** Valid JWT token
    **Allowed Roles:** Any authenticated user
    """
    return UserInfo(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=current_user["role"],
        permissions=current_user.get("permissions", [])
    )


# ============================================================================
# Example 3: Student-Only Endpoint
# ============================================================================

@router.get("/student-only")
async def student_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_student)
):
    """
    Student endpoint - requires student role or higher.
    
    **Required:** Student, Teacher, or Admin role
    **Permissions:** Any student-level permission
    """
    return {
        "message": f"Welcome, {current_user['email']}!",
        "role": current_user["role"],
        "access_level": "student"
    }


# ============================================================================
# Example 4: Teacher-Only Endpoint
# ============================================================================

@router.get("/teacher-only")
async def teacher_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_teacher)
):
    """
    Teacher endpoint - requires teacher/professor/instructor or admin role.
    
    **Required:** Teacher, Professor, Instructor, or Admin role
    **Permissions:** Teacher-level permissions
    """
    return {
        "message": f"Welcome, {current_user['email']}!",
        "role": current_user["role"],
        "access_level": "teacher",
        "can_grade": True,
        "can_create_assignments": True
    }


# ============================================================================
# Example 5: Admin-Only Endpoint
# ============================================================================

@router.get("/admin-only")
async def admin_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Admin endpoint - requires admin role.
    
    **Required:** Admin role only
    **Permissions:** System administrator permissions
    """
    return {
        "message": f"Welcome, Admin {current_user['email']}!",
        "role": current_user["role"],
        "access_level": "admin",
        "system_access": True
    }


# ============================================================================
# Example 6: Multiple Roles Allowed
# ============================================================================

@router.get("/multi-role", dependencies=[Depends(require_role(["teacher", "admin"]))])
async def multi_role_endpoint():
    """
    Multi-role endpoint - requires teacher or admin role.
    
    **Required:** Teacher or Admin role
    
    Note: Using dependencies parameter instead of function parameter.
    """
    return {
        "message": "Accessible by teachers and admins",
        "allowed_roles": ["teacher", "admin"]
    }


# ============================================================================
# Example 7: Permission-Based (Grading)
# ============================================================================

@router.get("/grades")
async def list_grades(
    current_user: Dict[str, Any] = Depends(require_permission(Permission.GRADING_READ))
):
    """
    List grades - requires GRADING_READ permission.
    
    **Required Permission:** GRADING_READ
    **Allowed Roles:** Student (own grades), Teacher, Admin
    """
    # In real implementation, filter by user role
    # Students see only their grades, teachers see all
    return {
        "grades": [
            {"id": "1", "score": 95, "assignment": "Homework 1"},
            {"id": "2", "score": 88, "assignment": "Quiz 1"},
        ],
        "user": current_user["email"]
    }


@router.post("/grades")
async def create_grade(
    grade: GradeItem,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.GRADING_WRITE))
):
    """
    Create grade - requires GRADING_WRITE permission.
    
    **Required Permission:** GRADING_WRITE
    **Allowed Roles:** Teacher, Admin
    """
    return {
        "message": "Grade created successfully",
        "grade_id": grade.id,
        "created_by": current_user["email"]
    }


@router.delete("/grades/{grade_id}")
async def delete_grade(
    grade_id: str,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.GRADING_DELETE))
):
    """
    Delete grade - requires GRADING_DELETE permission.
    
    **Required Permission:** GRADING_DELETE
    **Allowed Roles:** Teacher, Admin
    """
    return {
        "message": f"Grade {grade_id} deleted successfully",
        "deleted_by": current_user["email"]
    }


# ============================================================================
# Example 8: Multiple Permissions Required (AND logic)
# ============================================================================

@router.post("/admin/grades")
async def admin_grade_operation(
    current_user: Dict[str, Any] = Depends(require_permission([
        Permission.GRADING_ADMIN,
        Permission.SYSTEM_CONFIG
    ]))
):
    """
    Admin grade operation - requires BOTH permissions.
    
    **Required Permissions:** GRADING_ADMIN AND SYSTEM_CONFIG
    **Allowed Roles:** Admin only
    """
    return {
        "message": "Admin grade operation completed",
        "permissions_verified": ["GRADING_ADMIN", "SYSTEM_CONFIG"]
    }


# ============================================================================
# Example 9: Any Permission Allowed (OR logic)
# ============================================================================

@router.get("/content")
async def view_content(
    current_user: Dict[str, Any] = Depends(require_any_permission([
        Permission.CONTENT_READ,
        Permission.CONTENT_ADMIN
    ]))
):
    """
    View content - requires EITHER permission.
    
    **Required Permissions:** CONTENT_READ OR CONTENT_ADMIN
    **Allowed Roles:** Student, Teacher, Admin
    """
    return {
        "content": [
            {"id": "1", "title": "Introduction", "type": "lesson"},
            {"id": "2", "title": "Chapter 1", "type": "lesson"},
        ],
        "viewer": current_user["email"]
    }


# ============================================================================
# Example 10: Manual Permission Check
# ============================================================================

@router.get("/flexible")
async def flexible_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Flexible endpoint with manual permission checking.
    
    Different responses based on user permissions.
    
    **Required:** Valid JWT token
    **Response varies by role**
    """
    from utils.auth.permissions import PermissionChecker
    
    checker = PermissionChecker(role=current_user["role"])
    
    # Different access levels
    if checker.has_permission(Permission.GRADING_ADMIN):
        access_level = "full_admin"
        data = {
            "all_grades": True,
            "can_modify": True,
            "can_delete": True,
            "statistics": True
        }
    elif checker.has_permission(Permission.GRADING_WRITE):
        access_level = "teacher"
        data = {
            "class_grades": True,
            "can_modify": True,
            "can_delete": False,
            "statistics": True
        }
    elif checker.has_permission(Permission.GRADING_READ):
        access_level = "student"
        data = {
            "own_grades": True,
            "can_modify": False,
            "can_delete": False,
            "statistics": False
        }
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "access_level": access_level,
        "user": current_user["email"],
        "data": data
    }


# ============================================================================
# Example 11: Document Upload (Permission-Based)
# ============================================================================

@router.post("/documents/upload")
async def upload_document(
    filename: str,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.DOCUMENT_UPLOAD))
):
    """
    Upload document - requires DOCUMENT_UPLOAD permission.
    
    **Required Permission:** DOCUMENT_UPLOAD
    **Allowed Roles:** Student, Teacher, Admin
    """
    return {
        "message": "Document uploaded successfully",
        "filename": filename,
        "uploaded_by": current_user["email"],
        "user_role": current_user["role"]
    }


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """
    Delete document - requires DOCUMENT_DELETE permission.
    
    **Required Permission:** DOCUMENT_DELETE
    **Allowed Roles:** Student (own docs), Teacher, Admin
    """
    return {
        "message": f"Document {doc_id} deleted successfully",
        "deleted_by": current_user["email"]
    }


# ============================================================================
# Example 12: System Configuration (Admin Only)
# ============================================================================

@router.put("/system/config")
async def update_system_config(
    config: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG))
):
    """
    Update system configuration - requires SYSTEM_CONFIG permission.
    
    **Required Permission:** SYSTEM_CONFIG
    **Allowed Roles:** Admin only
    """
    return {
        "message": "System configuration updated",
        "updated_by": current_user["email"],
        "config": config
    }


# ============================================================================
# Example 13: Analytics (Read Permission)
# ============================================================================

@router.get("/analytics")
async def view_analytics(
    current_user: Dict[str, Any] = Depends(require_any_permission([
        Permission.ANALYTICS_READ,
        Permission.SYSTEM_ADMIN
    ]))
):
    """
    View analytics - requires ANALYTICS_READ or SYSTEM_ADMIN permission.
    
    **Required Permissions:** ANALYTICS_READ OR SYSTEM_ADMIN
    **Allowed Roles:** Teacher, Admin
    """
    return {
        "analytics": {
            "total_students": 150,
            "total_assignments": 25,
            "average_grade": 85.5,
            "completion_rate": 92.3
        },
        "viewer": current_user["email"]
    }


# ============================================================================
# Example 14: User Management (Admin Permission)
# ============================================================================

@router.get("/users")
async def list_users(
    current_user: Dict[str, Any] = Depends(require_permission(Permission.USER_READ))
):
    """
    List users - requires USER_READ permission.
    
    **Required Permission:** USER_READ
    **Allowed Roles:** Student (self), Teacher (class), Admin (all)
    """
    from utils.auth.permissions import PermissionChecker
    
    checker = PermissionChecker(role=current_user["role"])
    
    # Filter based on permissions
    if checker.has_permission(Permission.USER_ADMIN):
        users = ["All users in system"]
    elif current_user["role"] == "teacher":
        users = ["Students in my classes"]
    else:
        users = [current_user["email"]]
    
    return {
        "users": users,
        "role": current_user["role"]
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_permission(Permission.USER_WRITE))
):
    """
    Update user - requires USER_WRITE permission.
    
    **Required Permission:** USER_WRITE
    **Allowed Roles:** Teacher (own profile), Admin (any user)
    """
    # In real implementation, check if user can update this specific user
    return {
        "message": f"User {user_id} updated",
        "updated_by": current_user["email"]
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.USER_DELETE))
):
    """
    Delete user - requires USER_DELETE permission.
    
    **Required Permission:** USER_DELETE
    **Allowed Roles:** Admin only
    """
    return {
        "message": f"User {user_id} deleted",
        "deleted_by": current_user["email"]
    }


# ============================================================================
# Example 15: Payment Operations
# ============================================================================

@router.get("/payments")
async def list_payments(
    current_user: Dict[str, Any] = Depends(require_permission(Permission.PAYMENT_READ))
):
    """
    List payments - requires PAYMENT_READ permission.
    
    **Required Permission:** PAYMENT_READ
    **Allowed Roles:** Student (own), Teacher (own), Admin (all)
    """
    return {
        "payments": [
            {"id": "1", "amount": 99.99, "status": "completed"},
        ],
        "user": current_user["email"]
    }


@router.post("/payments/refund/{payment_id}")
async def refund_payment(
    payment_id: str,
    current_user: Dict[str, Any] = Depends(require_permission(Permission.PAYMENT_ADMIN))
):
    """
    Refund payment - requires PAYMENT_ADMIN permission.
    
    **Required Permission:** PAYMENT_ADMIN
    **Allowed Roles:** Admin only
    """
    return {
        "message": f"Payment {payment_id} refunded",
        "refunded_by": current_user["email"]
    }


# ============================================================================
# Info Endpoint
# ============================================================================

@router.get("/info")
async def rbac_info():
    """
    Get information about the RBAC system.
    
    Returns available roles and their permissions.
    """
    from utils.auth.permissions import get_all_roles, get_permissions_for_role
    
    roles_info = {}
    for role in get_all_roles():
        perms = get_permissions_for_role(role.value)
        roles_info[role.value] = {
            "name": role.value,
            "permission_count": len(perms),
            "permissions": [p.value for p in perms]
        }
    
    return {
        "message": "RBAC System Information",
        "roles": roles_info,
        "documentation": "/docs/RBAC_GUIDE.md"
    }
