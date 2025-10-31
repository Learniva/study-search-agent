"""
Profile Management Router

Endpoints for user profile management including:
- View profile information
- Update profile information
- Upload profile picture
- Manage contact information
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.auth import get_current_user  # Use unified authentication (supports both JWT and database tokens)
from api.models import ProfileResponse  # Import ProfileResponse from central models
from database.core.async_connection import get_session
from database.operations.user_ops import (
    get_user_by_id,
    update_user_profile,
    update_user_settings,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])
logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class ProfileInformation(BaseModel):
    """Profile information model."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: str
    email: str
    display_name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    profile_picture: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """Update profile request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


class UpdateAccountRequest(BaseModel):
    """Update account information request."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=ProfileResponse)
async def get_profile(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get current user's profile information.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Response:
        {
            "id": 1,
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "John D.",
            "location": "New York, USA",
            "website": "https://example.com",
            "profile_picture": "/uploads/profile/1.jpg",
            "role": "student"
        }
    """
    # Get user_id from current_user
    user_id = current_user["user_id"]
    
    # Log successful profile access with structured logging
    logger.info({
        "event": "profile_access",
        "action": "get_profile",
        "user_id": user_id,
        "has_auth_header": "Authorization" in request.headers,
        "client_ip": request.client.host if request.client else "unknown",
        "path": request.url.path
    })
    
    # Fetch user from database to get all profile fields
    user = await get_user_by_id(session, user_id)
    
    if not user:
        # Fallback to JWT data if user not found in database (shouldn't happen)
        name = current_user.get("name", "")
        name_parts = name.split(" ", 1) if name else ["", ""]
        
        return ProfileResponse(
            id=str(current_user.get("user_id", "")),
            username=current_user.get("email", "").split("@")[0],
            email=current_user.get("email", ""),
            first_name=name_parts[0] if len(name_parts) > 0 else "",
            last_name=name_parts[1] if len(name_parts) > 1 else "",
            display_name=current_user.get("name", ""),
            location="",
            website="",
            profile_picture="",
            role=current_user.get("role", "student")
        )
    
    # Return data from database
    return ProfileResponse(
        id=str(user.id),
        username=user.username or user.email.split("@")[0],
        email=user.email,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        display_name=user.display_name or user.name or "",
        location=user.location or "",
        website=user.website or "",
        profile_picture=user.profile_picture or user.picture or "",
        role=user.role
    )


@router.put("/", response_model=ProfileResponse)
@router.patch("/", response_model=ProfileResponse)
async def update_profile(
    profile_update: UpdateProfileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update user profile information.
    
    Accepts both PUT and PATCH methods.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "John D.",
            "location": "New York, USA",
            "website": "https://example.com"
        }
    
    Response:
        Updated profile information
    """
    # Get user_id from current_user
    user_id = current_user["user_id"]
    
    # Update profile in database
    updated_user_model = await update_user_profile(
        session,
        user_id,
        first_name=profile_update.first_name,
        last_name=profile_update.last_name,
        display_name=profile_update.display_name,
        location=profile_update.location,
        website=profile_update.website,
    )
    
    if not updated_user_model:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    return ProfileResponse(
        id=str(updated_user_model.id),
        username=updated_user_model.username,
        email=updated_user_model.email,
        first_name=updated_user_model.first_name or "",
        last_name=updated_user_model.last_name or "",
        display_name=updated_user_model.display_name or "",
        location=updated_user_model.location or "",
        website=updated_user_model.website or "",
        profile_picture=updated_user_model.profile_picture or "",
        role=updated_user_model.role
    )


@router.put("/update_account")
@router.patch("/update_account")
@router.put("/update_account/")
@router.patch("/update_account/")
async def update_account(
    account_update: UpdateAccountRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update user account information (alias for update_profile).
    
    Accepts both PUT and PATCH methods.
    Handles both with and without trailing slash.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "username": "newusername",
            "email": "newemail@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "John D.",
            "location": "New York, USA",
            "website": "https://example.com"
        }
    
    Response:
        Updated profile information
    """
    # Get user_id from current_user
    user_id = current_user["user_id"]
    
    # Update profile in database
    updated_user_model = await update_user_profile(
        session,
        user_id,
        username=account_update.username,
        first_name=account_update.first_name,
        last_name=account_update.last_name,
        display_name=account_update.display_name,
        location=account_update.location,
        website=account_update.website,
    )
    
    if not updated_user_model:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    return ProfileResponse(
        id=str(updated_user_model.id),
        username=updated_user_model.username,
        email=updated_user_model.email,
        first_name=updated_user_model.first_name or "",
        last_name=updated_user_model.last_name or "",
        display_name=updated_user_model.display_name or "",
        location=updated_user_model.location or "",
        website=updated_user_model.website or "",
        profile_picture=updated_user_model.profile_picture or "",
        role=updated_user_model.role
    )


@router.post("/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload profile picture.
    
    Headers:
        Authorization: Token abc123...
    
    Form Data:
        file: Image file (JPEG, PNG, GIF)
    
    Response:
        {
            "message": "Profile picture uploaded successfully",
            "url": "/uploads/profile/1.jpg"
        }
    """
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image (JPEG, PNG, GIF)"
        )
    
    # In production, save to storage service (S3, etc.)
    # For now, just return a mock URL
    user_id = current_user["user_id"]
    picture_url = f"/uploads/profile/{user_id}.jpg"
    
    # Update user in database
    await update_user_profile(session, user_id, profile_picture=picture_url)
    
    return {
        "message": "Profile picture uploaded successfully",
        "url": picture_url
    }


@router.delete("/picture")
async def delete_profile_picture(
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete profile picture.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "message": "Profile picture deleted successfully"
        }
    """
    user_id = current_user["user_id"]
    await update_user_profile(session, user_id, profile_picture=None)
    
    return {
        "message": "Profile picture deleted successfully"
    }


@router.get("/preferences")
@router.get("/preferences/")
async def get_profile_preferences(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get user preferences (default settings).
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Response:
        User preferences
    """
    # Return default preferences (can be enhanced later with database storage)
    return {
        "language": "English",
        "timezone": "UTC",
        "date_format": "MM/DD/YYYY",
        "theme": "system",
        "email": current_user.get("email", "")
    }


@router.get("/statistics")
@router.get("/statistics/")
async def get_profile_statistics(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get user statistics and activity.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Response:
        User activity statistics
    """
    # Return placeholder statistics (can be enhanced later with actual data)
    return {
        "total_queries": 0,
        "documents_uploaded": 0,
        "videos_generated": 0,
        "flashcards_created": 0,
        "study_sessions": 0,
        "total_time_spent": 0,
        "joined_date": "2025-10-19",
        "last_active": "2025-10-19",
        "user_email": current_user.get("email", "")
    }


# ============================================================================
# Billing Information (Read-only for now)
# ============================================================================

class PlanInformation(BaseModel):
    """Plan information model."""
    name: str
    tier: str
    price: float
    currency: str
    status: str
    features: list[str]


@router.get("/billing")
async def get_billing_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get user's billing information and current plan.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "current_plan": {
                "name": "Basic",
                "tier": "free",
                "price": 0.0,
                "currency": "USD",
                "status": "active",
                "features": [...]
            },
            "payment_method": null,
            "next_billing_date": null
        }
    """
    # Default to Basic (free) plan
    current_plan = PlanInformation(
        name="Basic",
        tier="free",
        price=0.0,
        currency="USD",
        status="active",
        features=[
            "Limited image and video generations",
            "Limited interactive flashcards",
            "Limited practice generations",
            "Limited chats and document search",
            "Basic support"
        ]
    )
    
    available_plans = [
        {
            "name": "Basic",
            "tier": "free",
            "price": 0.0,
            "currency": "USD",
            "features": [
                "Limited image and video generations",
                "Limited interactive flashcards",
                "Limited practice generations",
                "Limited chats and document search",
                "Basic support"
            ]
        },
        {
            "name": "Premium",
            "tier": "premium",
            "price": 9.99,
            "currency": "USD",
            "features": [
                "AI-Powered Study Tools",
                "Mind maps, notes, and more",
                "Unlimited journals & chats",
                "5 video generations / day",
                "5 flashcard generations / day",
                "30 day version history",
                "Priority support"
            ]
        }
    ]
    
    return {
        "current_plan": current_plan.dict(),
        "available_plans": available_plans,
        "payment_method": None,
        "next_billing_date": None,
        "billing_required": False
    }


@router.post("/upgrade")
async def upgrade_plan(
    plan_tier: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Upgrade user's subscription plan.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "plan_tier": "premium"
        }
    
    Response:
        {
            "message": "Plan upgrade initiated",
            "plan": "premium",
            "checkout_url": "https://stripe.com/checkout/..."
        }
    """
    # In production, integrate with payment gateway (Stripe, PayPal, etc.)
    return {
        "message": "Plan upgrade initiated (not implemented)",
        "plan": plan_tier,
        "checkout_url": None,
        "status": "pending_payment"
    }

