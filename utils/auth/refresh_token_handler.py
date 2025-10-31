"""
Refresh Token JWT Handler

Handles creation and verification of JWT-based refresh tokens.
Refresh tokens are:
- Longer-lived than access tokens (7 days default vs 15 minutes)
- Stored in httpOnly cookies
- Single-use with rotation
- Tracked in database for revocation
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status

from utils.monitoring import get_logger

logger = get_logger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError(
        "SECRET_KEY environment variable is required and must be at least 32 characters long. "
        "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

ALGORITHM = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_refresh_token(
    user_id: str,
    rotation_chain_id: str,
    token_id: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Refresh tokens contain:
    - user_id: User identifier
    - token_id: Database token ID for tracking
    - rotation_chain_id: Chain ID for revocation
    - type: "refresh" to distinguish from access tokens
    - jti: Unique token identifier (random)
    - exp: Expiration timestamp
    - iat: Issued at timestamp
    
    Args:
        user_id: User ID
        rotation_chain_id: Rotation chain ID
        token_id: Database token ID
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT refresh token
    """
    to_encode = {
        "user_id": user_id,
        "token_id": token_id,
        "rotation_chain_id": rotation_chain_id,
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),  # JWT ID for additional uniqueness
    }
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.debug(f"🔑 Created refresh token for user {user_id}, chain {rotation_chain_id[:8]}...")
    return encoded_jwt


def verify_refresh_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT refresh token.
    
    Validates:
    - Token signature
    - Token expiration
    - Token type (must be "refresh")
    
    Args:
        token: JWT refresh token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid, expired, or wrong type
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        token_type = payload.get("type")
        if token_type != "refresh":
            logger.warning(f"⚠️ Wrong token type: {token_type}, expected 'refresh'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Verify required fields
        user_id = payload.get("user_id")
        token_id = payload.get("token_id")
        rotation_chain_id = payload.get("rotation_chain_id")
        
        if not all([user_id, token_id, rotation_chain_id]):
            logger.warning("⚠️ Refresh token missing required fields")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        logger.debug(f"✅ Verified refresh token for user {user_id}")
        return payload
        
    except JWTError as e:
        logger.warning(f"⚠️ JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate refresh token: {str(e)}"
        )


def extract_user_id_from_refresh_token(token: str) -> Optional[str]:
    """
    Extract user ID from refresh token without full verification.
    
    Useful for logging/debugging. Does NOT validate signature or expiration.
    
    Args:
        token: JWT refresh token string
    
    Returns:
        User ID or None if extraction fails
    """
    try:
        # Decode without verification (for info only)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})
        return payload.get("user_id")
    except Exception:
        return None


def generate_refresh_token_value() -> str:
    """
    Generate a random refresh token value.
    
    This can be used as an alternative to JWT if you prefer opaque tokens.
    For this implementation, we use JWT for stateless verification.
    
    Returns:
        Random URL-safe token string
    """
    return secrets.token_urlsafe(64)
