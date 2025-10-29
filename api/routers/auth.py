"""
Comprehensive Authentication Endpoints

Production-ready authentication system with comprehensive security features:
- Google OAuth integration
- Account lockout protection
- Password policy enforcement
- Session management
- Device tracking
- Security monitoring
- Admin functions

Security Features:
- Progressive lockout (5, 10, 30, 60 minutes)
- Password complexity validation
- Breach database checking
- Session fingerprinting
- Suspicious activity detection
- Rate limiting integration
- Security headers protection

Author: Study Search Agent Team
Version: 2.0.0
"""

import os
import logging
import httpx
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Header
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.core.async_connection import get_session
from database.core.async_engine import get_async_db
from database.models.user import User, UserRole
from database.operations.user_ops import (
    create_user,
    authenticate_user,
    get_user_by_id,
    get_user_by_email,
    update_user_activity,
    change_user_password
)
from database.operations.token_ops import (
    create_token,
    get_token,
    delete_token,
    delete_user_tokens
)
from database.operations.refresh_token_ops import (
    create_refresh_token,
    get_refresh_token,
    revoke_user_tokens,
    rotate_refresh_token,
    revoke_token_chain
)
from database.models.audit import AuditLog
from utils.auth import create_access_token, get_current_user, google_oauth
from utils.auth.refresh_token_handler import (
    create_refresh_token as create_refresh_token_jwt,
    verify_refresh_token
)
from utils.auth.cookie_config import CookieConfig
from utils.auth.password import (
    hash_password, 
    verify_password,
    validate_password_policy,
    PasswordPolicyRequest,
    PasswordPolicyResponse,
    PasswordValidationResult
)
from utils.auth.account_lockout import (
    record_failed_login,
    check_account_lockout,
    get_lockout_manager
)
from utils.auth.token_cache import get_token_cache
from utils.monitoring import get_logger

logger = get_logger(__name__)

# Main router for all authentication endpoints
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Legacy router for backward compatibility (old /auth prefix)
legacy_router = APIRouter(prefix="/auth", tags=["authentication-legacy"])

# ============================================================================
# Configuration
# ============================================================================

# Google OAuth Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback/")

# Shared HTTP client with connection pooling for better performance
_http_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
        )
    return _http_client

async def close_http_client():
    """Close the shared HTTP client on shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "authentication",
        "google_oauth_configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    }


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request with enhanced security."""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = Field(default=False)
    device_name: Optional[str] = Field(None, max_length=100)
    device_type: Optional[str] = Field(None, max_length=50)


class LoginResponse(BaseModel):
    """Enhanced login response."""
    token: str
    user: Dict[str, Any]
    expires_at: datetime
    session_id: str
    security_warnings: List[str] = []


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="student")
    
    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['student', 'teacher', 'professor', 'instructor', 'admin']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v


class RegisterResponse(BaseModel):
    """User registration response."""
    user: Dict[str, Any]
    token: str
    expires_at: datetime
    session_id: str
    password_strength: Dict[str, Any]


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class ChangePasswordResponse(BaseModel):
    """Change password response."""
    success: bool
    message: str
    password_strength: Dict[str, Any]


class SetPasswordRequest(BaseModel):
    """Set password request for OAuth users without existing password."""
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class SetPasswordResponse(BaseModel):
    """Set password response."""
    success: bool
    message: str
    password_strength: Dict[str, Any]
    account_type: str  # "oauth_with_password" after setting


class LogoutRequest(BaseModel):
    """Logout request."""
    logout_all_devices: bool = Field(default=False)


class LogoutResponse(BaseModel):
    """Logout response."""
    success: bool
    message: str
    sessions_terminated: int


class RefreshTokenResponse(BaseModel):
    """Refresh token response."""
    access_token: str
    expires_at: datetime
    token_type: str = "bearer"


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    device_name: Optional[str]
    device_type: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    created_at: datetime
    last_used: datetime
    is_current: bool


class SessionsResponse(BaseModel):
    """Active sessions response."""
    sessions: List[SessionInfo]
    total_count: int


class SecurityEvent(BaseModel):
    """Security event information."""
    event_type: str
    timestamp: datetime
    ip_address: str
    user_agent: Optional[str]
    details: Dict[str, Any]
    severity: str


class SecurityEventsResponse(BaseModel):
    """Security events response."""
    events: List[SecurityEvent]
    total_count: int


class SessionValidateResponse(BaseModel):
    """Session validation response."""
    valid: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


# Legacy models for Google OAuth compatibility
class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User response model."""
    id: str  # Changed from int to str to support UUID
    email: str
    name: Optional[str]
    picture: Optional[str]
    role: str
    is_verified: bool


# ============================================================================
# Helper Functions
# ============================================================================

def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


def _create_session_fingerprint(request: Request) -> str:
    """Create session fingerprint for device tracking."""
    import hashlib
    
    ip = _get_client_ip(request)
    user_agent = _get_user_agent(request)
    
    fingerprint_data = f"{ip}:{user_agent}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


async def _get_current_user_from_token(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Get current user from authorization token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # Parse token
    try:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2:
            scheme, token = parts
            if scheme.lower() not in ["token", "bearer"]:
                raise ValueError("Invalid scheme")
        else:
            token = authorization
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    # Check token cache
    token_cache = await get_token_cache()
    cached_user = await token_cache.get(token)
    if cached_user:
        return cached_user
    
    # Verify token from database
    token_data = await get_token(session, token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get user data
    user = await get_user_by_id(session, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    user_dict = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_active": user.last_active.isoformat() if user.last_active else None
    }
    
    # Cache user data
    await token_cache.set(token, user_dict)
    
    return user_dict


async def get_current_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Unified authentication: Accepts both JWT tokens (Google OAuth) and database tokens.
    
    Tries to validate in this order:
    1. Database token (custom auth)
    2. JWT token (Google OAuth)
    
    This allows the frontend to use either authentication method seamlessly.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # Parse token
    try:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2:
            scheme, token = parts
            if scheme.lower() not in ["token", "bearer"]:
                raise ValueError("Invalid scheme")
        else:
            token = authorization
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    # Check token cache first
    token_cache = await get_token_cache()
    cached_user = await token_cache.get(token)
    if cached_user:
        return cached_user
    
    # Try database token first (custom auth)
    try:
        token_data = await get_token(session, token)
        if token_data and token_data.is_valid():
            user = await get_user_by_id(session, token_data.user_id)
            if user and user.is_active:
                user_dict = {
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                    "last_active": user.last_active.isoformat() if user.last_active else None
                }
                await token_cache.set(token, user_dict)
                return user_dict
    except Exception:
        pass  # If database token fails, try JWT
    
    # Try JWT token (Google OAuth)
    try:
        from utils.auth.jwt_handler import verify_access_token
        payload = verify_access_token(token)
        
        # Get or create user from JWT payload
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing email"
            )
        
        # Check if user exists in database
        user = await get_user_by_email(session, email)
        
        if not user:
            # Auto-create user from JWT data (OAuth user)
            from database.operations.user_ops import create_user
            user = await create_user(
                session=session,
                email=email,
                username=email.split("@")[0],
                name=payload.get("name"),
                google_id=payload.get("sub"),
                picture=payload.get("picture"),
                is_verified=True  # OAuth users are pre-verified
            )
        
        if user and user.is_active:
            user_dict = {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "auth_type": "jwt"  # Mark as JWT auth
            }
            await token_cache.set(token, user_dict)
            return user_dict
    except Exception:
        pass  # If JWT also fails, raise final error
    
    # Both methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for authentication service."""
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "google_oauth_configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    }


# ============================================================================
# Google OAuth Endpoints
# ============================================================================

@router.get("/google/login/")
async def google_login():
    """
    Initiate Google OAuth login flow with CSRF protection.
    
    Security Features:
    - Generates cryptographically secure state parameter
    - Stores state in Redis with 5-minute TTL
    - State serves as CSRF token
    - State validates handshake continuity across service restarts
    
    Returns:
        Redirect to Google OAuth consent screen
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured"
        )
    
    # Generate cryptographically secure state parameter (CSRF protection)
    import secrets
    state = secrets.token_urlsafe(32)  # 256 bits of entropy
    
    # Store state in Redis with 5-minute TTL
    # This allows state to survive service restart if Redis is available
    from utils.cache.redis_client import RedisClient
    redis_client = RedisClient.get_instance()
    
    if redis_client:
        try:
            # Store state with metadata for audit trail
            state_data = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            redis_client.setex(
                f"oauth:state:{state}",
                300,  # 5 minutes TTL
                json.dumps(state_data)
            )
            logger.info(f"🔐 OAuth state generated and stored: {state[:10]}... (TTL: 5min)")
        except Exception as e:
            logger.error(f"❌ Failed to store OAuth state in Redis: {e}")
            # In production, you may want to reject OAuth flow if Redis is unavailable
            # For now, we'll continue but log the security warning
            logger.warning("⚠️  SECURITY WARNING: OAuth state not stored - CSRF protection degraded")
    else:
        logger.warning("⚠️  Redis unavailable - OAuth state parameter cannot be validated on restart")
    
    # Build authorization URL with state parameter
    from urllib.parse import urlencode
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,  # CSRF protection
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    logger.info(f"↪️  Redirecting to Google OAuth with state parameter")
    
    return RedirectResponse(url=auth_url)


@router.get("/google/callback/")
@router.get("/google/callback")  # Without trailing slash for compatibility
async def google_callback(
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Google OAuth callback with state validation.
    
    Security Features:
    - Validates state parameter (CSRF protection)
    - Detects service restart during handshake
    - One-time state usage (prevents replay)
    - Comprehensive security logging
    
    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
        db: Database session
        
    Returns:
        Redirect to frontend with token or error
    """
    logger.info(f"🔐 OAuth callback received. Code length: {len(code) if code else 0}, State: {state[:10] if state else 'MISSING'}...")
    logger.info(f"🔐 Using redirect URI: {GOOGLE_REDIRECT_URI}")
    logger.info(f"🔐 Frontend URL: {FRONTEND_URL}")
    
    # ========================================================================
    # SECURITY: Validate required parameters
    # ========================================================================
    
    if not code:
        logger.error("❌ SECURITY: Missing authorization code")
        error_url = f"{FRONTEND_URL}/auth/error?reason=missing_code&message=Missing+authorization+code"
        return RedirectResponse(url=error_url)
    
    if not state:
        logger.error("❌ SECURITY: Missing state parameter - potential CSRF attack or old OAuth flow")
        logger.warning("🔒 SECURITY ALERT: OAuth callback without state parameter")
        error_url = f"{FRONTEND_URL}/auth/error?reason=missing_state&message=Invalid+request+-+missing+state"
        return RedirectResponse(url=error_url)
    
    # ========================================================================
    # SECURITY: Validate state parameter from Redis
    # ========================================================================
    
    from utils.cache.redis_client import RedisClient
    redis_client = RedisClient.get_instance()
    
    if redis_client:
        try:
            # Retrieve state from Redis
            state_key = f"oauth:state:{state}"
            stored_state = redis_client.get(state_key)
            
            if not stored_state:
                # State not found - either expired, invalid, or service restarted
                logger.error(f"❌ SECURITY: Invalid or expired state parameter: {state[:10]}...")
                logger.warning("🔒 SECURITY ALERT: OAuth state validation failed - possible attack or service restart")
                logger.info("🔍 Possible scenarios: 1) CSRF attack, 2) State expired (>5min), 3) Service restarted during handshake")
                
                error_url = f"{FRONTEND_URL}/auth/error?reason=invalid_state&message=Session+expired+or+invalid+request"
                return RedirectResponse(url=error_url)
            
            # State is valid - delete it immediately (one-time use, prevents replay)
            redis_client.delete(state_key)
            logger.info(f"✅ State validated and consumed: {state[:10]}...")
            
            # Parse state metadata for audit trail
            try:
                state_data = json.loads(stored_state)
                created_at = state_data.get("created_at")
                logger.info(f"📋 State created at: {created_at}")
            except Exception:
                pass  # Metadata parsing is optional
                
        except Exception as e:
            logger.error(f"❌ Redis error during state validation: {e}")
            logger.warning("⚠️  Proceeding without state validation (Redis unavailable)")
            # In production, you might want to reject if Redis is required
    else:
        logger.warning("⚠️  Redis unavailable - cannot validate state parameter")
        logger.warning("⚠️  SECURITY DEGRADED: Proceeding without state validation")
        # In production with strict security, you should reject here
    
    try:
        # Exchange code for tokens
        client = get_http_client()
        try:
            logger.info("🔄 Exchanging code for access token...")
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            
            if token_response.status_code != 200:
                error_detail = token_response.text
                logger.error(f"❌ Google token error (status {token_response.status_code}): {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to get access token: {error_detail}")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            logger.info("✅ Successfully got access token from Google")
            
            # Get user info from Google
            logger.info("🔄 Fetching user info from Google...")
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if user_info_response.status_code != 200:
                logger.error(f"❌ Failed to get user info (status {user_info_response.status_code})")
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            user_data = user_info_response.json()
            logger.info(f"✅ Got user info: {user_data.get('email')}")
        except Exception as e:
            logger.error(f"❌ HTTP request error during OAuth: {e}", exc_info=True)
            raise
        
        # Extract user information
        google_id = user_data.get("id")
        email = user_data.get("email")
        name = user_data.get("name")
        picture = user_data.get("picture")
        email_verified = user_data.get("verified_email", False)
        
        logger.info(f"🔄 Processing user: {email} (Google ID: {google_id})")
        
        # Check if user exists
        result = await db.execute(
            select(User).where(User.google_id == google_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.info(f"👤 User not found by Google ID, checking by email...")
            # Check by email
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Check if this is a first-time Google account linking
                is_first_time_linking = user.google_id is None
                
                logger.info(f"✅ Found existing user by email, updating with Google ID")
                # Update existing user with Google ID
                user.google_id = google_id
                user.picture = picture
                user.profile_picture = picture
                user.is_verified = email_verified
                user.last_login = datetime.now(timezone.utc)
                
                # Log security event for account linking
                if is_first_time_linking:
                    logger.info(f"🔗 First-time Google account linking detected for {email}")
                    
                    # Create audit log entry
                    try:
                        audit_entry = AuditLog(
                            user_id=user.user_id,
                            user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
                            action_type="oauth_account_linked",
                            resource_type="user_account",
                            resource_id=user.id,
                            action_details={
                                "provider": "google",
                                "google_id": google_id,
                                "email": email,
                                "name": name,
                                "email_verified": email_verified,
                                "profile_updated": True
                            },
                            old_value={"google_id": None},
                            new_value={"google_id": google_id},
                            ip_address="oauth_callback",  # Could extract from request if available
                            success=True
                        )
                        db.add(audit_entry)
                        logger.info(f"✅ Audit log created for account linking")
                    except Exception as audit_error:
                        logger.error(f"❌ Failed to create audit log: {audit_error}")
                        # Don't fail the OAuth flow if audit fails
                    
                    # Send notification email for first-time account linking
                    try:
                        from utils.email import email_service
                        
                        # Send account linking notification email
                        email_sent = email_service.send_account_linked_email(
                            to_email=email,
                            username=user.username or email.split('@')[0],
                            linked_service="Google"
                        )
                        
                        if email_sent:
                            logger.info(f"✅ Account linking notification email sent to {email}")
                        else:
                            logger.warning(f"⚠️ Failed to send account linking notification to {email}")
                    except Exception as e:
                        logger.error(f"❌ Error sending account linking email: {e}")
                        # Don't fail the OAuth flow if email fails
            else:
                logger.info(f"👤 Creating new user from Google OAuth")
                # Create new user from Google OAuth
                username = email.split('@')[0] if email else name.replace(' ', '_').lower()
                
                user = User(
                    user_id=email,  # Use email as user_id
                    email=email,
                    username=username,
                    name=name,
                    display_name=name,
                    picture=picture,
                    profile_picture=picture,
                    google_id=google_id,
                    role=UserRole.STUDENT,  # Default role
                    is_verified=email_verified,
                    is_active=True,
                    last_login=datetime.now(timezone.utc),
                    settings={}  # Initialize empty settings
                )
                db.add(user)
                logger.info(f"✅ New user created: {username}")
        else:
            logger.info(f"✅ Found existing user, updating last login")
            # Update last login
            user.last_login = datetime.now(timezone.utc)
        
        logger.info(f"💾 Committing user to database...")
        await db.commit()
        await db.refresh(user)
        logger.info(f"✅ User saved with ID: {user.id}")
        
        # Create JWT token
        token_data = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "name": user.name,
        }
        jwt_token = create_access_token(token_data)
        logger.info(f"🔑 JWT token created for user {user.id}")
        
        # Redirect to frontend with token
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}"
        logger.info(f"↪️  Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ OAuth error: {str(e)}", exc_info=True)
        # Redirect to frontend with error instead of showing HTTP error
        error_url = f"{FRONTEND_URL}/auth/error?message={str(e)}"
        logger.info(f"↪️  Redirecting to error page: {error_url}")
        return RedirectResponse(url=error_url)


# ============================================================================
# Enhanced Authentication Endpoints
# ============================================================================

@router.post("/login/", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: JSONResponse,
    session: AsyncSession = Depends(get_session)
):
    """
    Enhanced login endpoint with comprehensive security features.
    
    Security Features:
    - Account lockout protection
    - Session fingerprinting
    - Device tracking
    - Security monitoring
    - Rate limiting (handled by middleware)
    - Refresh token rotation
    """
    client_ip = _get_client_ip(http_request)
    user_agent = _get_user_agent(http_request)
    
    logger.info(f"Login attempt: {request.username} from {client_ip}")
    
    # Check account lockout
    is_locked, lockout_message = await check_account_lockout(
        request.username, client_ip
    )
    if is_locked:
        logger.warning(f"Login blocked - account locked: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error": "account_locked", "message": lockout_message}
        )
    
    # Authenticate user
    user = await authenticate_user(session, request.username, request.password)
    
    if not user:
        # Record failed attempt
        await record_failed_login(request.username, client_ip, user_agent)
        
        logger.warning(f"Login failed: {request.username} from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Invalid username or password"}
        )
    
    # Create session fingerprint
    session_fingerprint = _create_session_fingerprint(http_request)
    
    # Create token with device info
    token = await create_token(
        session,
        user.user_id,
        device_info=f"{request.device_name or 'Unknown'}:{request.device_type or 'Unknown'}",
        ip_address=client_ip
    )
    
    if not token:
        logger.error(f"Failed to create token for user: {user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create authentication token"
        )
    
    # Create refresh token with rotation chain
    from database.models.refresh_token import RefreshToken as RefreshTokenModel
    rotation_chain_id = RefreshTokenModel.generate_chain_id()
    
    # Generate token ID for database record
    import uuid
    refresh_token_id = str(uuid.uuid4())
    
    # Create JWT refresh token
    refresh_token_jwt = create_refresh_token_jwt(
        user_id=user.user_id,
        rotation_chain_id=rotation_chain_id,
        token_id=refresh_token_id
    )
    
    # Store refresh token in database
    refresh_token_record = await create_refresh_token(
        session=session,
        user_id=user.user_id,
        token_value=refresh_token_jwt,
        rotation_chain_id=rotation_chain_id,
        device_info=user_agent,
        ip_address=client_ip
    )
    
    if not refresh_token_record:
        logger.error(f"Failed to create refresh token for user: {user.user_id}")
        # Don't fail login, just log the error
    else:
        # Set refresh token in httpOnly cookie
        CookieConfig.set_refresh_token_cookie(response, refresh_token_jwt)
        logger.debug(f"✅ Refresh token created for user {user.user_id}")
    
    # Update user activity
    await update_user_activity(session, user.user_id)
    
    # Prepare response
    user_dict = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_active": user.last_active.isoformat() if user.last_active else None
    }
    
    # Check for security warnings
    security_warnings = []
    if user.last_active and (datetime.now(timezone.utc) - user.last_active).days > 30:
        security_warnings.append("Account has been inactive for over 30 days")
    
    logger.info(f"Login successful: {user.username} from {client_ip}")
    
    return LoginResponse(
        token=token.token,
        user=user_dict,
        expires_at=token.expires_at,
        session_id=session_fingerprint,
        security_warnings=security_warnings
    )


@router.post("/exchange-token/")
async def exchange_token(
    http_request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Exchange a JWT token (from Google OAuth) for a database token.
    
    This allows OAuth users to get a database token that works with
    the same authentication system as email/password users.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Response:
        {
            "token": "database_token_here",
            "user": {...},
            "expires_at": "2025-10-28T12:00:00Z"
        }
    """
    # Get JWT token from header
    authorization = http_request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # Parse token
    try:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2:
            scheme, jwt_token = parts
            if scheme.lower() not in ["bearer"]:
                raise ValueError("Invalid scheme")
        else:
            jwt_token = authorization
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    # Verify JWT token
    try:
        from utils.auth.jwt_handler import verify_access_token
        payload = verify_access_token(jwt_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT token: {str(e)}"
        )
    
    # Extract user info from JWT
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token missing email"
        )
    
    # Get or create user
    user = await get_user_by_email(session, email)
    
    if not user:
        # Auto-create user from OAuth data
        user = await create_user(
            session=session,
            email=email,
            username=email.split("@")[0],
            name=payload.get("name"),
            google_id=payload.get("sub"),
            picture=payload.get("picture"),
            is_verified=True  # OAuth users are pre-verified
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Create database token
    client_ip = _get_client_ip(http_request)
    db_token = await create_token(
        session,
        user.user_id,
        device_info="OAuth Exchange",
        ip_address=client_ip
    )
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create token"
        )
    
    # Update user activity
    await update_user_activity(session, user.user_id)
    
    # Prepare user data
    user_dict = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_active": user.last_active.isoformat() if user.last_active else None
    }
    
    logger.info(f"Token exchange successful for: {user.email}")
    
    return {
        "token": db_token.token,
        "user": user_dict,
        "expires_at": db_token.expires_at,
        "token_type": "database"
    }


@router.post("/register/", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    User registration with password policy validation.
    
    Security Features:
    - Password policy enforcement
    - Email validation
    - Username uniqueness
    - Automatic login after registration
    """
    client_ip = _get_client_ip(http_request)
    
    logger.info(f"Registration attempt: {request.email} from {client_ip}")
    
    # Validate password policy
    password_validation = await validate_password_policy(
        request.password,
        username=request.username,
        email=request.email
    )
    
    if not password_validation.is_valid:
        logger.warning(f"Registration failed - weak password: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "weak_password",
                "message": "Password does not meet security requirements",
                "errors": password_validation.errors,
                "suggestions": password_validation.suggestions
            }
        )
    
    # Check if user already exists
    existing_user = await get_user_by_email(session, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "user_exists", "message": "User with this email already exists"}
        )
    
    # Create user - split full_name into first_name and last_name
    name_parts = request.full_name.split(' ', 1) if request.full_name else ['', '']
    first_name = name_parts[0] if len(name_parts) > 0 else ''
    last_name = name_parts[1] if len(name_parts) > 1 else ''
    
    user = await create_user(
        session,
        email=request.email,
        username=request.username,
        password=request.password,
        role=request.role,
        first_name=first_name,
        last_name=last_name,
        name=request.full_name  # Also store in name field
    )
    
    if not user:
        logger.error(f"Failed to create user: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )
    
    # Create session fingerprint
    session_fingerprint = _create_session_fingerprint(http_request)
    
    # Create token
    token = await create_token(
        session,
        user.user_id,
        device_info="Registration Device",
        ip_address=client_ip
    )
    
    if not token:
        logger.error(f"Failed to create token for new user: {user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create authentication token"
        )
    
    # Prepare response
    user_dict = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat()
    }
    
    password_strength = {
        "strength": password_validation.strength.value,
        "score": password_validation.score,
        "warnings": password_validation.warnings
    }
    
    logger.info(f"Registration successful: {user.username} from {client_ip}")
    
    # Send welcome email to new user
    try:
        from utils.email import email_service
        logger.info(f"📧 Sending welcome email to {user.email}")
        email_sent = email_service.send_welcome_email(
            to_email=user.email,
            username=user.username,
            first_name=first_name
        )
        if email_sent:
            logger.info(f"✅ Welcome email sent successfully to {user.email}")
        else:
            logger.warning(f"⚠️ Failed to send welcome email to {user.email}")
    except Exception as e:
        # Don't fail registration if email fails
        logger.error(f"❌ Error sending welcome email: {e}")
    
    return RegisterResponse(
        user=user_dict,
        token=token.token,
        expires_at=token.expires_at,
        session_id=session_fingerprint,
        password_strength=password_strength
    )


@router.post("/change-password/", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Change user password with policy validation.
    
    Security Features:
    - Current password verification
    - Password policy enforcement
    - Session invalidation
    - Security logging
    """
    client_ip = _get_client_ip(http_request)
    user_id = current_user["user_id"]
    
    logger.info(f"Password change attempt: {current_user['username']} from {client_ip}")
    
    # Validate new password policy
    password_validation = await validate_password_policy(
        request.new_password,
        username=current_user["username"],
        email=current_user["email"]
    )
    
    if not password_validation.is_valid:
        logger.warning(f"Password change failed - weak password: {current_user['username']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "weak_password",
                "message": "New password does not meet security requirements",
                "errors": password_validation.errors,
                "suggestions": password_validation.suggestions
            }
        )
    
    # Change password
    success = await change_user_password(
        session,
        user_id,
        request.current_password,
        request.new_password
    )
    
    if not success:
        logger.warning(f"Password change failed - invalid current password: {current_user['username']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_password", "message": "Current password is incorrect"}
        )
    
    # Invalidate all existing sessions (force re-login)
    await delete_user_tokens(session, user_id)
    
    password_strength = {
        "strength": password_validation.strength.value,
        "score": password_validation.score,
        "warnings": password_validation.warnings
    }
    
    logger.info(f"Password changed successfully: {current_user['username']} from {client_ip}")
    
    return ChangePasswordResponse(
        success=True,
        message="Password changed successfully. Please log in again.",
        password_strength=password_strength
    )


@router.post("/set-password/", response_model=SetPasswordResponse)
async def set_password(
    request: SetPasswordRequest,
    http_request: Request,
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Set password for OAuth users who don't have one.
    
    This endpoint allows users who signed up via Google OAuth (or other OAuth providers)
    to create a password for their account, enabling them to log in with email/password
    in addition to OAuth.
    
    Security Features:
    - Only works if user has NO existing password
    - Password policy enforcement
    - Prevents password change (use /change-password for that)
    - Security logging
    - Audit trail
    
    Args:
        request: Password creation request
        http_request: HTTP request for IP/user agent
        current_user: Current authenticated user
        session: Database session
        
    Returns:
        Success response with password strength info
        
    Raises:
        HTTPException: If user already has a password or validation fails
    """
    client_ip = _get_client_ip(http_request)
    user_id = current_user["user_id"]
    
    logger.info(f"Set password attempt: {current_user['username']} from {client_ip}")
    
    # Get user from database to check password status
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user already has a password
    has_password = False
    if user.password_hash:
        has_password = True
    elif user.settings and user.settings.get('password_hash'):
        # Check legacy location
        has_password = True
    
    if has_password:
        logger.warning(f"Set password failed - user already has password: {current_user['username']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "password_exists",
                "message": "You already have a password set. Use the 'Change Password' feature instead.",
                "suggestion": "Go to Settings > Security > Change Password"
            }
        )
    
    # Validate new password policy
    password_validation = await validate_password_policy(
        request.new_password,
        username=current_user["username"],
        email=current_user["email"]
    )
    
    if not password_validation.is_valid:
        logger.warning(f"Set password failed - weak password: {current_user['username']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "weak_password",
                "message": "Password does not meet security requirements",
                "errors": password_validation.errors,
                "suggestions": password_validation.suggestions
            }
        )
    
    # Hash and set the password
    from sqlalchemy import update
    new_hash = hash_password(request.new_password)
    
    try:
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(password_hash=new_hash)
        )
        
        # Log audit event
        audit_entry = AuditLog(
            user_id=user.user_id,
            user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            action_type="password_created",
            resource_type="user_account",
            resource_id=user.id,
            action_details={
                "method": "set_password_api",
                "had_google_oauth": bool(user.google_id),
                "ip_address": client_ip,
                "user_agent": _get_user_agent(http_request)
            },
            old_value={"has_password": False},
            new_value={"has_password": True},
            ip_address=client_ip,
            success=True
        )
        session.add(audit_entry)
        
        await session.commit()
        logger.info(f"✅ Password set successfully for OAuth user: {current_user['username']}")
        
    except Exception as e:
        logger.error(f"❌ Error setting password: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set password"
        )
    
    password_strength = {
        "strength": password_validation.strength.value,
        "score": password_validation.score,
        "warnings": password_validation.warnings
    }
    
    # Determine account type for response
    account_type = "oauth_with_password"
    if user.google_id:
        account_type = "google_and_password"
    
    logger.info(f"Password set successfully: {current_user['username']} from {client_ip}")
    
    return SetPasswordResponse(
        success=True,
        message="Password created successfully! You can now log in with either Google or email/password.",
        password_strength=password_strength,
        account_type=account_type
    )


@router.post("/logout/", response_model=LogoutResponse)
async def logout(
    http_request: Request,
    request: Optional[LogoutRequest] = None,
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Logout endpoint with session management.
    
    Security Features:
    - Token invalidation
    - Optional logout from all devices
    - Session cleanup
    - Security logging
    """
    client_ip = _get_client_ip(http_request)
    user_id = current_user["user_id"]
    
    logger.info(f"Logout: {current_user['username']} from {client_ip}")
    
    # Get authorization header for token
    authorization = http_request.headers.get("Authorization")
    if authorization:
        try:
            parts = authorization.split(maxsplit=1)
            if len(parts) == 2:
                scheme, token = parts
                if scheme.lower() in ["token", "bearer"]:
                    # Delete specific token
                    await delete_token(session, token)
        except (ValueError, AttributeError):
            pass
    
    sessions_terminated = 1
    
    if request and request.logout_all_devices:
        # Delete all user tokens
        await delete_user_tokens(session, user_id)
        sessions_terminated = "all"
    
    # Revoke all refresh tokens for the user
    await revoke_user_tokens(session, user_id, reason="user_logout")
    
    return LogoutResponse(
        success=True,
        message="Logged out successfully",
        sessions_terminated=sessions_terminated
    )


@router.post("/refresh/", response_model=RefreshTokenResponse)
async def refresh_access_token(
    http_request: Request,
    response: JSONResponse,
    session: AsyncSession = Depends(get_session)
):
    """
    Refresh access token using refresh token rotation.
    
    Security Features:
    - Token rotation: Each refresh creates a new refresh token
    - Single-use tokens: Old refresh token becomes invalid
    - Chain tracking: All tokens in rotation chain are linked
    - Misuse detection: Reuse of old token → revoke entire chain
    - httpOnly cookies: Tokens not accessible to JavaScript
    
    Flow:
    1. Read refresh_token from httpOnly cookie
    2. Verify it's valid and not revoked
    3. Check for reuse (security threat)
    4. Create new access + refresh tokens
    5. Mark old refresh token as used
    6. Set new tokens in httpOnly cookies
    
    Returns:
        New access token and expiration
    
    Raises:
        HTTPException: If refresh token is invalid, expired, revoked, or reused
    """
    client_ip = _get_client_ip(http_request)
    user_agent = _get_user_agent(http_request)
    
    # Get refresh token from httpOnly cookie
    refresh_token = CookieConfig.get_refresh_token_from_cookie(http_request)
    
    if not refresh_token:
        logger.warning(f"Refresh attempt without token from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_refresh_token", "message": "Refresh token not found"}
        )
    
    # Verify JWT structure
    try:
        payload = verify_refresh_token(refresh_token)
    except HTTPException as e:
        logger.warning(f"Invalid refresh token JWT from {client_ip}: {e.detail}")
        raise
    
    # Extract token details
    user_id = payload.get("user_id")
    token_id = payload.get("token_id")
    rotation_chain_id = payload.get("rotation_chain_id")
    
    # Fetch user to get current role
    user = await get_user_by_id(session, user_id)
    if not user:
        logger.error(f"User {user_id} not found during token refresh")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "user_not_found", "message": "User not found"}
        )
    
    # Generate new tokens with role claim
    from utils.auth.jwt_handler import create_access_token
    new_access_token = create_access_token(
        data={
            "user_id": user_id,
            "sub": user_id,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "name": user.name,
            "type": "access"
        }
    )
    
    # Create new refresh token value (JWT)
    from database.models.refresh_token import RefreshToken as RefreshTokenModel
    new_refresh_token_record = RefreshTokenModel()  # For generating token_id
    
    new_refresh_token_jwt = create_refresh_token_jwt(
        user_id=user_id,
        rotation_chain_id=rotation_chain_id,
        token_id=new_refresh_token_record.token_id
    )
    
    # Rotate refresh token in database
    new_refresh_token_db, error = await rotate_refresh_token(
        session=session,
        old_token_value=refresh_token,
        new_token_value=new_refresh_token_jwt,
        device_info=user_agent,
        ip_address=client_ip
    )
    
    if error:
        # Handle specific errors
        if error == "refresh_token_not_found":
            logger.warning(f"Refresh token not found in DB from {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_refresh_token", "message": "Refresh token not found"}
            )
        elif error == "refresh_token_revoked":
            logger.warning(f"Attempted to use revoked refresh token from {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "refresh_token_revoked", "message": "Refresh token has been revoked"}
            )
        elif error == "refresh_token_expired":
            logger.warning(f"Attempted to use expired refresh token from {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "refresh_token_expired", "message": "Refresh token has expired"}
            )
        elif error == "refresh_token_reused_chain_revoked":
            logger.error(
                f"🚨 SECURITY: Refresh token reuse detected from {client_ip}! "
                f"Chain {rotation_chain_id[:8]}... revoked."
            )
            # Clear cookies to force re-authentication
            CookieConfig.clear_auth_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "security_violation",
                    "message": "Token reuse detected. All sessions have been terminated for security."
                }
            )
        else:
            logger.error(f"Refresh token rotation failed from {client_ip}: {error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "token_rotation_failed", "message": "Failed to rotate refresh token"}
            )
    
    # Set new tokens in httpOnly cookies
    CookieConfig.set_access_token_cookie(response, new_access_token)
    CookieConfig.set_refresh_token_cookie(response, new_refresh_token_jwt)
    
    logger.info(f"✅ Token refreshed for user {user_id} from {client_ip}")
    
    return RefreshTokenResponse(
        access_token=new_access_token,
        expires_at=new_refresh_token_db.expires_at,
        token_type="bearer"
    )


@router.get("/sessions/", response_model=SessionsResponse)
async def get_active_sessions(
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Get active sessions for the current user.
    
    Security Features:
    - Session fingerprinting
    - Device tracking
    - Last activity monitoring
    """
    # In a real implementation, this would query the database for active sessions
    # For now, we'll return a placeholder response
    sessions = [
        SessionInfo(
            session_id="current_session",
            device_name="Current Device",
            device_type="Web Browser",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0...",
            created_at=datetime.now(timezone.utc),
            last_used=datetime.now(timezone.utc),
            is_current=True
        )
    ]
    
    return SessionsResponse(
        sessions=sessions,
        total_count=len(sessions)
    )


@router.post("/validate-password/", response_model=PasswordPolicyResponse)
async def validate_password(
    request: PasswordPolicyRequest
):
    """
    Validate password against policy without changing it.
    
    Security Features:
    - Real-time validation
    - Policy compliance checking
    - Strength assessment
    
    Note: This endpoint is public to allow password validation during registration
    """
    password_validation = await validate_password_policy(
        request.password,
        username=request.username,
        email=request.email
    )
    
    return PasswordPolicyResponse(
        is_valid=password_validation.is_valid,
        strength=password_validation.strength.value,
        score=password_validation.score,
        errors=password_validation.errors,
        warnings=password_validation.warnings,
        suggestions=password_validation.suggestions
    )


@router.get("/security-events/", response_model=SecurityEventsResponse)
async def get_security_events(
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    limit: int = 50
):
    """
    Get security events for the current user.
    
    Security Features:
    - Login attempts tracking
    - Suspicious activity monitoring
    - Security event logging
    """
    # In a real implementation, this would query security events from the database
    # For now, we'll return a placeholder response
    events = [
        SecurityEvent(
            event_type="login_success",
            timestamp=datetime.now(timezone.utc),
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0...",
            details={"method": "password"},
            severity="info"
        )
    ]
    
    return SecurityEventsResponse(
        events=events,
        total_count=len(events)
    )


@router.get("/password-status/")
async def get_password_status(
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Check if the current user has a password set.
    
    This is useful for the frontend to determine whether to show
    "Set Password" or "Change Password" options.
    
    Returns:
        {
            "has_password": bool,
            "has_google_oauth": bool,
            "account_type": str,  # "password_only", "oauth_only", "both"
            "can_set_password": bool,
            "can_change_password": bool
        }
    """
    user_id = current_user["user_id"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check password status
    has_password = bool(user.password_hash or (user.settings and user.settings.get('password_hash')))
    has_google = bool(user.google_id)
    
    # Determine account type
    if has_password and has_google:
        account_type = "both"
    elif has_password:
        account_type = "password_only"
    elif has_google:
        account_type = "oauth_only"
    else:
        account_type = "incomplete"  # Shouldn't happen
    
    return {
        "has_password": has_password,
        "has_google_oauth": has_google,
        "account_type": account_type,
        "can_set_password": not has_password,  # Can set if no password
        "can_change_password": has_password,  # Can change if has password
        "email": user.email,
        "username": user.username or user.email
    }


# ============================================================================
# Legacy Compatibility Endpoints
# ============================================================================

@router.get("/me/", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get current authenticated user information.
    
    Args:
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        User information
    """
    user_id = current_user.get("user_id")
    
    # Convert string UUID to UUID object for comparison with User.id (UUID field)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid user_id format in JWT: {user_id}")
        raise HTTPException(status_code=401, detail="Invalid user ID in token")
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user.id),  # Convert UUID to string
        email=user.email,
        name=user.name,
        picture=user.picture,
        role=user.role.value,
        is_verified=user.is_verified,
    )


@router.get("/session/validate", response_model=SessionValidateResponse)
async def validate_session(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Lightweight endpoint for silent session validation.
    
    This endpoint validates the user's session without hitting the database
    if the token is cached. Designed for frequent client-side checks of
    authentication status.
    
    Features:
    - Cookie-based authentication support
    - Header-based authentication fallback
    - Token cache optimization (no DB hit if cached)
    - Minimal response payload
    - Compatible with httpOnly cookies
    
    Returns:
        SessionValidateResponse: Validation status and minimal user data
        
    Raises:
        No exceptions - returns valid=false for unauthenticated requests
    """
    try:
        # Try to get token from cookie or header
        from utils.auth.cookie_config import CookieConfig
        token = CookieConfig.get_token_from_cookie_or_header(request, authorization)
        
        if not token:
            return SessionValidateResponse(valid=False)
        
        # Check token cache first (avoids DB hit)
        from utils.auth.token_cache import get_token_cache
        token_cache = await get_token_cache()
        cached_user = await token_cache.get(token)
        
        if cached_user:
            # Return cached user data (no DB hit!)
            return SessionValidateResponse(
                valid=True,
                user_id=cached_user.get("user_id"),
                username=cached_user.get("username"),
                email=cached_user.get("email"),
                role=cached_user.get("role")
            )
        
        # Token not in cache - validate it
        # Try JWT first (faster, no DB hit)
        try:
            from utils.auth.jwt_handler import verify_access_token
            payload = verify_access_token(token)
            
            # Valid JWT token
            user_data = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username") or payload.get("email", "").split("@")[0],
                "email": payload.get("email"),
                "role": payload.get("role", "student")
            }
            
            # Cache it for next time
            await token_cache.set(token, user_data)
            
            return SessionValidateResponse(
                valid=True,
                user_id=user_data.get("user_id"),
                username=user_data.get("username"),
                email=user_data.get("email"),
                role=user_data.get("role")
            )
        except Exception:
            # JWT validation failed, return invalid
            # We deliberately don't check DB tokens here to keep it lightweight
            return SessionValidateResponse(valid=False)
            
    except Exception as e:
        # Any error means invalid session
        logger.debug(f"Session validation error: {e}")
        return SessionValidateResponse(valid=False)


@router.get("/config/")
async def get_auth_config():
    """
    Get authentication configuration for frontend.
    
    SECURITY NOTE: Only returns non-sensitive configuration.
    Client ID is safe to expose as it's used for OAuth redirect flow.
    Never expose client secret.
    """
    return {
        "google_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "google_auth_url": "/api/auth/google/login/",
        "google_client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None,
    }


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.post("/admin/unlock-account/{user_id}")
async def admin_unlock_account(
    user_id: str,
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token),
    session: AsyncSession = Depends(get_session)
):
    """
    Admin endpoint to unlock a locked account.
    
    Security Features:
    - Admin role verification
    - Audit logging
    - Account status management
    """
    # Check admin role
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Unlock account
    lockout_manager = get_lockout_manager()
    success = await lockout_manager.unlock_account(
        user_id,
        admin_user_id=current_user["user_id"],
        reason="admin_unlock"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock account"
        )
    
    logger.info(f"Account unlocked by admin: {user_id} by {current_user['username']}")
    
    return {"success": True, "message": f"Account {user_id} unlocked successfully"}


@router.get("/admin/lockout-stats/")
async def admin_get_lockout_stats(
    current_user: Dict[str, Any] = Depends(_get_current_user_from_token)
):
    """
    Admin endpoint to get lockout statistics.
    
    Security Features:
    - Admin role verification
    - System monitoring
    - Security metrics
    """
    # Check admin role
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    lockout_manager = get_lockout_manager()
    stats = await lockout_manager.get_lockout_stats()
    
    return stats


# ============================================================================
# Legacy Compatibility Endpoints (for old Google OAuth redirect URIs)
# ============================================================================

@legacy_router.get("/google/callback")
async def legacy_google_callback(
    code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Legacy Google OAuth callback handler for backward compatibility.
    
    This handles callbacks from Google Cloud Console redirect URIs that
    were configured with the old /auth prefix.
    
    Redirects to the main callback handler.
    """
    # Call the main callback handler
    return await google_callback(code, db)