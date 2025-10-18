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
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            logger.warning("Password longer than 72 bytes, truncating for bcrypt")
            password = password_bytes[:72].decode('utf-8', errors='ignore')
    
    try:
        return pwd_context.hash(password)
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
    try:
        return pwd_context.verify(plain_password, hashed_password)
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

