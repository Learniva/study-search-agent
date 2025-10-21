"""
Profile Management Router

Endpoints for user profile management including:
- View profile information
- Update profile information
- Upload profile picture
- Manage contact information
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from utils.auth.jwt_handler import get_current_user, get_optional_current_user  # Use Google OAuth JWT authentication
from database.core.async_connection import get_session
from database.operations.user_ops import (
    get_user_by_id,
    update_user_profile,
    update_user_settings,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


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


class ProfileResponse(BaseModel):
    """Profile response."""
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    location: Optional[str]
    website: Optional[str]
    profile_picture: Optional[str]
    role: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=ProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
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
    # Handle Google OAuth user structure
    user_id = int(current_user.get("user_id", 0))
    name = current_user.get("name", "")
    name_parts = name.split(" ", 1) if name else ["", ""]
    
    return ProfileResponse(
        id=user_id,
        username=current_user.get("email", "").split("@")[0],  # Use email prefix as username
        email=current_user.get("email", ""),
        first_name=name_parts[0] if len(name_parts) > 0 else "",
        last_name=name_parts[1] if len(name_parts) > 1 else "",
        display_name=current_user.get("name", ""),
        location="",
        website="",
        profile_picture="",
        role=current_user.get("role", "student")
    )


@router.put("/", response_model=ProfileResponse)
@router.patch("/", response_model=ProfileResponse)
async def update_profile(
    profile_update: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
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
    # Get user_id from current_user (email is used as user_id)
    user_id = current_user["email"]
    
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
        id=hash(updated_user_model.user_id) % 1000000,
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
    current_user: dict = Depends(get_current_user),
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
    # Get user_id from current_user (email is used as user_id)
    user_id = current_user["email"]
    
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
        id=hash(updated_user_model.user_id) % 1000000,
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
    current_user: dict = Depends(get_current_user),
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
    user_id_hash = current_user["id"]
    picture_url = f"/uploads/profile/{user_id_hash}.jpg"
    
    # Update user in database
    user_email = current_user["email"]
    await update_user_profile(session, user_email, profile_picture=picture_url)
    
    return {
        "message": "Profile picture uploaded successfully",
        "url": picture_url
    }


@router.delete("/picture")
async def delete_profile_picture(
    current_user: dict = Depends(get_current_user),
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
    user_email = current_user["email"]
    await update_user_profile(session, user_email, profile_picture=None)
    
    return {
        "message": "Profile picture deleted successfully"
    }


@router.get("/preferences")
@router.get("/preferences/")
async def get_profile_preferences(current_user: dict = Depends(get_current_user)):
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
async def get_profile_statistics(current_user: dict = Depends(get_current_user)):
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
async def get_billing_info(current_user: dict = Depends(get_current_user)):
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
    current_user: dict = Depends(get_current_user)
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

