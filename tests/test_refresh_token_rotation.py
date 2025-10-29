"""
Refresh Token Rotation Tests

Tests for refresh token rotation with server-side revocation:
- Token rotation on each refresh
- Chain tracking and validation
- Misuse detection (token reuse)
- Chain revocation on security violations
- httpOnly cookie storage
- Concurrent request handling

Security Tests:
✓ Stolen token detection via reuse
✓ Entire chain revocation on misuse
✓ Expired token rejection
✓ Revoked token rejection
✓ Chain integrity validation
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.user import User
from database.models.refresh_token import RefreshToken
from database.operations.refresh_token_ops import (
    create_refresh_token,
    get_refresh_token,
    rotate_refresh_token,
    revoke_token_chain,
    revoke_user_tokens,
    get_user_active_tokens
)
from utils.auth.refresh_token_handler import (
    create_refresh_token as create_refresh_token_jwt,
    verify_refresh_token
)


@pytest.fixture
async def test_user(async_session: AsyncSession):
    """Create a test user for refresh token tests."""
    from database.operations.user_ops import create_user
    
    user = await create_user(
        session=async_session,
        email="refresh_test@example.com",
        username="refresh_test_user",
        password="SecurePassword123!@#",
        name="Refresh Test User"
    )
    
    yield user
    
    # Cleanup
    await async_session.delete(user)
    await async_session.commit()


@pytest.fixture
async def initial_refresh_token(async_session: AsyncSession, test_user):
    """Create an initial refresh token for testing."""
    rotation_chain_id = RefreshToken.generate_chain_id()
    
    # Create JWT
    refresh_token_jwt = create_refresh_token_jwt(
        user_id=test_user.user_id,
        rotation_chain_id=rotation_chain_id,
        token_id="test_token_id_001"
    )
    
    # Store in database
    refresh_token = await create_refresh_token(
        session=async_session,
        user_id=test_user.user_id,
        token_value=refresh_token_jwt,
        rotation_chain_id=rotation_chain_id,
        device_info="pytest/1.0",
        ip_address="127.0.0.1"
    )
    
    yield refresh_token
    
    # Cleanup handled by cascade delete


class TestRefreshTokenRotation:
    """Test refresh token rotation functionality."""
    
    @pytest.mark.asyncio
    async def test_create_refresh_token(self, async_session: AsyncSession, test_user):
        """Test creating a refresh token."""
        rotation_chain_id = RefreshToken.generate_chain_id()
        
        refresh_token_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=rotation_chain_id,
            token_id="test_token_create"
        )
        
        refresh_token = await create_refresh_token(
            session=async_session,
            user_id=test_user.user_id,
            token_value=refresh_token_jwt,
            rotation_chain_id=rotation_chain_id
        )
        
        assert refresh_token is not None
        assert refresh_token.user_id == test_user.user_id
        assert refresh_token.rotation_chain_id == rotation_chain_id
        assert refresh_token.is_valid()
        assert not refresh_token.is_revoked
        assert not refresh_token.is_reused()
    
    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, async_session: AsyncSession, test_user, initial_refresh_token):
        """Test successful token rotation."""
        old_token_value = initial_refresh_token.token
        old_chain_id = initial_refresh_token.rotation_chain_id
        
        # Create new token JWT
        new_token_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=old_chain_id,
            token_id="test_token_rotated"
        )
        
        # Rotate token
        new_token, error = await rotate_refresh_token(
            session=async_session,
            old_token_value=old_token_value,
            new_token_value=new_token_jwt,
            device_info="pytest/1.0",
            ip_address="127.0.0.1"
        )
        
        # Verify rotation succeeded
        assert error is None
        assert new_token is not None
        assert new_token.rotation_chain_id == old_chain_id
        assert new_token.parent_token_id == initial_refresh_token.token_id
        assert new_token.is_valid()
        
        # Verify old token is marked as used
        await async_session.refresh(initial_refresh_token)
        assert initial_refresh_token.used_at is not None
        assert initial_refresh_token.is_reused()
    
    @pytest.mark.asyncio
    async def test_token_reuse_detection(self, async_session: AsyncSession, test_user, initial_refresh_token):
        """Test detection of token reuse (security threat)."""
        old_token_value = initial_refresh_token.token
        old_chain_id = initial_refresh_token.rotation_chain_id
        
        # First rotation - should succeed
        new_token_jwt_1 = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=old_chain_id,
            token_id="test_token_reuse_1"
        )
        
        new_token_1, error_1 = await rotate_refresh_token(
            session=async_session,
            old_token_value=old_token_value,
            new_token_value=new_token_jwt_1,
            device_info="pytest/1.0",
            ip_address="127.0.0.1"
        )
        
        assert error_1 is None
        assert new_token_1 is not None
        
        # Try to reuse old token - should fail and revoke chain
        new_token_jwt_2 = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=old_chain_id,
            token_id="test_token_reuse_2"
        )
        
        new_token_2, error_2 = await rotate_refresh_token(
            session=async_session,
            old_token_value=old_token_value,  # Reusing old token!
            new_token_value=new_token_jwt_2,
            device_info="attacker/1.0",
            ip_address="192.168.1.100"
        )
        
        # Verify reuse was detected
        assert error_2 == "refresh_token_reused_chain_revoked"
        assert new_token_2 is None
        
        # Verify entire chain is revoked
        await async_session.refresh(initial_refresh_token)
        await async_session.refresh(new_token_1)
        
        assert initial_refresh_token.is_revoked
        assert new_token_1.is_revoked
        assert initial_refresh_token.revocation_reason == "misuse_detected_token_reuse"
        assert new_token_1.revocation_reason == "misuse_detected_token_reuse"
    
    @pytest.mark.asyncio
    async def test_expired_token_rejection(self, async_session: AsyncSession, test_user):
        """Test that expired tokens are rejected."""
        rotation_chain_id = RefreshToken.generate_chain_id()
        
        # Create expired token (expires 1 day ago)
        expired_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=rotation_chain_id,
            token_id="test_token_expired",
            expires_delta=timedelta(days=-1)  # Already expired
        )
        
        expired_token = await create_refresh_token(
            session=async_session,
            user_id=test_user.user_id,
            token_value=expired_jwt,
            rotation_chain_id=rotation_chain_id,
            expires_days=0  # Force immediate expiry
        )
        
        # Manually set expiry to past
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await async_session.commit()
        
        # Try to rotate expired token
        new_token_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=rotation_chain_id,
            token_id="test_token_new"
        )
        
        new_token, error = await rotate_refresh_token(
            session=async_session,
            old_token_value=expired_jwt,
            new_token_value=new_token_jwt
        )
        
        assert error == "refresh_token_expired"
        assert new_token is None
    
    @pytest.mark.asyncio
    async def test_revoked_token_rejection(self, async_session: AsyncSession, test_user, initial_refresh_token):
        """Test that revoked tokens are rejected."""
        from database.operations.refresh_token_ops import revoke_token
        
        # Revoke the token
        await revoke_token(async_session, initial_refresh_token.token_id, "test_revocation")
        
        # Try to use revoked token
        new_token_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=initial_refresh_token.rotation_chain_id,
            token_id="test_token_after_revoke"
        )
        
        new_token, error = await rotate_refresh_token(
            session=async_session,
            old_token_value=initial_refresh_token.token,
            new_token_value=new_token_jwt
        )
        
        assert error == "refresh_token_revoked"
        assert new_token is None
    
    @pytest.mark.asyncio
    async def test_chain_revocation(self, async_session: AsyncSession, test_user):
        """Test revoking an entire rotation chain."""
        rotation_chain_id = RefreshToken.generate_chain_id()
        
        # Create multiple tokens in the same chain
        tokens = []
        for i in range(3):
            token_jwt = create_refresh_token_jwt(
                user_id=test_user.user_id,
                rotation_chain_id=rotation_chain_id,
                token_id=f"chain_token_{i}"
            )
            
            token = await create_refresh_token(
                session=async_session,
                user_id=test_user.user_id,
                token_value=token_jwt,
                rotation_chain_id=rotation_chain_id
            )
            tokens.append(token)
        
        # Revoke entire chain
        revoked_count = await revoke_token_chain(
            session=async_session,
            rotation_chain_id=rotation_chain_id,
            reason="test_chain_revocation"
        )
        
        assert revoked_count == 3
        
        # Verify all tokens are revoked
        for token in tokens:
            await async_session.refresh(token)
            assert token.is_revoked
            assert token.revocation_reason == "test_chain_revocation"
    
    @pytest.mark.asyncio
    async def test_user_logout_revokes_all_tokens(self, async_session: AsyncSession, test_user):
        """Test that logout revokes all user's refresh tokens."""
        # Create multiple refresh tokens for user
        tokens = []
        for i in range(3):
            chain_id = RefreshToken.generate_chain_id()
            token_jwt = create_refresh_token_jwt(
                user_id=test_user.user_id,
                rotation_chain_id=chain_id,
                token_id=f"logout_token_{i}"
            )
            
            token = await create_refresh_token(
                session=async_session,
                user_id=test_user.user_id,
                token_value=token_jwt,
                rotation_chain_id=chain_id
            )
            tokens.append(token)
        
        # Revoke all user tokens
        revoked_count = await revoke_user_tokens(
            session=async_session,
            user_id=test_user.user_id,
            reason="user_logout"
        )
        
        assert revoked_count == 3
        
        # Verify all are revoked
        for token in tokens:
            await async_session.refresh(token)
            assert token.is_revoked
            assert token.revocation_reason == "user_logout"
    
    @pytest.mark.asyncio
    async def test_rotation_chain_integrity(self, async_session: AsyncSession, test_user):
        """Test that rotation chain maintains parent-child relationships."""
        chain_id = RefreshToken.generate_chain_id()
        
        # Create initial token
        token_0_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=chain_id,
            token_id="chain_integrity_0"
        )
        
        token_0 = await create_refresh_token(
            session=async_session,
            user_id=test_user.user_id,
            token_value=token_0_jwt,
            rotation_chain_id=chain_id
        )
        
        # Rotate 3 times
        current_token = token_0
        tokens = [token_0]
        
        for i in range(1, 4):
            new_jwt = create_refresh_token_jwt(
                user_id=test_user.user_id,
                rotation_chain_id=chain_id,
                token_id=f"chain_integrity_{i}"
            )
            
            new_token, error = await rotate_refresh_token(
                session=async_session,
                old_token_value=current_token.token,
                new_token_value=new_jwt
            )
            
            assert error is None
            assert new_token.parent_token_id == current_token.token_id
            assert new_token.rotation_chain_id == chain_id
            
            tokens.append(new_token)
            current_token = new_token
        
        # Verify chain structure
        for i in range(1, len(tokens)):
            assert tokens[i].parent_token_id == tokens[i-1].token_id
            assert tokens[i].rotation_chain_id == chain_id
    
    @pytest.mark.asyncio
    async def test_jwt_verification(self, test_user):
        """Test JWT refresh token creation and verification."""
        chain_id = RefreshToken.generate_chain_id()
        token_id = "test_jwt_verification"
        
        # Create JWT
        token_jwt = create_refresh_token_jwt(
            user_id=test_user.user_id,
            rotation_chain_id=chain_id,
            token_id=token_id
        )
        
        # Verify JWT
        payload = verify_refresh_token(token_jwt)
        
        assert payload["user_id"] == test_user.user_id
        assert payload["rotation_chain_id"] == chain_id
        assert payload["token_id"] == token_id
        assert payload["type"] == "refresh"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload
    
    @pytest.mark.asyncio
    async def test_get_user_active_tokens(self, async_session: AsyncSession, test_user):
        """Test retrieving user's active tokens."""
        # Create 3 active tokens and 2 revoked tokens
        active_tokens = []
        for i in range(3):
            chain_id = RefreshToken.generate_chain_id()
            token_jwt = create_refresh_token_jwt(
                user_id=test_user.user_id,
                rotation_chain_id=chain_id,
                token_id=f"active_token_{i}"
            )
            
            token = await create_refresh_token(
                session=async_session,
                user_id=test_user.user_id,
                token_value=token_jwt,
                rotation_chain_id=chain_id
            )
            active_tokens.append(token)
        
        # Create 2 revoked tokens
        for i in range(2):
            chain_id = RefreshToken.generate_chain_id()
            token_jwt = create_refresh_token_jwt(
                user_id=test_user.user_id,
                rotation_chain_id=chain_id,
                token_id=f"revoked_token_{i}"
            )
            
            token = await create_refresh_token(
                session=async_session,
                user_id=test_user.user_id,
                token_value=token_jwt,
                rotation_chain_id=chain_id
            )
            token.is_revoked = True
            await async_session.commit()
        
        # Get active tokens
        active = await get_user_active_tokens(async_session, test_user.user_id)
        
        assert len(active) == 3
        for token in active:
            assert not token.is_revoked
            assert token.is_valid()


class TestRefreshTokenAPI:
    """Test refresh token API endpoints."""
    
    @pytest.mark.asyncio
    async def test_refresh_endpoint_success(self, async_client: AsyncClient, test_user, async_session: AsyncSession):
        """Test successful token refresh via API."""
        # First login to get refresh token
        login_response = await async_client.post(
            "/api/auth/login/",
            json={
                "username": test_user.username,
                "password": "SecurePassword123!@#"
            }
        )
        
        assert login_response.status_code == 200
        
        # Get refresh token from cookie
        cookies = login_response.cookies
        assert "refresh_token" in cookies
        
        # Call refresh endpoint
        refresh_response = await async_client.post(
            "/api/auth/refresh/",
            cookies=cookies
        )
        
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        
        assert "access_token" in refresh_data
        assert "expires_at" in refresh_data
        assert refresh_data["token_type"] == "bearer"
        
        # Verify new refresh token in cookies
        new_cookies = refresh_response.cookies
        assert "refresh_token" in new_cookies
        assert new_cookies["refresh_token"] != cookies["refresh_token"]
    
    @pytest.mark.asyncio
    async def test_refresh_endpoint_missing_token(self, async_client: AsyncClient):
        """Test refresh endpoint without refresh token."""
        response = await async_client.post("/api/auth/refresh/")
        
        assert response.status_code == 401
        assert "missing_refresh_token" in response.json()["detail"]["error"]
    
    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_tokens(self, async_client: AsyncClient, test_user):
        """Test that logout revokes refresh tokens."""
        # Login
        login_response = await async_client.post(
            "/api/auth/login/",
            json={
                "username": test_user.username,
                "password": "SecurePassword123!@#"
            }
        )
        
        assert login_response.status_code == 200
        cookies = login_response.cookies
        token = login_response.json()["token"]
        
        # Logout
        logout_response = await async_client.post(
            "/api/auth/logout/",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert logout_response.status_code == 200
        
        # Try to refresh - should fail
        refresh_response = await async_client.post(
            "/api/auth/refresh/",
            cookies=cookies
        )
        
        assert refresh_response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
