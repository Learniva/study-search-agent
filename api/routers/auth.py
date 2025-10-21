"""Authentication endpoints for Google OAuth."""

import os
from datetime import datetime, timedelta
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

router = APIRouter(prefix="/auth", tags=["authentication"])

# Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


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


@router.get("/google/login")
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


@router.get("/google/callback")
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
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
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
                print(f"Google token error: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to get access token: {error_detail}")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if user_info_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            user_data = user_info_response.json()
        
        # Extract user information
        google_id = user_data.get("id")
        email = user_data.get("email")
        name = user_data.get("name")
        picture = user_data.get("picture")
        email_verified = user_data.get("verified_email", False)
        
        # Check if user exists
        result = await db.execute(
            select(User).where(User.google_id == google_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Check by email
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Update existing user with Google ID
                user.google_id = google_id
                user.picture = picture
                user.is_verified = email_verified
                user.last_login = datetime.utcnow()
            else:
                # Create new user
                user = User(
                    email=email,
                    name=name,
                    picture=picture,
                    google_id=google_id,
                    role=UserRole.STUDENT,  # Default role
                    is_verified=email_verified,
                    is_active=True,
                    last_login=datetime.utcnow(),
                )
                db.add(user)
        else:
            # Update last login
            user.last_login = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user)
        
        # Create JWT token
        token_data = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "name": user.name,
        }
        jwt_token = create_access_token(token_data)
        
        # Redirect to frontend with token
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"OAuth error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal).
    
    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
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


@router.get("/config")
async def get_auth_config():
    """Get authentication configuration for frontend."""
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "google_auth_url": "/auth/google/login",
    }

