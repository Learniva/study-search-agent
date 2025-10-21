"""
Password Hashing Utilities

Secure password hashing using bcrypt.
"""

from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)

# Password context with bcrypt
# Use explicit rounds to avoid compatibility issues
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Explicit rounds for compatibility
    bcrypt__ident="2b"  # Use 2b variant for better compatibility
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    
    Note:
        Bcrypt has a 72-byte limit. Passwords longer than that will be truncated.
    """
    # Bcrypt has a 72-byte limit, truncate if necessary
    # Convert to bytes and truncate before hashing
    password_bytes = password.encode('utf-8')[:72]
    
    try:
        # Use bcrypt directly to avoid passlib compatibility issues
        import bcrypt
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
    
    Returns:
        True if password matches, False otherwise
    """
    # Bcrypt has a 72-byte limit, truncate if necessary (same as hash_password)
    password_bytes = plain_password.encode('utf-8')[:72]
    
    try:
        # Use bcrypt directly to avoid passlib compatibility issues
        import bcrypt
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"❌ Password verification error: {e}")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be updated.
    
    Args:
        hashed_password: Hashed password to check
    
    Returns:
        True if hash needs update, False otherwise
    """
    return pwd_context.needs_update(hashed_password)


__all__ = ['hash_password', 'verify_password', 'needs_rehash']

