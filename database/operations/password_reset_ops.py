"""
Password Reset Token Operations

Database operations for managing password reset tokens.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Optional
import secrets
import logging
from datetime import datetime, timedelta, timezone

from database.models.password_reset_token import PasswordResetToken
from config.settings import settings

logger = logging.getLogger(__name__)


def generate_reset_token() -> str:
    """
    Generate a secure random token for password reset.
    
    Returns:
        Secure random token string (64 characters)
    """
    return secrets.token_urlsafe(48)


async def create_reset_token(
    session: AsyncSession,
    email: str
) -> Optional[PasswordResetToken]:
    """
    Create a new password reset token.
    
    Args:
        session: Database session
        email: User email address
    
    Returns:
        Created PasswordResetToken or None on error
    """
    try:
        # Generate unique token
        token = generate_reset_token()
        
        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.password_reset_token_expire_hours
        )
        
        # Create token record
        reset_token = PasswordResetToken(
            email=email,
            token=token,
            is_used=False,
            expires_at=expires_at
        )
        
        session.add(reset_token)
        await session.commit()
        await session.refresh(reset_token)
        
        logger.info(f"✅ Password reset token created for: {email}")
        return reset_token
        
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error creating reset token for {email}: {e}")
        return None


async def get_valid_reset_token(
    session: AsyncSession,
    token: str,
    email: str
) -> Optional[PasswordResetToken]:
    """
    Get a valid (not used, not expired) reset token.
    
    Args:
        session: Database session
        token: Reset token string
        email: User email address
    
    Returns:
        PasswordResetToken if valid, None otherwise
    """
    try:
        now = datetime.now(timezone.utc)
        
        result = await session.execute(
            select(PasswordResetToken).where(
                and_(
                    PasswordResetToken.token == token,
                    PasswordResetToken.email == email,
                    PasswordResetToken.is_used == False,
                    PasswordResetToken.expires_at > now
                )
            )
        )
        
        reset_token = result.scalars().first()
        
        if reset_token:
            logger.debug(f"✅ Valid reset token found for: {email}")
        else:
            logger.debug(f"⚠️  No valid reset token found for: {email}")
        
        return reset_token
        
    except Exception as e:
        logger.error(f"❌ Error fetching reset token: {e}")
        return None


async def mark_token_as_used(
    session: AsyncSession,
    token_id: int
) -> bool:
    """
    Mark a reset token as used.
    
    Args:
        session: Database session
        token_id: Token ID
    
    Returns:
        True if successful, False otherwise
    """
    try:
        result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.id == token_id)
        )
        reset_token = result.scalars().first()
        
        if not reset_token:
            logger.warning(f"⚠️  Reset token not found: {token_id}")
            return False
        
        reset_token.is_used = True
        reset_token.used_at = datetime.now(timezone.utc)
        
        await session.commit()
        logger.info(f"✅ Reset token marked as used: {token_id}")
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error marking token as used: {e}")
        return False


async def delete_expired_tokens(session: AsyncSession) -> int:
    """
    Delete all expired reset tokens (cleanup).
    
    Args:
        session: Database session
    
    Returns:
        Number of deleted tokens
    """
    try:
        now = datetime.now(timezone.utc)
        
        result = await session.execute(
            select(PasswordResetToken).where(
                or_(
                    PasswordResetToken.expires_at < now,
                    PasswordResetToken.is_used == True
                )
            )
        )
        
        tokens_to_delete = result.scalars().all()
        count = len(tokens_to_delete)
        
        for token in tokens_to_delete:
            await session.delete(token)
        
        await session.commit()
        logger.info(f"✅ Deleted {count} expired/used reset tokens")
        return count
        
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error deleting expired tokens: {e}")
        return 0


__all__ = [
    'generate_reset_token',
    'create_reset_token',
    'get_valid_reset_token',
    'mark_token_as_used',
    'delete_expired_tokens'
]

