"""Authentication endpoints for Google OAuth."""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.core.async_engine import get_async_db
from database.models.user import User, UserRole
from utils.auth import create_access_token, get_current_user, google_oauth
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Legacy router for backward compatibility (old /auth prefix)
legacy_router = APIRouter(prefix="/auth", tags=["authentication-legacy"])

# Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback/")

# Shared HTTP client with connection pooling for better performance
# OPTIMIZATION: Reuse connections instead of creating new client each time
_http_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    """
    Get or create shared HTTP client with connection pooling.
    
    Connection pooling improves performance by reusing connections.
    """
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


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User response model."""
    id: int
    email: str
    name: Optional[str]
    picture: Optional[str]
    role: str
    is_verified: bool


@router.get("/google/login/")
async def google_login():
    """
    Initiate Google OAuth login flow.
    
    Returns:
        Redirect to Google OAuth consent screen
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured"
        )
    
    auth_url = google_oauth.get_authorization_url(GOOGLE_REDIRECT_URI)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback/")
@router.get("/google/callback")  # Without trailing slash for compatibility
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Google OAuth callback.
    
    Args:
        code: Authorization code from Google
        db: Database session
        
    Returns:
        Redirect to frontend with token
    """
    logger.info(f"🔐 OAuth callback received. Code length: {len(code) if code else 0}")
    logger.info(f"🔐 Using redirect URI: {GOOGLE_REDIRECT_URI}")
    logger.info(f"🔐 Frontend URL: {FRONTEND_URL}")
    
    if not code:
        logger.error("❌ Missing authorization code")
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    try:
        # Exchange code for tokens
        # OPTIMIZATION: Use shared HTTP client with connection pooling
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
                logger.info(f"✅ Found existing user by email, updating with Google ID")
                # Update existing user with Google ID
                user.google_id = google_id
                user.picture = picture
                user.profile_picture = picture
                user.is_verified = email_verified
                user.last_login = datetime.now(timezone.utc)
            else:
                logger.info(f"👤 Creating new user from Google OAuth")
                # Create new user from Google OAuth
                # Generate username from email or name
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


@router.post("/logout/")
async def logout():
    """
    Logout endpoint (client-side token removal).
    
    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}


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
    
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        role=user.role.value,
        is_verified=user.is_verified,
    )


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
        # Note: google_client_id is intentionally included as it's needed for frontend OAuth flow
        # and is not sensitive (client secret is never exposed)
        "google_client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None,
    }


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

