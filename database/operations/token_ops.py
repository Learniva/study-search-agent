"""
Token Database Operations

CRUD operations for PostgreSQL-based token management.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError
from typing import Optional
import secrets
import logging
from datetime import datetime, timezone

from database.models.token import Token

logger = logging.getLogger(__name__)


async def create_token(
    session: AsyncSession,
    user_id: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Optional[Token]:
    """
    Create a new authentication token.
    
    Args:
        session: Database session
        user_id: User ID
        device_info: Optional device information
        ip_address: Optional IP address
    
    Returns:
        Created token or None if creation failed
    """
    try:
        # Generate secure random token
        token_value = secrets.token_urlsafe(48)
        
        # Create token record
        token = Token(
            token=token_value,
            user_id=user_id,
            expires_at=Token.create_expiry(),
            device_info=device_info,
            ip_address=ip_address,
            is_active=True
        )
        
        session.add(token)
        await session.commit()
        await session.refresh(token)
        
        logger.info(f"✅ Token created for user: {user_id}")
        return token
        
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"❌ Token creation failed (integrity error): {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Token creation error: {e}")
        return None


async def get_token(
    session: AsyncSession,
    token_value: str
) -> Optional[Token]:
    """
    Get token by value.
    
    Args:
        session: Database session
        token_value: Token value
    
    Returns:
        Token or None if not found
    """
    try:
        result = await session.execute(
            select(Token).where(Token.token == token_value)
        )
        token = result.scalars().first()
        
        if token and token.is_valid():
            # Update last_used timestamp
            token.last_used = datetime.now(timezone.utc)
            await session.commit()
            return token
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Error fetching token: {e}")
        return None


async def get_user_tokens(
    session: AsyncSession,
    user_id: str,
    active_only: bool = True
) -> list[Token]:
    """
    Get all tokens for a user.
    
    Args:
        session: Database session
        user_id: User ID
        active_only: Only return active, non-expired tokens
    
    Returns:
        List of tokens
    """
    try:
        query = select(Token).where(Token.user_id == user_id)
        
        if active_only:
            query = query.where(
                Token.is_active == True,
                Token.expires_at > datetime.now(timezone.utc)
            )
        
        result = await session.execute(query)
        return list(result.scalars().all())
        
    except Exception as e:
        logger.error(f"❌ Error fetching user tokens: {e}")
        return []


async def delete_token(
    session: AsyncSession,
    token_value: str
) -> bool:
    """
    Delete (invalidate) a token.
    
    Args:
        session: Database session
        token_value: Token value
    
    Returns:
        True if deleted successfully
    """
    try:
        result = await session.execute(
            delete(Token).where(Token.token == token_value)
        )
        await session.commit()
        
        if result.rowcount > 0:
            logger.info(f"✅ Token deleted: {token_value[:8]}...")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error deleting token: {e}")
        await session.rollback()
        return False


async def delete_user_tokens(
    session: AsyncSession,
    user_id: str
) -> int:
    """
    Delete all tokens for a user.
    
    Args:
        session: Database session
        user_id: User ID
    
    Returns:
        Number of tokens deleted
    """
    try:
        result = await session.execute(
            delete(Token).where(Token.user_id == user_id)
        )
        await session.commit()
        
        count = result.rowcount
        logger.info(f"✅ Deleted {count} tokens for user: {user_id}")
        return count
        
    except Exception as e:
        logger.error(f"❌ Error deleting user tokens: {e}")
        await session.rollback()
        return 0


async def cleanup_expired_tokens(session: AsyncSession) -> int:
    """
    Delete all expired tokens.
    
    Args:
        session: Database session
    
    Returns:
        Number of tokens deleted
    """
    try:
        result = await session.execute(
            delete(Token).where(Token.expires_at < datetime.now(timezone.utc))
        )
        await session.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info(f"🧹 Cleaned up {count} expired tokens")
        return count
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up expired tokens: {e}")
        await session.rollback()
        return 0


__all__ = [
    'create_token',
    'get_token',
    'get_user_tokens',
    'delete_token',
    'delete_user_tokens',
    'cleanup_expired_tokens',
]

