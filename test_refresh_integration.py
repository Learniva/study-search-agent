"""
Quick integration test for refresh token rotation.
Run this to verify the implementation works end-to-end.
"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.async_engine import get_async_db
from database.operations.user_ops import create_user, get_user_by_email
from database.operations.refresh_token_ops import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_user_tokens,
    get_user_active_tokens
)
from database.models.refresh_token import RefreshToken
from utils.auth.refresh_token_handler import (
    create_refresh_token as create_refresh_token_jwt,
    verify_refresh_token
)


async def test_refresh_token_integration():
    """Test the complete refresh token flow."""
    print("\n Testing Refresh Token Rotation Integration\n")
    
    async for session in get_async_db():
        try:
            # 1. Create test user
            print("1  Creating test user...")
            test_email = f"refresh_test_{datetime.now().timestamp()}@example.com"
            user = await create_user(
                session=session,
                email=test_email,
                username=f"refresh_test_{int(datetime.now().timestamp())}",
                password="SecurePassword123!@#",
                name="Refresh Test User"
            )
            print(f"    User created: {user.user_id}")
            
            # 2. Create initial refresh token
            print("\n2  Creating initial refresh token...")
            chain_id = RefreshToken.generate_chain_id()
            
            token_jwt_1 = create_refresh_token_jwt(
                user_id=user.user_id,
                rotation_chain_id=chain_id,
                token_id="integration_test_1"
            )
            
            token_1 = await create_refresh_token(
                session=session,
                user_id=user.user_id,
                token_value=token_jwt_1,
                rotation_chain_id=chain_id,
                device_info="integration_test/1.0",
                ip_address="127.0.0.1"
            )
            print(f"    Token 1 created: {token_1.token_id[:8]}...")
            print(f"    Chain ID: {chain_id[:8]}...")
            
            # 3. Verify JWT
            print("\n3  Verifying JWT token...")
            payload = verify_refresh_token(token_jwt_1)
            assert payload["user_id"] == user.user_id
            assert payload["rotation_chain_id"] == chain_id
            print(f"    JWT verified: user_id={payload['user_id']}")
            
            # 4. Rotate token (first rotation)
            print("\n4  Rotating token (first rotation)...")
            token_jwt_2 = create_refresh_token_jwt(
                user_id=user.user_id,
                rotation_chain_id=chain_id,
                token_id="integration_test_2"
            )
            
            token_2, error = await rotate_refresh_token(
                session=session,
                old_token_value=token_jwt_1,
                new_token_value=token_jwt_2,
                device_info="integration_test/1.0",
                ip_address="127.0.0.1"
            )
            
            assert error is None, f"Rotation failed: {error}"
            assert token_2 is not None
            assert token_2.parent_token_id == token_1.token_id
            print(f"    Token 2 created: {token_2.token_id[:8]}...")
            print(f"    Parent link verified")
            
            # 5. Verify old token is marked as used
            print("\n5  Verifying old token is marked as used...")
            await session.refresh(token_1)
            assert token_1.used_at is not None
            assert token_1.is_reused()
            print(f"    Token 1 marked as used at {token_1.used_at}")
            
            # 6. Test reuse detection (security feature)
            print("\n6  Testing token reuse detection...")
            token_jwt_3 = create_refresh_token_jwt(
                user_id=user.user_id,
                rotation_chain_id=chain_id,
                token_id="integration_test_3"
            )
            
            token_3, error = await rotate_refresh_token(
                session=session,
                old_token_value=token_jwt_1,  # Reusing old token!
                new_token_value=token_jwt_3,
                device_info="attacker/1.0",
                ip_address="192.168.1.100"
            )
            
            assert error == "refresh_token_reused_chain_revoked", f"Expected reuse error, got: {error}"
            assert token_3 is None
            print(f"    Reuse detected and blocked")
            
            # 7. Verify entire chain is revoked
            print("\n7  Verifying chain revocation...")
            await session.refresh(token_1)
            await session.refresh(token_2)
            
            assert token_1.is_revoked
            assert token_2.is_revoked
            assert token_1.revocation_reason == "misuse_detected_token_reuse"
            assert token_2.revocation_reason == "misuse_detected_token_reuse"
            print(f"    Entire chain revoked (2 tokens)")
            
            # 8. Create new chain and test logout
            print("\n8  Testing logout (revoke all user tokens)...")
            new_chain_id = RefreshToken.generate_chain_id()
            
            token_jwt_4 = create_refresh_token_jwt(
                user_id=user.user_id,
                rotation_chain_id=new_chain_id,
                token_id="integration_test_4"
            )
            
            token_4 = await create_refresh_token(
                session=session,
                user_id=user.user_id,
                token_value=token_jwt_4,
                rotation_chain_id=new_chain_id,
                device_info="integration_test/1.0",
                ip_address="127.0.0.1"
            )
            
            revoked_count = await revoke_user_tokens(
                session=session,
                user_id=user.user_id,
                reason="user_logout"
            )
            
            print(f"    Revoked {revoked_count} tokens on logout")
            
            # 9. Verify no active tokens
            print("\n9  Verifying no active tokens remain...")
            active_tokens = await get_user_active_tokens(session, user.user_id)
            assert len(active_tokens) == 0
            print(f"    All tokens revoked")
            
            # Cleanup
            print("\n Cleaning up test data...")
            await session.delete(user)
            await session.commit()
            print(f"    Test user deleted")
            
            print("\n All integration tests passed!\n")
            print("=" * 60)
            print(" Refresh token rotation is working correctly!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"\n Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.close()


if __name__ == "__main__":
    result = asyncio.run(test_refresh_token_integration())
    exit(0 if result else 1)
