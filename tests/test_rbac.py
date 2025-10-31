"""
RBAC System Tests

Tests for role-based access control implementation including:
- Permission checking
- Role validation
- JWT token validation with roles
- Middleware enforcement
"""

import pytest
from datetime import timedelta
from fastapi import HTTPException
from utils.auth.permissions import (
    Permission,
    Role,
    PermissionChecker,
    get_permissions_for_role,
    check_permission,
)
from utils.auth import create_access_token
from middleware.rbac import check_user_permission


class TestPermissions:
    """Test permission definitions and mappings."""
    
    def test_role_enum_values(self):
        """Test role enum has correct values."""
        assert Role.STUDENT.value == "student"
        assert Role.TEACHER.value == "teacher"
        assert Role.ADMIN.value == "admin"
    
    def test_student_permissions(self):
        """Test student has basic permissions."""
        perms = get_permissions_for_role("student")
        
        # Students should have read permissions
        assert Permission.USER_READ in perms
        assert Permission.CONTENT_READ in perms
        assert Permission.ASSIGNMENT_READ in perms
        assert Permission.GRADING_READ in perms
        assert Permission.QUERY_EXECUTE in perms
        
        # Students should NOT have write permissions
        assert Permission.GRADING_WRITE not in perms
        assert Permission.ASSIGNMENT_WRITE not in perms
        assert Permission.SYSTEM_ADMIN not in perms
    
    def test_teacher_permissions(self):
        """Test teacher has extended permissions."""
        perms = get_permissions_for_role("teacher")
        
        # Teachers should have grading permissions
        assert Permission.GRADING_READ in perms
        assert Permission.GRADING_WRITE in perms
        assert Permission.GRADING_DELETE in perms
        assert Permission.GRADING_ADMIN in perms
        
        # Teachers should have assignment permissions
        assert Permission.ASSIGNMENT_READ in perms
        assert Permission.ASSIGNMENT_WRITE in perms
        assert Permission.ASSIGNMENT_DELETE in perms
        
        # Teachers should NOT have system admin
        assert Permission.SYSTEM_ADMIN not in perms
    
    def test_admin_permissions(self):
        """Test admin has all permissions."""
        perms = get_permissions_for_role("admin")
        
        # Admin should have everything
        assert Permission.USER_ADMIN in perms
        assert Permission.GRADING_ADMIN in perms
        assert Permission.SYSTEM_ADMIN in perms
        assert Permission.PAYMENT_ADMIN in perms
        
        # Verify admin has significantly more permissions than student
        student_perms = get_permissions_for_role("student")
        assert len(perms) > len(student_perms)
    
    def test_professor_alias(self):
        """Test professor role is alias for teacher."""
        teacher_perms = get_permissions_for_role("teacher")
        professor_perms = get_permissions_for_role("professor")
        
        assert teacher_perms == professor_perms
    
    def test_instructor_alias(self):
        """Test instructor role is alias for teacher."""
        teacher_perms = get_permissions_for_role("teacher")
        instructor_perms = get_permissions_for_role("instructor")
        
        assert teacher_perms == instructor_perms


class TestPermissionChecker:
    """Test PermissionChecker utility class."""
    
    def test_student_checker(self):
        """Test permission checker for student role."""
        checker = PermissionChecker(role="student")
        
        assert checker.has_permission(Permission.CONTENT_READ)
        assert not checker.has_permission(Permission.GRADING_WRITE)
        assert checker.has_role("student")
        assert not checker.has_role("admin")
    
    def test_teacher_checker(self):
        """Test permission checker for teacher role."""
        checker = PermissionChecker(role="teacher")
        
        assert checker.has_permission(Permission.GRADING_WRITE)
        assert checker.has_permission(Permission.CONTENT_READ)
        assert checker.has_role("teacher")
        assert checker.has_any_role(["teacher", "admin"])
    
    def test_admin_checker(self):
        """Test permission checker for admin role."""
        checker = PermissionChecker(role="admin")
        
        assert checker.has_permission(Permission.SYSTEM_ADMIN)
        assert checker.has_permission(Permission.GRADING_WRITE)
        assert checker.has_role("admin")
    
    def test_has_any_permission(self):
        """Test checking for any of multiple permissions."""
        checker = PermissionChecker(role="student")
        
        # Student should have at least one of these
        assert checker.has_any_permission([
            Permission.CONTENT_READ,
            Permission.GRADING_ADMIN
        ])
        
        # Student should have none of these
        assert not checker.has_any_permission([
            Permission.SYSTEM_ADMIN,
            Permission.GRADING_ADMIN
        ])
    
    def test_has_all_permissions(self):
        """Test checking for all of multiple permissions."""
        teacher_checker = PermissionChecker(role="teacher")
        
        # Teacher should have all grading permissions
        assert teacher_checker.has_all_permissions([
            Permission.GRADING_READ,
            Permission.GRADING_WRITE,
            Permission.GRADING_DELETE
        ])
        
        # But not all admin permissions
        assert not teacher_checker.has_all_permissions([
            Permission.GRADING_ADMIN,
            Permission.SYSTEM_ADMIN
        ])
    
    def test_role_normalization(self):
        """Test role normalization (professor/instructor -> teacher)."""
        prof_checker = PermissionChecker(role="professor")
        inst_checker = PermissionChecker(role="instructor")
        teacher_checker = PermissionChecker(role="teacher")
        
        # All should have same permissions
        assert prof_checker.get_permissions() == teacher_checker.get_permissions()
        assert inst_checker.get_permissions() == teacher_checker.get_permissions()
    
    def test_invalid_role(self):
        """Test handling of invalid role."""
        checker = PermissionChecker(role="invalid_role")
        
        # Should have empty permissions
        assert len(checker.get_permissions()) == 0
        assert not checker.has_permission(Permission.CONTENT_READ)


class TestJWTTokenWithRoles:
    """Test JWT token creation and validation with role claims."""
    
    def test_create_token_with_role(self):
        """Test creating JWT token with role claim."""
        token_data = {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "role": "teacher",
            "name": "Test Teacher"
        }
        
        token = create_access_token(token_data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_token_contains_role(self):
        """Test that decoded token contains role."""
        from utils.auth import verify_access_token
        
        token_data = {
            "user_id": "test-user-456",
            "email": "student@example.com",
            "role": "student",
            "name": "Test Student"
        }
        
        token = create_access_token(token_data)
        decoded = verify_access_token(token)
        
        assert decoded["role"] == "student"
        assert decoded["user_id"] == "test-user-456"
        assert decoded["email"] == "student@example.com"
    
    def test_admin_token(self):
        """Test admin token creation."""
        from utils.auth import verify_access_token
        
        token_data = {
            "user_id": "admin-789",
            "email": "admin@example.com",
            "role": "admin",
            "name": "Test Admin"
        }
        
        token = create_access_token(token_data)
        decoded = verify_access_token(token)
        
        assert decoded["role"] == "admin"
        
        # Verify admin has system permissions
        assert check_user_permission(decoded["role"], Permission.SYSTEM_ADMIN)
    
    def test_token_expiration(self):
        """Test token with custom expiration."""
        token_data = {
            "user_id": "test-user",
            "email": "test@example.com",
            "role": "student"
        }
        
        # Create token with 1 hour expiration
        token = create_access_token(token_data, expires_delta=timedelta(hours=1))
        assert token is not None
    
    def test_multiple_role_tokens(self):
        """Test creating tokens for different roles."""
        from utils.auth import verify_access_token
        
        roles = ["student", "teacher", "admin"]
        tokens = {}
        
        for role in roles:
            token_data = {
                "user_id": f"{role}-user",
                "email": f"{role}@example.com",
                "role": role
            }
            tokens[role] = create_access_token(token_data)
        
        # Verify each token has correct role
        for role, token in tokens.items():
            decoded = verify_access_token(token)
            assert decoded["role"] == role


class TestCheckPermission:
    """Test the check_permission utility function."""
    
    def test_student_grading_read(self):
        """Test student can read grades."""
        assert check_permission("student", Permission.GRADING_READ)
    
    def test_student_grading_write(self):
        """Test student cannot write grades."""
        assert not check_permission("student", Permission.GRADING_WRITE)
    
    def test_teacher_grading_write(self):
        """Test teacher can write grades."""
        assert check_permission("teacher", Permission.GRADING_WRITE)
    
    def test_admin_all_permissions(self):
        """Test admin has all permissions."""
        assert check_permission("admin", Permission.SYSTEM_ADMIN)
        assert check_permission("admin", Permission.GRADING_ADMIN)
        assert check_permission("admin", Permission.USER_ADMIN)
    
    def test_case_insensitive_role(self):
        """Test role checking is case-insensitive."""
        assert check_permission("STUDENT", Permission.CONTENT_READ)
        assert check_permission("Teacher", Permission.GRADING_WRITE)
        assert check_permission("ADMIN", Permission.SYSTEM_ADMIN)


class TestRBACIntegration:
    """Integration tests for RBAC system."""
    
    def test_student_workflow(self):
        """Test complete student workflow."""
        # Create student token
        token_data = {
            "user_id": "student-001",
            "email": "student@school.com",
            "role": "student",
            "name": "John Student"
        }
        token = create_access_token(token_data)
        
        # Verify token
        from utils.auth import verify_access_token
        decoded = verify_access_token(token)
        
        # Check permissions
        checker = PermissionChecker(role=decoded["role"])
        
        # Student can read
        assert checker.has_permission(Permission.CONTENT_READ)
        assert checker.has_permission(Permission.ASSIGNMENT_READ)
        
        # Student cannot write
        assert not checker.has_permission(Permission.GRADING_WRITE)
        assert not checker.has_permission(Permission.ASSIGNMENT_WRITE)
    
    def test_teacher_workflow(self):
        """Test complete teacher workflow."""
        # Create teacher token
        token_data = {
            "user_id": "teacher-001",
            "email": "teacher@school.com",
            "role": "teacher",
            "name": "Jane Teacher"
        }
        token = create_access_token(token_data)
        
        # Verify token
        from utils.auth import verify_access_token
        decoded = verify_access_token(token)
        
        # Check permissions
        checker = PermissionChecker(role=decoded["role"])
        
        # Teacher can read and write
        assert checker.has_permission(Permission.GRADING_READ)
        assert checker.has_permission(Permission.GRADING_WRITE)
        assert checker.has_permission(Permission.ASSIGNMENT_WRITE)
        
        # Teacher cannot perform system admin
        assert not checker.has_permission(Permission.SYSTEM_ADMIN)
    
    def test_admin_workflow(self):
        """Test complete admin workflow."""
        # Create admin token
        token_data = {
            "user_id": "admin-001",
            "email": "admin@school.com",
            "role": "admin",
            "name": "Admin User"
        }
        token = create_access_token(token_data)
        
        # Verify token
        from utils.auth import verify_access_token
        decoded = verify_access_token(token)
        
        # Check permissions
        checker = PermissionChecker(role=decoded["role"])
        
        # Admin can do everything
        assert checker.has_permission(Permission.SYSTEM_ADMIN)
        assert checker.has_permission(Permission.USER_ADMIN)
        assert checker.has_permission(Permission.GRADING_ADMIN)
        assert checker.has_permission(Permission.CONTENT_ADMIN)


class TestRoleAliases:
    """Test role aliases (professor, instructor -> teacher)."""
    
    def test_professor_has_teacher_permissions(self):
        """Test professor role has same permissions as teacher."""
        prof_perms = get_permissions_for_role("professor")
        teacher_perms = get_permissions_for_role("teacher")
        
        assert prof_perms == teacher_perms
    
    def test_instructor_has_teacher_permissions(self):
        """Test instructor role has same permissions as teacher."""
        inst_perms = get_permissions_for_role("instructor")
        teacher_perms = get_permissions_for_role("teacher")
        
        assert inst_perms == teacher_perms
    
    def test_professor_token(self):
        """Test creating token with professor role."""
        from utils.auth import verify_access_token
        
        token_data = {
            "user_id": "prof-001",
            "email": "prof@school.com",
            "role": "professor"
        }
        token = create_access_token(token_data)
        decoded = verify_access_token(token)
        
        # Token should contain professor role
        assert decoded["role"] == "professor"
        
        # But permission check should work
        assert check_permission("professor", Permission.GRADING_WRITE)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
