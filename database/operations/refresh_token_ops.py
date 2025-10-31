"""
Refresh Token Database Operations

CRUD operations for refresh token rotation with server-side revocation.
Implements secure token rotation pattern with chain tracking.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import logging
import secrets

from database.models.refresh_token import RefreshToken
from utils.monitoring import get_logger

logger = get_logger(__name__)


async def create_refresh_token(
    session: AsyncSession,
    user_id: str,
    token_value: str,
    parent_token_id: Optional[str] = None,
    rotation_chain_id: Optional[str] = None,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
    expires_days: Optional[int] = None
) -> Optional[RefreshToken]:
    """
    Create a new refresh token.
    
    Args:
        session: Database session
        user_id: User ID
        token_value: The actual token value (JWT or random string)
        parent_token_id: Optional parent token ID for rotation chain
        rotation_chain_id: Optional rotation chain ID (generated if not provided)
        device_info: Optional device information
        ip_address: Optional IP address
        expires_days: Optional custom expiry in days
    
    Returns:
        Created refresh token or None if creation failed
    """
    try:
        # Generate rotation chain ID if this is the first token in chain
        if rotation_chain_id is None:
            rotation_chain_id = RefreshToken.generate_chain_id()
        
        # Create token record
        refresh_token = RefreshToken(
            token=token_value,
            user_id=user_id,
            parent_token_id=parent_token_id,
            rotation_chain_id=rotation_chain_id,
            expires_at=RefreshToken.create_expiry(expires_days),
            device_info=device_info,
            ip_address=ip_address,
            is_revoked=False
        )
        
        session.add(refresh_token)
        await session.commit()
        await session.refresh(refresh_token)
        
        logger.info(f"✅ Refresh token created for user {user_id}, chain {rotation_chain_id[:8]}...")
        return refresh_token
        
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"❌ Refresh token creation failed (integrity error): {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Refresh token creation error: {e}")
        return None


async def get_refresh_token(
    session: AsyncSession,
    token_value: str
) -> Optional[RefreshToken]:
    """
    Get refresh token by value.
    
    Args:
        session: Database session
        token_value: Token value to look up
    
    Returns:
        RefreshToken or None if not found
    """
    try:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token == token_value)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"❌ Error fetching refresh token: {e}")
        return None


async def get_refresh_token_by_id(
    session: AsyncSession,
    token_id: str
) -> Optional[RefreshToken]:
    """
    Get refresh token by ID.
    
    Args:
        session: Database session
        token_id: Token ID to look up
    
    Returns:
        RefreshToken or None if not found
    """
    try:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_id == token_id)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"❌ Error fetching refresh token by ID: {e}")
        return None


async def mark_token_used(
    session: AsyncSession,
    token_id: str
) -> bool:
    """
    Mark a refresh token as used (after successful rotation).
    
    Args:
        session: Database session
        token_id: Token ID to mark as used
    
    Returns:
        True if successful
    """
    try:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_id == token_id)
            .values(used_at=datetime.now(timezone.utc))
        )
        await session.commit()
        logger.debug(f"✅ Marked token {token_id[:8]}... as used")
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error marking token as used: {e}")
        return False


async def revoke_token(
    session: AsyncSession,
    token_id: str,
    reason: str = "manual_revocation"
) -> bool:
    """
    Revoke a single refresh token.
    
    Args:
        session: Database session
        token_id: Token ID to revoke
        reason: Reason for revocation
    
    Returns:
        True if successful
    """
    try:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_id == token_id)
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revocation_reason=reason
            )
        )
        await session.commit()
        logger.info(f"✅ Revoked token {token_id[:8]}... (reason: {reason})")
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error revoking token: {e}")
        return False


async def revoke_token_chain(
    session: AsyncSession,
    rotation_chain_id: str,
    reason: str = "chain_revocation"
) -> int:
    """
    Revoke entire refresh token rotation chain.
    
    This is the key security feature: when token reuse is detected,
    all tokens in the chain are revoked.
    
    Args:
        session: Database session
        rotation_chain_id: Chain ID to revoke
        reason: Reason for revocation
    
    Returns:
        Number of tokens revoked
    """
    try:
        result = await session.execute(
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.rotation_chain_id == rotation_chain_id,
                    RefreshToken.is_revoked == False
                )
            )
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revocation_reason=reason
            )
        )
        await session.commit()
        
        count = result.rowcount
        logger.warning(f"⚠️ Revoked entire token chain {rotation_chain_id[:8]}... ({count} tokens) - reason: {reason}")
        return count
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error revoking token chain: {e}")
        return 0


async def revoke_user_tokens(
    session: AsyncSession,
    user_id: str,
    reason: str = "user_logout"
) -> int:
    """
    Revoke all refresh tokens for a user (e.g., on logout).
    
    Args:
        session: Database session
        user_id: User ID
        reason: Reason for revocation
    
    Returns:
        Number of tokens revoked
    """
    try:
        result = await session.execute(
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc),
                revocation_reason=reason
            )
        )
        await session.commit()
        
        count = result.rowcount
        logger.info(f"✅ Revoked {count} refresh tokens for user {user_id} (reason: {reason})")
        return count
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error revoking user tokens: {e}")
        return 0


async def rotate_refresh_token(
    session: AsyncSession,
    old_token_value: str,
    new_token_value: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Tuple[Optional[RefreshToken], Optional[str]]:
    """
    Rotate a refresh token (create new, mark old as used).
    
    This is the core rotation operation:
    1. Verify old token is valid
    2. Check for reuse (security threat)
    3. Create new token linked to old one
    4. Mark old token as used
    
    Args:
        session: Database session
        old_token_value: Current refresh token value
        new_token_value: New refresh token value to create
        device_info: Optional device information
        ip_address: Optional IP address
    
    Returns:
        Tuple of (new_refresh_token, error_message)
        If error_message is not None, rotation failed
    """
    try:
        # Get old token
        old_token = await get_refresh_token(session, old_token_value)
        
        if not old_token:
            return None, "refresh_token_not_found"
        
        # Check if already revoked
        if old_token.is_revoked:
            logger.warning(f"⚠️ Attempted to use revoked token {old_token.token_id[:8]}...")
            return None, "refresh_token_revoked"
        
        # Check if expired
        if old_token.is_expired():
            logger.warning(f"⚠️ Attempted to use expired token {old_token.token_id[:8]}...")
            await revoke_token(session, old_token.token_id, "expired")
            return None, "refresh_token_expired"
        
        # CRITICAL SECURITY CHECK: Detect token reuse
        if old_token.is_reused():
            logger.error(
                f"🚨 SECURITY ALERT: Token reuse detected! "
                f"Token {old_token.token_id[:8]}... chain {old_token.rotation_chain_id[:8]}... "
                f"Revoking entire chain."
            )
            await revoke_token_chain(
                session, 
                old_token.rotation_chain_id, 
                "misuse_detected_token_reuse"
            )
            return None, "refresh_token_reused_chain_revoked"
        
        # Token is valid - create new token in rotation chain
        new_token = await create_refresh_token(
            session=session,
            user_id=old_token.user_id,
            token_value=new_token_value,
            parent_token_id=old_token.token_id,
            rotation_chain_id=old_token.rotation_chain_id,
            device_info=device_info,
            ip_address=ip_address
        )
        
        if not new_token:
            return None, "failed_to_create_new_token"
        
        # Mark old token as used
        await mark_token_used(session, old_token.token_id)
        
        logger.info(
            f"✅ Token rotated successfully for user {old_token.user_id}, "
            f"chain {old_token.rotation_chain_id[:8]}..."
        )
        
        return new_token, None
        
    except Exception as e:
        logger.error(f"❌ Error rotating refresh token: {e}")
        return None, "internal_error"


async def get_user_active_tokens(
    session: AsyncSession,
    user_id: str
) -> List[RefreshToken]:
    """
    Get all active (valid, non-revoked) refresh tokens for a user.
    
    Args:
        session: Database session
        user_id: User ID
    
    Returns:
        List of active refresh tokens
    """
    try:
        result = await session.execute(
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > datetime.now(timezone.utc)
                )
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"❌ Error fetching user active tokens: {e}")
        return []


async def cleanup_expired_tokens(
    session: AsyncSession,
    days_old: int = 30
) -> int:
    """
    Clean up expired and old refresh tokens.
    
    Args:
        session: Database session
        days_old: Delete tokens older than this many days
    
    Returns:
        Number of tokens deleted
    """
    try:
        from sqlalchemy import delete
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        result = await session.execute(
            delete(RefreshToken)
            .where(
                or_(
                    RefreshToken.expires_at < datetime.now(timezone.utc),
                    RefreshToken.created_at < cutoff_date
                )
            )
        )
        await session.commit()
        
        count = result.rowcount
        logger.info(f"🧹 Cleaned up {count} expired/old refresh tokens")
        return count
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error cleaning up expired tokens: {e}")
        return 0
