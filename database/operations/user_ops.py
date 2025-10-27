"""
User Database Operations

CRUD operations for user management with PostgreSQL.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from typing import Optional, Dict
import logging
from datetime import datetime, timezone

from database.models.user import User
from utils.auth.password import hash_password, verify_password

logger = logging.getLogger(__name__)


async def create_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
    role: str = "student",
    **kwargs
) -> Optional[User]:
    """
    Create a new user.
    
    Args:
        session: Database session
        email: User email
        username: Username
        password: Plain text password (will be hashed)
        role: User role (student, teacher, admin)
        **kwargs: Additional user fields
    
    Returns:
        Created user or None if email/username already exists
    """
    try:
        # Hash password using bcrypt
        hashed_password = await hash_password(password)
        
        # SECURITY: Password hash is stored in dedicated column, not in settings JSONB
        # Settings JSONB should only contain user preferences, NOT sensitive data
        user_settings = kwargs.get('settings', {})
        
        # Create user
        user = User(
            user_id=email,  # Use email as user_id for now
            email=email,
            username=username,
            role=role,
            name=kwargs.get('name', ''),  # Full name field
            first_name=kwargs.get('first_name', ''),
            last_name=kwargs.get('last_name', ''),
            display_name=kwargs.get('display_name', username),
            profile_picture=kwargs.get('profile_picture'),
            location=kwargs.get('location'),
            website=kwargs.get('website'),
            password_hash=hashed_password,  # Dedicated password hash column
            settings=user_settings,  # User preferences only (no sensitive data)
            is_active=True
        )
        
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        logger.info(f"✅ User created: {username} ({email})")
        return user
        
    except IntegrityError as e:
        await session.rollback()
        logger.warning(f"⚠️  User creation failed (duplicate): {email}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ User creation error: {e}")
        return None


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """
    Get user by email.
    
    Args:
        session: Database session
        email: User email
    
    Returns:
        User or None if not found
    """
    try:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"❌ Error fetching user by email: {e}")
        return None


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """
    Get user by username.
    
    Args:
        session: Database session
        username: Username
    
    Returns:
        User or None if not found
    """
    try:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"❌ Error fetching user by username: {e}")
        return None


async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    """
    Get user by user_id.
    
    Args:
        session: Database session
        user_id: User ID
    
    Returns:
        User or None if not found
    """
    try:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"❌ Error fetching user by ID: {e}")
        return None


async def authenticate_user(
    session: AsyncSession,
    username: str,
    password: str
) -> Optional[User]:
    """
    Authenticate user with username/email and password.
    
    Args:
        session: Database session
        username: Username or email
        password: Plain text password
    
    Returns:
        User if authenticated, None otherwise
    """
    try:
        # Try email first
        user = await get_user_by_email(session, username)
        
        # Try username if not found by email
        if not user:
            user = await get_user_by_username(session, username)
        
        if not user:
            logger.debug(f"🔍 User not found: {username}")
            return None
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"⚠️  Inactive user attempted login: {username}")
            return None
        
        # Verify password from dedicated column
        # SECURITY: Password hash is in dedicated column, not settings JSONB
        if not user.password_hash:
            # Try fallback to settings for backward compatibility (migration period)
            password_hash = user.settings.get('password_hash') if user.settings else None
            if not password_hash:
                logger.error(f"❌ No password hash for user: {username}")
                return None
        else:
            password_hash = user.password_hash
        
        if not await verify_password(password, password_hash):
            logger.debug(f"🔐 Invalid password for user: {username}")
            return None
        
        # Update last active
        await update_user_activity(session, user.user_id)
        
        logger.info(f"✅ User authenticated: {username}")
        return user
        
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        return None


async def update_user_activity(session: AsyncSession, user_id: str) -> bool:
    """
    Update user's last active timestamp.
    
    Args:
        session: Database session
        user_id: User ID
    
    Returns:
        True if updated successfully
    """
    try:
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(last_active=datetime.now(timezone.utc))
        )
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Error updating user activity: {e}")
        await session.rollback()
        return False


async def update_user_profile(
    session: AsyncSession,
    user_id: str,
    **updates
) -> Optional[User]:
    """
    Update user profile.
    
    Args:
        session: Database session
        user_id: User ID
        **updates: Fields to update
    
    Returns:
        Updated user or None if not found
    """
    try:
        # Filter valid fields
        valid_fields = {
            'username', 'first_name', 'last_name', 'display_name',
            'profile_picture', 'location', 'website'
        }
        filtered_updates = {
            k: v for k, v in updates.items()
            if k in valid_fields and v is not None
        }
        
        if not filtered_updates:
            return await get_user_by_id(session, user_id)
        
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(**filtered_updates)
        )
        await session.commit()
        
        user = await get_user_by_id(session, user_id)
        logger.info(f"✅ User profile updated: {user_id}")
        return user
        
    except Exception as e:
        logger.error(f"❌ Error updating user profile: {e}")
        await session.rollback()
        return None


async def update_user_settings(
    session: AsyncSession,
    user_id: str,
    settings: Dict
) -> bool:
    """
    Update user settings.
    
    Args:
        session: Database session
        user_id: User ID
        settings: New settings (merged with existing)
    
    Returns:
        True if updated successfully
    """
    try:
        user = await get_user_by_id(session, user_id)
        if not user:
            return False
        
        # Merge settings
        current_settings = user.settings or {}
        updated_settings = {**current_settings, **settings}
        
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(settings=updated_settings)
        )
        await session.commit()
        
        logger.info(f"✅ User settings updated: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating user settings: {e}")
        await session.rollback()
        return False


async def change_user_password(
    session: AsyncSession,
    user_id: str,
    old_password: str,
    new_password: str
) -> bool:
    """
    Change user password.
    
    Args:
        session: Database session
        user_id: User ID
        old_password: Current password
        new_password: New password
    
    Returns:
        True if changed successfully
    """
    try:
        user = await get_user_by_id(session, user_id)
        if not user:
            return False
        
        # Verify old password from dedicated column
        # SECURITY: Use dedicated password_hash column
        password_hash = user.password_hash
        if not password_hash:
            # Fallback to settings for backward compatibility
            password_hash = user.settings.get('password_hash') if user.settings else None
        
        if not password_hash or not await verify_password(old_password, password_hash):
            logger.warning(f"⚠️  Invalid old password for user: {user_id}")
            return False
        
        # Hash new password
        new_hash = hash_password(new_password)
        
        # Update password in dedicated column
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(password_hash=new_hash)
        )
        await session.commit()
        
        logger.info(f"✅ Password changed for user: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error changing password: {e}")
        await session.rollback()
        return False


__all__ = [
    'create_user',
    'get_user_by_email',
    'get_user_by_username',
    'get_user_by_id',
    'authenticate_user',
    'update_user_activity',
    'update_user_profile',
    'update_user_settings',
    'change_user_password',
]

