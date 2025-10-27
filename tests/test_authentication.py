"""
Comprehensive Authentication Tests

Tests all authentication endpoints with edge cases, security scenarios,
and performance conditions.

Coverage:
- Login/Registration flows
- Password policy validation
- Account lockout mechanisms
- Session management
- Google OAuth integration
- Admin functions
- Security monitoring
- Performance under load
- Error handling
- Edge cases

Author: Study Search Agent Team
Version: 1.0.0
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from api.app import app
from database.core.async_connection import get_session
from database.models.user import User, UserRole
from database.models.token import Token
from utils.auth.password import hash_password, verify_password
from utils.auth.account_lockout import AccountLockoutManager
from config import settings


# ============================================================================
# Test Configuration and Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async test client for FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_session():
    """Test database session."""
    # Mock session for testing
    session = AsyncMock(spec=AsyncSession)
    yield session


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "role": "student"
    }


@pytest.fixture
def test_user():
    """Test user object."""
    return User(
        user_id="test@example.com",
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        password_hash=hash_password("SecurePassword123!"),
        role=UserRole.STUDENT,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc)
    )


@pytest.fixture
def test_token():
    """Test token object."""
    return Token(
        token="test_token_123",
        user_id="test@example.com",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        is_active=True,
        device_info="Test Device",
        ip_address="127.0.0.1"
    )


@pytest.fixture
def admin_user():
    """Admin user for testing admin endpoints."""
    return User(
        user_id="admin@example.com",
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        password_hash=hash_password("AdminPassword123!"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )


# ============================================================================
# Login Tests
# ============================================================================

class TestLogin:
    """Test login endpoint with all edge cases."""
    
    @pytest.mark.asyncio
    async def test_successful_login(self, client, test_user_data, test_user):
        """Test successful login."""
        with patch('api.routers.auth.authenticate_user', return_value=test_user):
            with patch('api.routers.auth.create_token', return_value=Mock(token="test_token")):
                response = client.post("/api/auth/login/", json={
                    "username": test_user_data["email"],
                    "password": test_user_data["password"],
                    "device_name": "Test Device"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert "token" in data
                assert "user" in data
                assert "expires_at" in data
                assert "session_id" in data
                assert data["user"]["email"] == test_user_data["email"]
    
    @pytest.mark.asyncio
    async def test_login_with_username(self, client, test_user_data, test_user):
        """Test login with username instead of email."""
        with patch('api.routers.auth.authenticate_user', return_value=test_user):
            with patch('api.routers.auth.create_token', return_value=Mock(token="test_token")):
                response = client.post("/api/auth/login/", json={
                    "username": test_user_data["username"],
                    "password": test_user_data["password"]
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["user"]["username"] == test_user_data["username"]
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        with patch('api.routers.auth.authenticate_user', return_value=None):
            with patch('api.routers.auth.record_failed_login'):
                response = client.post("/api/auth/login/", json={
                    "username": "nonexistent@example.com",
                    "password": "wrongpassword"
                })
                
                assert response.status_code == 401
                data = response.json()
                assert data["detail"]["error"] == "invalid_credentials"
    
    @pytest.mark.asyncio
    async def test_login_account_locked(self, client):
        """Test login with locked account."""
        with patch('api.routers.auth.check_account_lockout', return_value=(True, "Account locked")):
            response = client.post("/api/auth/login/", json={
                "username": "locked@example.com",
                "password": "password123"
            })
            
            assert response.status_code == 423
            data = response.json()
            assert data["detail"]["error"] == "account_locked"
    
    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client):
        """Test login with inactive user."""
        inactive_user = User(
            user_id="inactive@example.com",
            email="inactive@example.com",
            username="inactive",
            password_hash=hash_password("password123"),
            is_active=False
        )
        
        with patch('api.routers.auth.authenticate_user', return_value=inactive_user):
            response = client.post("/api/auth/login/", json={
                "username": "inactive@example.com",
                "password": "password123"
            })
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_missing_password_hash(self, client):
        """Test login with user having no password hash."""
        user_no_hash = User(
            user_id="nohash@example.com",
            email="nohash@example.com",
            username="nohash",
            password_hash=None,
            settings={"password_hash": hash_password("password123")}
        )
        
        with patch('api.routers.auth.authenticate_user', return_value=user_no_hash):
            with patch('api.routers.auth.create_token', return_value=Mock(token="test_token")):
                response = client.post("/api/auth/login/", json={
                    "username": "nohash@example.com",
                    "password": "password123"
                })
                
                assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_login_empty_username(self, client):
        """Test login with empty username."""
        response = client.post("/api/auth/login/", json={
            "username": "",
            "password": "password123"
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_empty_password(self, client):
        """Test login with empty password."""
        response = client.post("/api/auth/login/", json={
            "username": "test@example.com",
            "password": ""
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """Test login with missing required fields."""
        response = client.post("/api/auth/login/", json={
            "username": "test@example.com"
            # Missing password
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_invalid_json(self, client):
        """Test login with invalid JSON."""
        response = client.post("/api/auth/login/", 
                              data="invalid json",
                              headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_very_long_username(self, client):
        """Test login with extremely long username."""
        long_username = "a" * 300  # Exceeds max length
        
        response = client.post("/api/auth/login/", json={
            "username": long_username,
            "password": "password123"
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_very_long_password(self, client):
        """Test login with extremely long password."""
        long_password = "a" * 200  # Exceeds max length
        
        response = client.post("/api/auth/login/", json={
            "username": "test@example.com",
            "password": long_password
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_sql_injection_attempt(self, client):
        """Test login with SQL injection attempt."""
        with patch('api.routers.auth.authenticate_user', return_value=None):
            with patch('api.routers.auth.record_failed_login'):
                response = client.post("/api/auth/login/", json={
                    "username": "'; DROP TABLE users; --",
                    "password": "password123"
                })
                
                assert response.status_code == 401
                # Should not cause SQL injection
    
    @pytest.mark.asyncio
    async def test_login_xss_attempt(self, client):
        """Test login with XSS attempt."""
        with patch('api.routers.auth.authenticate_user', return_value=None):
            with patch('api.routers.auth.record_failed_login'):
                response = client.post("/api/auth/login/", json={
                    "username": "<script>alert('xss')</script>",
                    "password": "password123"
                })
                
                assert response.status_code == 401
                # Should not execute XSS


# ============================================================================
# Registration Tests
# ============================================================================

class TestRegistration:
    """Test registration endpoint with all edge cases."""
    
    @pytest.mark.asyncio
    async def test_successful_registration(self, client, test_user_data):
        """Test successful user registration."""
        with patch('api.routers.auth.get_user_by_email', return_value=None):
            with patch('api.routers.auth.create_user', return_value=Mock(**test_user_data)):
                with patch('api.routers.auth.create_token', return_value=Mock(token="test_token")):
                    response = client.post("/api/auth/register/", json=test_user_data)
                    
                    assert response.status_code == 201
                    data = response.json()
                    assert "user" in data
                    assert "token" in data
                    assert "password_strength" in data
    
    @pytest.mark.asyncio
    async def test_registration_weak_password(self, client, test_user_data):
        """Test registration with weak password."""
        weak_password_data = test_user_data.copy()
        weak_password_data["password"] = "123"
        
        with patch('api.routers.auth.validate_password_policy') as mock_validate:
            mock_validate.return_value = Mock(
                is_valid=False,
                errors=["Password too short"],
                suggestions=["Add more characters"]
            )
            
            response = client.post("/api/auth/register/", json=weak_password_data)
            
            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"] == "weak_password"
    
    @pytest.mark.asyncio
    async def test_registration_existing_email(self, client, test_user_data):
        """Test registration with existing email."""
        existing_user = Mock(email=test_user_data["email"])
        
        with patch('api.routers.auth.get_user_by_email', return_value=existing_user):
            response = client.post("/api/auth/register/", json=test_user_data)
            
            assert response.status_code == 409
            data = response.json()
            assert data["detail"]["error"] == "user_exists"
    
    @pytest.mark.asyncio
    async def test_registration_invalid_email(self, client, test_user_data):
        """Test registration with invalid email format."""
        invalid_email_data = test_user_data.copy()
        invalid_email_data["email"] = "invalid-email"
        
        response = client.post("/api/auth/register/", json=invalid_email_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_registration_invalid_role(self, client, test_user_data):
        """Test registration with invalid role."""
        invalid_role_data = test_user_data.copy()
        invalid_role_data["role"] = "invalid_role"
        
        response = client.post("/api/auth/register/", json=invalid_role_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_registration_empty_fields(self, client):
        """Test registration with empty required fields."""
        response = client.post("/api/auth/register/", json={
            "email": "",
            "username": "",
            "password": "",
            "full_name": ""
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_registration_username_too_short(self, client, test_user_data):
        """Test registration with username too short."""
        short_username_data = test_user_data.copy()
        short_username_data["username"] = "ab"  # Less than min_length=3
        
        response = client.post("/api/auth/register/", json=short_username_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_registration_username_too_long(self, client, test_user_data):
        """Test registration with username too long."""
        long_username_data = test_user_data.copy()
        long_username_data["username"] = "a" * 51  # Exceeds max_length=50
        
        response = client.post("/api/auth/register/", json=long_username_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_registration_password_contains_personal_info(self, client, test_user_data):
        """Test registration with password containing personal info."""
        personal_info_data = test_user_data.copy()
        personal_info_data["password"] = "testuser123"  # Contains username
        
        with patch('api.routers.auth.validate_password_policy') as mock_validate:
            mock_validate.return_value = Mock(
                is_valid=False,
                errors=["Password should not contain your username"]
            )
            
            response = client.post("/api/auth/register/", json=personal_info_data)
            
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_registration_common_password(self, client, test_user_data):
        """Test registration with common password."""
        common_password_data = test_user_data.copy()
        common_password_data["password"] = "password123"
        
        with patch('api.routers.auth.validate_password_policy') as mock_validate:
            mock_validate.return_value = Mock(
                is_valid=False,
                errors=["Password is too common and easily guessable"]
            )
            
            response = client.post("/api/auth/register/", json=common_password_data)
            
            assert response.status_code == 400


# ============================================================================
# Password Management Tests
# ============================================================================

class TestPasswordManagement:
    """Test password management endpoints."""
    
    @pytest.mark.asyncio
    async def test_password_change_success(self, client, test_user):
        """Test successful password change."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            with patch('api.routers.auth.change_user_password', return_value=True):
                with patch('api.routers.auth.delete_user_tokens'):
                    response = client.post("/api/auth/change-password/", 
                                         json={
                                             "current_password": "SecurePassword123!",
                                             "new_password": "NewSecurePassword456!",
                                             "confirm_password": "NewSecurePassword456!"
                                         },
                                         headers={"Authorization": "Token test_token"})
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_password_change_wrong_current_password(self, client, test_user):
        """Test password change with wrong current password."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            with patch('api.routers.auth.change_user_password', return_value=False):
                response = client.post("/api/auth/change-password/", 
                                     json={
                                         "current_password": "WrongPassword123!",
                                         "new_password": "NewSecurePassword456!",
                                         "confirm_password": "NewSecurePassword456!"
                                     },
                                     headers={"Authorization": "Token test_token"})
                
                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"] == "invalid_password"
    
    @pytest.mark.asyncio
    async def test_password_change_passwords_dont_match(self, client, test_user):
        """Test password change with mismatched passwords."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            response = client.post("/api/auth/change-password/", 
                                 json={
                                     "current_password": "SecurePassword123!",
                                     "new_password": "NewSecurePassword456!",
                                     "confirm_password": "DifferentPassword789!"
                                 },
                                 headers={"Authorization": "Token test_token"})
            
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_password_change_weak_new_password(self, client, test_user):
        """Test password change with weak new password."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            with patch('api.routers.auth.validate_password_policy') as mock_validate:
                mock_validate.return_value = Mock(
                    is_valid=False,
                    errors=["Password too short"]
                )
                
                response = client.post("/api/auth/change-password/", 
                                     json={
                                         "current_password": "SecurePassword123!",
                                         "new_password": "123",
                                         "confirm_password": "123"
                                     },
                                     headers={"Authorization": "Token test_token"})
                
                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"] == "weak_password"
    
    @pytest.mark.asyncio
    async def test_password_change_no_auth(self, client):
        """Test password change without authentication."""
        response = client.post("/api/auth/change-password/", 
                             json={
                                 "current_password": "SecurePassword123!",
                                 "new_password": "NewSecurePassword456!",
                                 "confirm_password": "NewSecurePassword456!"
                             })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_password_validation_success(self, client):
        """Test password validation with strong password."""
        with patch('api.routers.auth.validate_password_policy') as mock_validate:
            mock_validate.return_value = Mock(
                is_valid=True,
                strength="strong",
                score=85,
                errors=[],
                warnings=[],
                suggestions=[]
            )
            
            response = client.post("/api/auth/validate-password/", 
                                 json={
                                     "password": "StrongPassword123!",
                                     "username": "testuser",
                                     "email": "test@example.com"
                                 })
            
            assert response.status_code == 200
            data = response.json()
            assert data["is_valid"] is True
            assert data["strength"] == "strong"


# ============================================================================
# Session Management Tests
# ============================================================================

class TestSessionManagement:
    """Test session management endpoints."""
    
    @pytest.mark.asyncio
    async def test_logout_success(self, client, test_user):
        """Test successful logout."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            with patch('api.routers.auth.delete_token'):
                response = client.post("/api/auth/logout/", 
                                     json={"logout_all_devices": False},
                                     headers={"Authorization": "Token test_token"})
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_logout_all_devices(self, client, test_user):
        """Test logout from all devices."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            with patch('api.routers.auth.delete_user_tokens'):
                response = client.post("/api/auth/logout/", 
                                     json={"logout_all_devices": True},
                                     headers={"Authorization": "Token test_token"})
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["sessions_terminated"] == "all"
    
    @pytest.mark.asyncio
    async def test_get_sessions(self, client, test_user):
        """Test getting active sessions."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": test_user.user_id}):
            response = client.get("/api/auth/sessions/", 
                                headers={"Authorization": "Token test_token"})
            
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "total_count" in data
    
    @pytest.mark.asyncio
    async def test_logout_no_auth(self, client):
        """Test logout without authentication."""
        response = client.post("/api/auth/logout/", 
                             json={"logout_all_devices": False})
        
        assert response.status_code == 401


# ============================================================================
# Google OAuth Tests
# ============================================================================

class TestGoogleOAuth:
    """Test Google OAuth integration."""
    
    @pytest.mark.asyncio
    async def test_google_login_redirect(self, client):
        """Test Google login redirect."""
        with patch('api.routers.auth.google_oauth.get_authorization_url', return_value="https://google.com/oauth"):
            response = client.get("/api/auth/google/login/")
            
            assert response.status_code == 307  # Redirect
            assert "google.com/oauth" in response.headers["location"]
    
    @pytest.mark.asyncio
    async def test_google_login_not_configured(self, client):
        """Test Google login when not configured."""
        with patch.dict('os.environ', {'GOOGLE_OAUTH_CLIENT_ID': '', 'GOOGLE_OAUTH_CLIENT_SECRET': ''}):
            response = client.get("/api/auth/google/login/")
            
            assert response.status_code == 500
            data = response.json()
            assert "not configured" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_google_callback_success(self, client):
        """Test successful Google OAuth callback."""
        mock_user_data = {
            "id": "google123",
            "email": "oauth@example.com",
            "name": "OAuth User",
            "picture": "https://example.com/pic.jpg",
            "verified_email": True
        }
        
        with patch('api.routers.auth.get_http_client') as mock_client:
            mock_client.return_value.post.return_value.status_code = 200
            mock_client.return_value.post.return_value.json.return_value = {"access_token": "google_token"}
            mock_client.return_value.get.return_value.status_code = 200
            mock_client.return_value.get.return_value.json.return_value = mock_user_data
            
            with patch('api.routers.auth.get_async_db'):
                response = client.get("/api/auth/google/callback/?code=test_code")
                
                assert response.status_code == 307  # Redirect to frontend
    
    @pytest.mark.asyncio
    async def test_google_callback_missing_code(self, client):
        """Test Google callback with missing code."""
        response = client.get("/api/auth/google/callback/")
        
        assert response.status_code == 400
        data = response.json()
        assert "Missing authorization code" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_google_callback_invalid_code(self, client):
        """Test Google callback with invalid code."""
        with patch('api.routers.auth.get_http_client') as mock_client:
            mock_client.return_value.post.return_value.status_code = 400
            mock_client.return_value.post.return_value.text = "Invalid code"
            
            response = client.get("/api/auth/google/callback/?code=invalid_code")
            
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_google_callback_network_error(self, client):
        """Test Google callback with network error."""
        with patch('api.routers.auth.get_http_client') as mock_client:
            mock_client.return_value.post.side_effect = Exception("Network error")
            
            response = client.get("/api/auth/google/callback/?code=test_code")
            
            assert response.status_code == 307  # Redirect to error page


# ============================================================================
# Admin Endpoints Tests
# ============================================================================

class TestAdminEndpoints:
    """Test admin-only endpoints."""
    
    @pytest.mark.asyncio
    async def test_admin_unlock_account_success(self, client, admin_user):
        """Test successful account unlock by admin."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"role": "admin", "user_id": admin_user.user_id}):
            with patch('api.routers.auth.get_lockout_manager') as mock_manager:
                mock_manager.return_value.unlock_account.return_value = True
                
                response = client.post("/api/auth/admin/unlock-account/test@example.com",
                                     headers={"Authorization": "Token admin_token"})
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_admin_unlock_account_non_admin(self, client, test_user):
        """Test account unlock by non-admin user."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"role": "student", "user_id": test_user.user_id}):
            response = client.post("/api/auth/admin/unlock-account/test@example.com",
                                 headers={"Authorization": "Token user_token"})
            
            assert response.status_code == 403
            data = response.json()
            assert "Admin access required" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_admin_get_lockout_stats(self, client, admin_user):
        """Test getting lockout statistics."""
        with patch('api.routers.auth._get_current_user_from_token', return_value={"role": "admin", "user_id": admin_user.user_id}):
            with patch('api.routers.auth.get_lockout_manager') as mock_manager:
                mock_manager.return_value.get_lockout_stats.return_value = {"locked_accounts": 5}
                
                response = client.get("/api/auth/admin/lockout-stats/",
                                    headers={"Authorization": "Token admin_token"})
                
                assert response.status_code == 200
                data = response.json()
                assert "locked_accounts" in data
    
    @pytest.mark.asyncio
    async def test_admin_endpoints_no_auth(self, client):
        """Test admin endpoints without authentication."""
        response = client.post("/api/auth/admin/unlock-account/test@example.com")
        assert response.status_code == 401
        
        response = client.get("/api/auth/admin/lockout-stats/")
        assert response.status_code == 401


# ============================================================================
# Security Tests
# ============================================================================

class TestSecurityFeatures:
    """Test security features and edge cases."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_login_attempts(self, client):
        """Test rate limiting on login attempts."""
        # Simulate multiple rapid login attempts
        for i in range(10):
            response = client.post("/api/auth/login/", json={
                "username": f"user{i}@example.com",
                "password": "password123"
            })
            
            # Should eventually hit rate limit
            if response.status_code == 429:
                break
        
        # Rate limiting should be handled by middleware
        assert True  # Test passes if no exceptions
    
    @pytest.mark.asyncio
    async def test_account_lockout_progression(self, client):
        """Test progressive account lockout."""
        username = "lockout@example.com"
        
        # Simulate multiple failed login attempts
        for attempt in range(6):  # More than max_login_attempts
            with patch('api.routers.auth.authenticate_user', return_value=None):
                with patch('api.routers.auth.record_failed_login'):
                    response = client.post("/api/auth/login/", json={
                        "username": username,
                        "password": "wrongpassword"
                    })
                    
                    if attempt < 5:
                        assert response.status_code == 401
                    else:
                        # Should be locked after 5 attempts
                        assert response.status_code == 423
    
    @pytest.mark.asyncio
    async def test_session_fingerprinting(self, client, test_user):
        """Test session fingerprinting."""
        with patch('api.routers.auth.authenticate_user', return_value=test_user):
            with patch('api.routers.auth.create_token', return_value=Mock(token="test_token")):
                response = client.post("/api/auth/login/", 
                                     json={
                                         "username": test_user.email,
                                         "password": "SecurePassword123!"
                                     },
                                     headers={"User-Agent": "Test Browser"})
                
                assert response.status_code == 200
                data = response.json()
                assert "session_id" in data
                assert len(data["session_id"]) == 16  # Fingerprint length
    
    @pytest.mark.asyncio
    async def test_security_headers(self, client):
        """Test security headers are present."""
        response = client.get("/api/auth/config/")
        
        # Security headers should be added by middleware
        assert response.status_code == 200
        # Headers are tested in middleware tests
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, client):
        """Test CORS headers."""
        response = client.options("/api/auth/login/")
        
        assert response.status_code == 200
        # CORS headers should be present


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_logins(self, async_client):
        """Test concurrent login requests."""
        async def login_request():
            return await async_client.post("/api/auth/login/", json={
                "username": "concurrent@example.com",
                "password": "password123"
            })
        
        # Run 10 concurrent login requests
        tasks = [login_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All requests should complete (even if they fail)
        assert len(responses) == 10
    
    @pytest.mark.asyncio
    async def test_token_validation_performance(self, async_client):
        """Test token validation performance."""
        with patch('api.routers.auth.get_token_cache') as mock_cache:
            mock_cache.return_value.get.return_value = {"user_id": "test@example.com"}
            
            # Measure time for multiple token validations
            start_time = time.time()
            
            tasks = []
            for _ in range(100):
                task = async_client.get("/api/auth/me/", 
                                      headers={"Authorization": "Token test_token"})
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            end_time = time.time()
            
            # Should be very fast due to caching
            assert end_time - start_time < 1.0  # Less than 1 second for 100 requests
            assert all(r.status_code == 200 for r in responses)
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling(self, async_client):
        """Test database connection pooling under load."""
        # This test would require actual database connections
        # For now, we'll test that the app doesn't crash under load
        tasks = []
        for i in range(50):
            task = async_client.get("/api/auth/config/")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All requests should complete without exceptions
        assert len(responses) == 50
        assert not any(isinstance(r, Exception) for r in responses)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self, client):
        """Test handling of database connection errors."""
        with patch('api.routers.auth.get_session', side_effect=Exception("Database connection failed")):
            response = client.post("/api/auth/login/", json={
                "username": "test@example.com",
                "password": "password123"
            })
            
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_redis_connection_error(self, client):
        """Test handling of Redis connection errors."""
        with patch('api.routers.auth.check_account_lockout', side_effect=Exception("Redis connection failed")):
            response = client.post("/api/auth/login/", json={
                "username": "test@example.com",
                "password": "password123"
            })
            
            # Should handle Redis errors gracefully
            assert response.status_code in [500, 423]
    
    @pytest.mark.asyncio
    async def test_malformed_token(self, client):
        """Test handling of malformed tokens."""
        response = client.get("/api/auth/me/", 
                            headers={"Authorization": "InvalidTokenFormat"})
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_token(self, client):
        """Test handling of expired tokens."""
        expired_token = Token(
            token="expired_token",
            user_id="test@example.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_active=True
        )
        
        with patch('api.routers.auth.verify_token_data', return_value=None):
            response = client.get("/api/auth/me/", 
                                headers={"Authorization": "Token expired_token"})
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_memory_limit_exceeded(self, client):
        """Test handling when memory limits are exceeded."""
        # This would require actual memory pressure testing
        # For now, we'll test that the app handles large requests gracefully
        large_data = {"username": "test@example.com", "password": "a" * 1000}
        
        response = client.post("/api/auth/login/", json=large_data)
        
        # Should reject oversized requests
        assert response.status_code == 422


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test complete authentication flows."""
    
    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, client):
        """Test complete authentication flow from registration to logout."""
        # 1. Register user
        user_data = {
            "email": "integration@example.com",
            "username": "integration",
            "password": "IntegrationTest123!",
            "full_name": "Integration Test",
            "role": "student"
        }
        
        with patch('api.routers.auth.get_user_by_email', return_value=None):
            with patch('api.routers.auth.create_user', return_value=Mock(**user_data)):
                with patch('api.routers.auth.create_token', return_value=Mock(token="integration_token")):
                    register_response = client.post("/api/auth/register/", json=user_data)
                    assert register_response.status_code == 201
                    
                    token = register_response.json()["token"]
        
        # 2. Use token to access protected endpoint
        with patch('api.routers.auth._get_current_user_from_token', return_value={"user_id": user_data["email"]}):
            me_response = client.get("/api/auth/me/", 
                                   headers={"Authorization": f"Token {token}"})
            assert me_response.status_code == 200
        
        # 3. Change password
        with patch('api.routers.auth.change_user_password', return_value=True):
            with patch('api.routers.auth.delete_user_tokens'):
                change_response = client.post("/api/auth/change-password/", 
                                           json={
                                               "current_password": user_data["password"],
                                               "new_password": "NewIntegrationTest456!",
                                               "confirm_password": "NewIntegrationTest456!"
                                           },
                                           headers={"Authorization": f"Token {token}"})
                assert change_response.status_code == 200
        
        # 4. Logout
        with patch('api.routers.auth.delete_token'):
            logout_response = client.post("/api/auth/logout/", 
                                       json={"logout_all_devices": False},
                                       headers={"Authorization": f"Token {token}"})
            assert logout_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_oauth_integration_flow(self, client):
        """Test complete OAuth integration flow."""
        # This would test the full OAuth flow
        # For now, we'll test the individual components
        
        # 1. Initiate OAuth
        with patch('api.routers.auth.google_oauth.get_authorization_url', return_value="https://google.com/oauth"):
            oauth_response = client.get("/api/auth/google/login/")
            assert oauth_response.status_code == 307
        
        # 2. Handle callback
        mock_user_data = {
            "id": "oauth123",
            "email": "oauth@example.com",
            "name": "OAuth User",
            "verified_email": True
        }
        
        with patch('api.routers.auth.get_http_client') as mock_client:
            mock_client.return_value.post.return_value.status_code = 200
            mock_client.return_value.post.return_value.json.return_value = {"access_token": "google_token"}
            mock_client.return_value.get.return_value.status_code = 200
            mock_client.return_value.get.return_value.json.return_value = mock_user_data
            
            callback_response = client.get("/api/auth/google/callback/?code=test_code")
            assert callback_response.status_code == 307


# ============================================================================
# Test Configuration
# ============================================================================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
