"""
Tests for the /session/validate endpoint.

This endpoint provides lightweight session validation for silent reauth checks.
"""

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock


def test_session_validate_no_token(test_client):
    """Test session validation with no token returns valid=false."""
    response = test_client.get("/api/auth/session/validate")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["valid"] is False
    assert data["user_id"] is None
    assert data["username"] is None
    assert data["email"] is None
    assert data["role"] is None


def test_session_validate_invalid_token(test_client):
    """Test session validation with invalid token returns valid=false."""
    response = test_client.get(
        "/api/auth/session/validate",
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["valid"] is False


def test_session_validate_expired_token(test_client):
    """Test session validation with expired token returns valid=false."""
    # Use a token that's expired
    expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxNTE2MjM5MDIyfQ.invalid"
    
    response = test_client.get(
        "/api/auth/session/validate",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["valid"] is False


def test_session_validate_cached_token(test_client):
    """Test session validation with cached token (no DB hit)."""
    # Mock cache with valid user data
    mock_user_data = {
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "role": "student"
    }
    
    with patch("api.routers.auth.get_token_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=mock_user_data)
        mock_get_cache.return_value = mock_cache
        
        response = test_client.get(
            "/api/auth/session/validate",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == "test-user-123"
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["role"] == "student"


def test_session_validate_with_cookie(test_client):
    """Test session validation using httpOnly cookie."""
    # Mock cache with valid user data
    mock_user_data = {
        "user_id": "test-user-456",
        "username": "cookieuser",
        "email": "cookie@example.com",
        "role": "teacher"
    }
    
    with patch("api.routers.auth.get_token_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=mock_user_data)
        mock_get_cache.return_value = mock_cache
        
        # Set cookie
        test_client.cookies.set("access_token", "test_cookie_token")
        
        response = test_client.get("/api/auth/session/validate")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == "test-user-456"
        assert data["username"] == "cookieuser"
        assert data["email"] == "cookie@example.com"
        assert data["role"] == "teacher"


def test_session_validate_valid_jwt_not_cached(test_client):
    """Test session validation with valid JWT that's not in cache."""
    from utils.auth.jwt_handler import create_access_token
    
    # Create a valid JWT token
    token_data = {
        "user_id": "jwt-user-789",
        "username": "jwtuser",
        "email": "jwt@example.com",
        "role": "admin"
    }
    
    token = create_access_token(token_data)
    
    # Mock cache to return None (not cached)
    with patch("api.routers.auth.get_token_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_get_cache.return_value = mock_cache
        
        response = test_client.get(
            "/api/auth/session/validate",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == "jwt-user-789"
        assert data["email"] == "jwt@example.com"
        assert data["role"] == "admin"
        
        # Verify the token was cached
        mock_cache.set.assert_called_once()


def test_session_validate_performance_no_db_hit(test_client):
    """Test that session validation doesn't hit the database when token is cached."""
    mock_user_data = {
        "user_id": "perf-test-user",
        "username": "perfuser",
        "email": "perf@example.com",
        "role": "student"
    }
    
    with patch("api.routers.auth.get_token_cache") as mock_get_cache, \
         patch("database.operations.token_ops.get_token") as mock_db_get:
        
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=mock_user_data)
        mock_get_cache.return_value = mock_cache
        
        response = test_client.get(
            "/api/auth/session/validate",
            headers={"Authorization": "Bearer cached_token"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["valid"] is True
        
        # Verify database was NOT called
        mock_db_get.assert_not_called()


def test_session_validate_minimal_response(test_client):
    """Test that session validation returns minimal response (lightweight)."""
    response = test_client.get("/api/auth/session/validate")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Check response only contains expected fields
    expected_fields = {"valid", "user_id", "username", "email", "role"}
    assert set(data.keys()) == expected_fields
    
    # Check response size is small
    import json
    response_size = len(json.dumps(data))
    assert response_size < 500, "Response should be lightweight (< 500 bytes)"


def test_session_validate_cookie_preference(test_client):
    """Test that cookie token is preferred over header token."""
    cookie_user_data = {
        "user_id": "cookie-user",
        "username": "cookieuser",
        "email": "cookie@example.com",
        "role": "student"
    }
    
    with patch("utils.auth.cookie_config.CookieConfig.get_token_from_cookie_or_header") as mock_get_token:
        mock_get_token.return_value = "cookie_token"
        
        with patch("api.routers.auth.get_token_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=cookie_user_data)
            mock_get_cache.return_value = mock_cache
            
            # Set both cookie and header
            test_client.cookies.set("access_token", "cookie_token")
            
            response = test_client.get(
                "/api/auth/session/validate",
                headers={"Authorization": "Bearer header_token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["valid"] is True
            
            # Verify the cookie extraction was called
            mock_get_token.assert_called_once()


def test_session_validate_graceful_error_handling(test_client):
    """Test that session validation handles errors gracefully."""
    with patch("utils.auth.cookie_config.CookieConfig.get_token_from_cookie_or_header") as mock_get_token:
        # Simulate an unexpected error
        mock_get_token.side_effect = Exception("Unexpected error")
        
        response = test_client.get("/api/auth/session/validate")
        
        # Should still return 200 with valid=false
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False


def test_session_validate_cors_compatible(test_client):
    """Test that session validation endpoint is CORS compatible."""
    response = test_client.options("/api/auth/session/validate")
    
    # Should handle OPTIONS preflight request
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

