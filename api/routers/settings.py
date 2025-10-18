"""
Settings Management Router

Endpoints for user settings and preferences including:
- Notification preferences
- Language and timezone settings
- Appearance preferences
- Password management
- Account deletion
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.learniva_auth import get_current_user
from database.core.async_connection import get_session
from database.operations.user_ops import (
    update_user_settings,
    get_user_by_id,
    change_user_password,
)
from utils.cache.redis_client import token_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ============================================================================
# Models
# ============================================================================

class NotificationSettings(BaseModel):
    """Notification settings model."""
    email_notifications: bool = True
    push_notifications: bool = False
    weekly_digest: bool = True
    product_updates: bool = False
    study_reminders: bool = True


class PreferencesSettings(BaseModel):
    """Preferences settings model."""
    language: str = "English"
    timezone: str = "UTC"
    date_format: str = "MM/DD/YYYY"


class AppearanceSettings(BaseModel):
    """Appearance settings model."""
    theme: str = "system"  # system, light, dark
    compact_mode: bool = False
    animations: bool = True


class UserSettings(BaseModel):
    """Complete user settings model."""
    notifications: NotificationSettings
    preferences: PreferencesSettings
    appearance: AppearanceSettings


class UpdateNotificationsRequest(BaseModel):
    """Update notification settings request."""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    weekly_digest: Optional[bool] = None
    product_updates: Optional[bool] = None
    study_reminders: Optional[bool] = None


class UpdatePreferencesRequest(BaseModel):
    """Update preferences request."""
    language: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None


class UpdateAppearanceRequest(BaseModel):
    """Update appearance request."""
    theme: Optional[str] = None
    compact_mode: Optional[bool] = None
    animations: Optional[bool] = None


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str
    confirm_password: str


# ============================================================================
# Helper Functions
# ============================================================================

def get_user_settings(user: dict) -> UserSettings:
    """Get user settings from database or defaults."""
    settings = user.get("settings", {})
    
    return UserSettings(
        notifications=NotificationSettings(
            email_notifications=settings.get("email_notifications", True),
            push_notifications=settings.get("push_notifications", False),
            weekly_digest=settings.get("weekly_digest", True),
            product_updates=settings.get("product_updates", False),
            study_reminders=settings.get("study_reminders", True)
        ),
        preferences=PreferencesSettings(
            language=settings.get("language", "English"),
            timezone=settings.get("timezone", "UTC"),
            date_format=settings.get("date_format", "MM/DD/YYYY")
        ),
        appearance=AppearanceSettings(
            theme=settings.get("theme", "system"),
            compact_mode=settings.get("compact_mode", False),
            animations=settings.get("animations", True)
        )
    )


# ============================================================================
# Endpoints - General Settings
# ============================================================================

@router.get("/", response_model=UserSettings)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """
    Get user's complete settings.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "notifications": {...},
            "preferences": {...},
            "appearance": {...}
        }
    """
    return get_user_settings(current_user)


# ============================================================================
# Endpoints - Notifications
# ============================================================================

@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(current_user: dict = Depends(get_current_user)):
    """
    Get user's notification settings.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "email_notifications": true,
            "push_notifications": false,
            "weekly_digest": true,
            "product_updates": false,
            "study_reminders": true
        }
    """
    settings = get_user_settings(current_user)
    return settings.notifications


@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    notification_update: UpdateNotificationsRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update user's notification settings.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "email_notifications": true,
            "push_notifications": false,
            "weekly_digest": true,
            "product_updates": false,
            "study_reminders": true
        }
    
    Response:
        Updated notification settings
    """
    user_id = current_user["email"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get current settings
    current_settings = user.settings or {}
    notifications = current_settings.get("notifications", {})
    
    # Update only provided fields
    if notification_update.email_notifications is not None:
        notifications["email_notifications"] = notification_update.email_notifications
    if notification_update.push_notifications is not None:
        notifications["push_notifications"] = notification_update.push_notifications
    if notification_update.weekly_digest is not None:
        notifications["weekly_digest"] = notification_update.weekly_digest
    if notification_update.product_updates is not None:
        notifications["product_updates"] = notification_update.product_updates
    if notification_update.study_reminders is not None:
        notifications["study_reminders"] = notification_update.study_reminders
    
    # Update settings in database
    current_settings["notifications"] = notifications
    await update_user_settings(session, user_id, current_settings)
    
    return NotificationSettings(**notifications)


# ============================================================================
# Endpoints - Preferences
# ============================================================================

@router.get("/preferences", response_model=PreferencesSettings)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    """
    Get user's preference settings.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "language": "English",
            "timezone": "UTC",
            "date_format": "MM/DD/YYYY"
        }
    """
    settings = get_user_settings(current_user)
    return settings.preferences


@router.put("/preferences", response_model=PreferencesSettings)
async def update_preferences(
    preferences_update: UpdatePreferencesRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update user's preference settings.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "language": "English",
            "timezone": "EST",
            "date_format": "DD/MM/YYYY"
        }
    
    Response:
        Updated preference settings
    """
    user_id = current_user["email"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get current settings
    current_settings = user.settings or {}
    preferences = current_settings.get("preferences", {})
    
    # Update only provided fields
    if preferences_update.language is not None:
        preferences["language"] = preferences_update.language
    if preferences_update.timezone is not None:
        preferences["timezone"] = preferences_update.timezone
    if preferences_update.date_format is not None:
        preferences["date_format"] = preferences_update.date_format
    
    # Update settings in database
    current_settings["preferences"] = preferences
    await update_user_settings(session, user_id, current_settings)
    
    return PreferencesSettings(**preferences)


# ============================================================================
# Endpoints - Appearance
# ============================================================================

@router.get("/appearance", response_model=AppearanceSettings)
async def get_appearance(current_user: dict = Depends(get_current_user)):
    """
    Get user's appearance settings.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "theme": "system",
            "compact_mode": false,
            "animations": true
        }
    """
    settings = get_user_settings(current_user)
    return settings.appearance


@router.put("/appearance", response_model=AppearanceSettings)
async def update_appearance(
    appearance_update: UpdateAppearanceRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update user's appearance settings.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "theme": "dark",
            "compact_mode": true,
            "animations": false
        }
    
    Response:
        Updated appearance settings
    """
    user_id = current_user["email"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get current settings
    current_settings = user.settings or {}
    appearance = current_settings.get("appearance", {})
    
    # Update appearance settings
    if appearance_update.theme is not None:
        # Validate theme
        valid_themes = ["system", "light", "dark"]
        if appearance_update.theme not in valid_themes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid theme. Must be one of: {', '.join(valid_themes)}"
            )
        appearance["theme"] = appearance_update.theme
    
    if appearance_update.compact_mode is not None:
        appearance["compact_mode"] = appearance_update.compact_mode
    if appearance_update.animations is not None:
        appearance["animations"] = appearance_update.animations
    
    # Update settings in database
    current_settings["appearance"] = appearance
    await update_user_settings(session, user_id, current_settings)
    
    return AppearanceSettings(**appearance)


# ============================================================================
# Endpoints - Security
# ============================================================================

@router.post("/password/change")
async def change_password(
    password_change: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Change user password.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "current_password": "oldpass123",
            "new_password": "newpass123",
            "confirm_password": "newpass123"
        }
    
    Response:
        {
            "message": "Password changed successfully"
        }
    """
    user_id = current_user["email"]
    
    # Verify new passwords match
    if password_change.new_password != password_change.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="New passwords do not match"
        )
    
    # Validate new password (add more validation in production)
    if len(password_change.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long"
        )
    
    # Change password using database operation (includes current password verification)
    success = await change_user_password(
        session,
        user_id,
        password_change.current_password,
        password_change.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )
    
    return {
        "message": "Password changed successfully"
    }


@router.delete("/account")
async def delete_account(
    password: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete user account permanently.
    
    WARNING: This action is irreversible!
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "password": "password123"
        }
    
    Response:
        {
            "message": "Account deleted successfully"
        }
    """
    user_id = current_user["email"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify password
    from utils.auth.password import verify_password
    password_hash = user.settings.get('password_hash')
    if not password_hash or not verify_password(password, password_hash):
        raise HTTPException(
            status_code=400,
            detail="Password is incorrect"
        )
    
    # Mark user as inactive (safer than deleting)
    # In production, you might want to completely delete or anonymize data
    from sqlalchemy import update
    from database.models.user import User
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(is_active=False)
    )
    await session.commit()
    
    # Note: Token invalidation would require iterating through Redis keys
    # For now, tokens will expire naturally
    # TODO: Implement proper token blacklist or invalidation strategy
    
    return {
        "message": "Account deleted successfully"
    }


# ============================================================================
# Endpoints - Connected Services (Placeholder)
# ============================================================================

@router.get("/connections")
async def get_connections(current_user: dict = Depends(get_current_user)):
    """
    Get user's connected services.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "connections": []
        }
    """
    # Placeholder for future integration with external services
    # (Google, GitHub, Canvas, etc.)
    return {
        "connections": []
    }


@router.post("/connections/{service}")
async def connect_service(
    service: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Connect an external service to the account.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        service: Service to connect (google, github, canvas, etc.)
    
    Response:
        {
            "message": "Service connection initiated",
            "authorization_url": "https://..."
        }
    """
    # Placeholder for OAuth flow
    return {
        "message": f"Connection to {service} initiated (not implemented)",
        "authorization_url": None
    }


@router.delete("/connections/{service}")
async def disconnect_service(
    service: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Disconnect an external service from the account.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        service: Service to disconnect
    
    Response:
        {
            "message": "Service disconnected successfully"
        }
    """
    # Placeholder
    return {
        "message": f"Disconnected from {service} (not implemented)"
    }

