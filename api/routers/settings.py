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
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.auth import get_current_user  # Use unified authentication (supports both JWT and database tokens)
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


class DeleteAccountRequest(BaseModel):
    """Delete account request."""
    password: str
    confirmation_text: str = ""  # User must type "DELETE" to confirm


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
async def get_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
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
async def get_notification_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
async def get_preferences(current_user: Dict[str, Any] = Depends(get_current_user)):
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
async def get_appearance(current_user: Dict[str, Any] = Depends(get_current_user)):
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user has a password (OAuth-only users)
    has_password = bool(user.password_hash or (user.settings and user.settings.get('password_hash')))
    
    if not has_password:
        # OAuth-only user trying to change password (they don't have one)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_password",
                "message": "You don't have a password set yet. Please set a password first.",
                "suggestion": "Use the 'Set Password' feature in Security settings to create a password for your account.",
                "endpoint": "/api/auth/set-password/"
            }
        )
    
    # Verify new passwords match
    if password_change.new_password != password_change.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="New passwords do not match"
        )
    
    # Validate new password strength
    if len(password_change.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long"
        )
    
    # Additional password strength checks
    if not any(c.isupper() for c in password_change.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter"
        )
    
    if not any(c.islower() for c in password_change.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter"
        )
    
    if not any(c.isdigit() for c in password_change.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one number"
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
    delete_request: DeleteAccountRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete user account permanently.
    
    WARNING: This action is irreversible! All data will be permanently deleted.
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "password": "password123",
            "confirmation_text": "DELETE"
        }
    
    Response:
        {
            "message": "Account deleted successfully",
            "deleted_items": {...}
        }
    """
    import logging
    from sqlalchemy import delete as sql_delete
    from database.models.user import User
    from database.models.token import Token
    from database.models.payment import Customer, Subscription, PaymentHistory
    from database.models.grading import GradingSession
    from database.models.rag import DocumentVector, RAGQueryLog
    from database.models.audit import AuditLog
    from utils.auth.password import verify_password
    
    logger = logging.getLogger(__name__)
    
    user_id = current_user["email"]
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify confirmation text
    if delete_request.confirmation_text.upper() != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Please type 'DELETE' to confirm account deletion"
        )
    
    # Verify password (skip for OAuth-only users)
    if user.settings and user.settings.get('password_hash'):
        password_hash = user.settings.get('password_hash')
        if not verify_password(delete_request.password, password_hash):
            raise HTTPException(
                status_code=400,
                detail="Password is incorrect"
            )
    elif user.google_id:
        # For OAuth users without password, require them to re-authenticate
        # For now, we'll skip password check but this could be enhanced
        logger.info(f"OAuth user {user_id} deleting account without password check")
    else:
        raise HTTPException(
            status_code=400,
            detail="Unable to verify account ownership"
        )
    
    # Track what we delete for audit purposes
    deleted_items = {
        "tokens": 0,
        "documents": 0,
        "grading_sessions": 0,
        "query_logs": 0,
        "audit_logs": 0,
        "payment_records": 0,
        "subscriptions_canceled": 0
    }
    
    try:
        # 1. Cancel Stripe subscriptions if any
        try:
            # Get user's Stripe customer record
            from sqlalchemy import select
            customer_result = await session.execute(
                select(Customer).where(Customer.user_id == user_id)
            )
            customer = customer_result.scalars().first()
            
            if customer:
                # Cancel all active subscriptions in Stripe
                try:
                    from utils.payment.stripe_client import stripe_client
                    import stripe
                    
                    # Get all subscriptions for this customer
                    subscriptions_result = await session.execute(
                        select(Subscription).where(Subscription.user_id == user_id)
                    )
                    subscriptions = subscriptions_result.scalars().all()
                    
                    for sub in subscriptions:
                        try:
                            # Cancel in Stripe
                            stripe.Subscription.delete(sub.stripe_subscription_id)
                            deleted_items["subscriptions_canceled"] += 1
                            logger.info(f"Canceled Stripe subscription: {sub.stripe_subscription_id}")
                        except Exception as stripe_err:
                            logger.warning(f"Failed to cancel Stripe subscription: {stripe_err}")
                    
                except Exception as stripe_err:
                    logger.warning(f"Stripe cancellation warning: {stripe_err}")
        except Exception as e:
            logger.warning(f"Error processing Stripe cleanup: {e}")
        
        # 2. Delete all user tokens (invalidate sessions)
        token_result = await session.execute(
            sql_delete(Token).where(Token.user_id == user_id)
        )
        deleted_items["tokens"] = token_result.rowcount
        
        # 3. Delete or anonymize user documents
        doc_result = await session.execute(
            sql_delete(DocumentVector).where(DocumentVector.user_id == user_id)
        )
        deleted_items["documents"] = doc_result.rowcount
        
        # 4. Delete grading sessions (or keep for institutional records)
        # Option 1: Delete completely
        grading_result = await session.execute(
            sql_delete(GradingSession).where(GradingSession.professor_id == user.id)
        )
        deleted_items["grading_sessions"] = grading_result.rowcount
        
        # 5. Delete RAG query logs
        query_result = await session.execute(
            sql_delete(RAGQueryLog).where(RAGQueryLog.user_id == user_id)
        )
        deleted_items["query_logs"] = query_result.rowcount
        
        # 6. Keep audit logs for compliance but anonymize
        # (Don't delete audit logs - they're needed for compliance)
        # Instead, we could anonymize them
        # For now, we'll keep them as-is
        
        # 7. Delete payment records (or keep for financial compliance)
        payment_result = await session.execute(
            sql_delete(PaymentHistory).where(PaymentHistory.user_id == user_id)
        )
        deleted_items["payment_records"] = payment_result.rowcount
        
        # 8. Delete subscription records
        sub_result = await session.execute(
            sql_delete(Subscription).where(Subscription.user_id == user_id)
        )
        
        # 9. Delete customer record
        customer_result = await session.execute(
            sql_delete(Customer).where(Customer.user_id == user_id)
        )
        
        # 10. Finally, delete the user account
        await session.execute(
            sql_delete(User).where(User.user_id == user_id)
        )
        
        # Commit all deletions
        await session.commit()
        
        logger.info(f"✅ Account deleted: {user_id}, Items: {deleted_items}")
        
        return {
            "message": "Account deleted successfully. All your data has been permanently removed.",
            "deleted_items": deleted_items
        }
        
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Account deletion failed for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Account deletion failed. Please contact support. Error: {str(e)}"
        )


# ============================================================================
# Endpoints - Connected Services (Placeholder)
# ============================================================================

@router.get("/connections")
async def get_connections(current_user: Dict[str, Any] = Depends(get_current_user)):
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
    current_user: Dict[str, Any] = Depends(get_current_user)
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
    current_user: Dict[str, Any] = Depends(get_current_user)
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

