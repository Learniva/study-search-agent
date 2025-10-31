"""JWT token handling for authentication."""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt, ExpiredSignatureError
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Setup logging
logger = logging.getLogger(__name__)

# Configuration validation
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError(
        "SECRET_KEY environment variable is required and must be at least 32 characters long. "
        "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

# JWT algorithm - MUST match across all environments
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
if ALGORITHM not in ["HS256", "HS384", "HS512"]:
    logger.warning(f"JWT_ALGORITHM '{ALGORITHM}' is not recommended. Using HS256.")
    ALGORITHM = "HS256"

# Token expiration - configurable but with safe defaults
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
if ACCESS_TOKEN_EXPIRE_MINUTES < 5:
    logger.warning(f"ACCESS_TOKEN_EXPIRE_MINUTES is too short ({ACCESS_TOKEN_EXPIRE_MINUTES} min). Setting to 5 minutes.")
    ACCESS_TOKEN_EXPIRE_MINUTES = 5
elif ACCESS_TOKEN_EXPIRE_MINUTES > 1440:  # 24 hours
    logger.warning(f"ACCESS_TOKEN_EXPIRE_MINUTES is very long ({ACCESS_TOKEN_EXPIRE_MINUTES} min). Consider using refresh tokens.")

# Clock skew tolerance (in seconds) to handle minor time differences between servers
# Recommended: 60 seconds for normal deployments, 120 seconds for distributed systems
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "60"))
if JWT_LEEWAY_SECONDS < 0:
    logger.warning("JWT_LEEWAY_SECONDS cannot be negative. Setting to 0.")
    JWT_LEEWAY_SECONDS = 0
elif JWT_LEEWAY_SECONDS > 300:
    logger.warning(f"JWT_LEEWAY_SECONDS is very large ({JWT_LEEWAY_SECONDS}s). This may be a security risk.")

# Log configuration on startup
logger.info(f"JWT Configuration: ALGORITHM={ALGORITHM}, EXPIRE_MINUTES={ACCESS_TOKEN_EXPIRE_MINUTES}, LEEWAY={JWT_LEEWAY_SECONDS}s")

security = HTTPBearer()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token with 'exp' (expiration) and 'iat' (issued at) claims
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,  # Expiration time
        "iat": now,     # Issued at
        "nbf": now      # Not before (token valid from now)
    })
    
    # Log token creation (exclude sensitive data)
    logger.debug(f"Creating JWT token for user_id={data.get('user_id')} with expiry in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Validates:
    - Token signature using SECRET_KEY
    - Token expiration (exp claim) with clock skew tolerance
    - Token not used before valid time (nbf claim)
    
    Clock Skew Handling:
    Uses JWT_LEEWAY_SECONDS to tolerate minor time differences between
    client and server clocks. This prevents false positives from:
    - NTP sync delays
    - Server clock drift
    - Network latency
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid, expired, or signature doesn't match
    """
    try:
        # Decode and verify token with clock skew tolerance
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "require_exp": True,
                "leeway": JWT_LEEWAY_SECONDS  # Clock skew tolerance
            }
        )
        
        # Verify required claims exist
        if "user_id" not in payload or "email" not in payload:
            logger.warning("Token missing required claims (user_id or email)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except ExpiredSignatureError as e:
        # Token has expired (even with leeway)
        logger.info(f"Token expired for request (beyond {JWT_LEEWAY_SECONDS}s leeway)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
        
    except JWTError as e:
        # Invalid signature, malformed token, or other JWT error
        logger.warning(f"JWT validation failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get the current authenticated user from the JWT token.
    
    Args:
        credentials: HTTP Bearer credentials with JWT token
        
    Returns:
        User data from token
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    payload = verify_access_token(token)
    
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    if user_id is None or email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    return payload


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict[str, Any]]:
    """
    Get the current user if authenticated, otherwise return None.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        
    Returns:
        User data or None
    """
    if credentials is None:
        return None
    
    try:
        return verify_access_token(credentials.credentials)
    except HTTPException:
        return None


def validate_jwt_config() -> Dict[str, Any]:
    """
    Validate JWT configuration for consistency across environments.
    
    This function should be called on application startup to ensure
    JWT configuration is correct and consistent.
    
    Returns:
        Dictionary with configuration details and validation status
    """
    config_status = {
        "valid": True,
        "algorithm": ALGORITHM,
        "expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "secret_key_length": len(SECRET_KEY) if SECRET_KEY else 0,
        "warnings": [],
        "errors": []
    }
    
    # Validate SECRET_KEY
    if not SECRET_KEY:
        config_status["valid"] = False
        config_status["errors"].append("SECRET_KEY is not set")
    elif len(SECRET_KEY) < 32:
        config_status["valid"] = False
        config_status["errors"].append(f"SECRET_KEY too short ({len(SECRET_KEY)} chars, minimum 32)")
    elif len(SECRET_KEY) < 64:
        config_status["warnings"].append(f"SECRET_KEY could be longer (current: {len(SECRET_KEY)} chars, recommended: 64+)")
    
    # Validate ALGORITHM
    if ALGORITHM not in ["HS256", "HS384", "HS512", "RS256"]:
        config_status["warnings"].append(f"Unusual JWT algorithm: {ALGORITHM}")
    
    # Validate expiration time
    if ACCESS_TOKEN_EXPIRE_MINUTES < 5:
        config_status["warnings"].append(f"Very short token lifetime: {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    elif ACCESS_TOKEN_EXPIRE_MINUTES > 1440:
        config_status["warnings"].append(f"Very long token lifetime: {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    
    # Log validation results
    if config_status["valid"]:
        logger.info(f"JWT configuration valid: {ALGORITHM}, {ACCESS_TOKEN_EXPIRE_MINUTES} min expiry")
        if config_status["warnings"]:
            logger.warning(f"JWT configuration warnings: {', '.join(config_status['warnings'])}")
    else:
        logger.error(f"JWT configuration invalid: {', '.join(config_status['errors'])}")
    
    return config_status


# Validate configuration on module load
_config_status = validate_jwt_config()
if not _config_status["valid"]:
    raise ValueError(f"Invalid JWT configuration: {', '.join(_config_status['errors'])}")
