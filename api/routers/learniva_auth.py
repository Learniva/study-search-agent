"""
Learniva-compatible authentication adapter.

This module provides Django REST Framework style token authentication
to make the Study Search Agent backend compatible with the Learniva frontend.

Usage:
    Add to api/app.py:
    from api.routers.learniva_auth import router as learniva_auth_router
    app.include_router(learniva_auth_router)

Production Notes:
    - Replace USERS_DB with PostgreSQL/database lookup
    - Replace TOKEN_STORE with Redis
    - Implement proper password hashing (bcrypt/argon2)
    - Add email verification
    - Add password reset flow
    - Add rate limiting
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets
from datetime import datetime, timedelta

router = APIRouter(prefix="/api", tags=["learniva-auth"])

# ============================================================================
# Configuration
# ============================================================================

# Token expiry (24 hours for development, consider longer for production)
TOKEN_EXPIRY = timedelta(hours=24)

# In-memory stores (REPLACE WITH DATABASE IN PRODUCTION!)
TOKEN_STORE = {}  # Use Redis in production
USERS_DB = {}     # Use PostgreSQL in production


# ============================================================================
# Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request body."""
    username: str  # Can be email or username
    password: str


class LoginResponse(BaseModel):
    """Login response matching Learniva frontend expectations."""
    token: str
    user: dict


class RegisterRequest(BaseModel):
    """Registration request body."""
    username: str
    email: EmailStr
    password: str
    password2: str


class UserResponse(BaseModel):
    """User data response."""
    id: int
    pk: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: str  # student, teacher, admin


# ============================================================================
# Helper Functions
# ============================================================================

def create_token(user_id: int, role: str) -> str:
    """
    Generate authentication token.
    
    Args:
        user_id: User's unique identifier
        role: User role (student, teacher, admin)
    
    Returns:
        Secure random token string
    """
    token = secrets.token_urlsafe(32)
    TOKEN_STORE[token] = {
        "user_id": user_id,
        "role": role,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + TOKEN_EXPIRY
    }
    return token


def verify_token(token: str) -> Optional[dict]:
    """
    Verify token validity and return associated data.
    
    Args:
        token: Token string to verify
    
    Returns:
        Token data if valid, None if invalid or expired
    """
    token_data = TOKEN_STORE.get(token)
    if not token_data:
        return None
    
    # Check expiration
    if datetime.now() > token_data["expires_at"]:
        del TOKEN_STORE[token]
        return None
    
    return token_data


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Look up user by ID in database."""
    for email, user in USERS_DB.items():
        if user["id"] == user_id:
            return user
    return None


def get_user_by_username_or_email(username: str) -> Optional[dict]:
    """Look up user by username or email."""
    # Try email first
    user = USERS_DB.get(username)
    if user:
        return user
    
    # Try username
    for email, u in USERS_DB.items():
        if u["username"] == username:
            return u
    
    return None


# ============================================================================
# Dependencies
# ============================================================================

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency to extract and validate user from Authorization header.
    
    Expected header format: "Token abc123..."
    
    Args:
        authorization: Authorization header value
    
    Returns:
        User dictionary
    
    Raises:
        HTTPException: If auth fails
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )
    
    # Parse "Token xyz" format (Django REST Framework style)
    try:
        scheme, token = authorization.split(maxsplit=1)
        if scheme.lower() != "token":
            raise ValueError("Invalid scheme")
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: 'Token <token>'"
        )
    
    # Verify token
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    # Find user
    user = get_user_by_id(token_data["user_id"])
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )
    
    return user


# ============================================================================
# Initialization (Development Only)
# ============================================================================

def initialize_demo_users():
    """
    Create demo users for development/testing.
    
    WARNING: Remove in production!
    """
    if not USERS_DB:  # Only initialize if empty
        USERS_DB["student@example.com"] = {
            "id": 1,
            "pk": 1,
            "username": "student",
            "email": "student@example.com",
            "password": "password123",  # HASH THIS IN PRODUCTION!
            "first_name": "John",
            "last_name": "Doe",
            "role": "student"
        }
        USERS_DB["teacher@example.com"] = {
            "id": 2,
            "pk": 2,
            "username": "teacher",
            "email": "teacher@example.com",
            "password": "password123",  # HASH THIS IN PRODUCTION!
            "first_name": "Jane",
            "last_name": "Smith",
            "role": "teacher"
        }
        USERS_DB["admin@example.com"] = {
            "id": 3,
            "pk": 3,
            "username": "admin",
            "email": "admin@example.com",
            "password": "password123",  # HASH THIS IN PRODUCTION!
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin"
        }


# Initialize demo users
initialize_demo_users()


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/login/", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return token.
    
    Compatible with Learniva frontend login flow.
    Accepts username or email + password.
    
    Request Body:
        {
            "username": "user@example.com",  # or username
            "password": "password123"
        }
    
    Response:
        {
            "token": "abc123...",
            "user": {
                "id": 1,
                "pk": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe"
            }
        }
    """
    # Find user
    user = get_user_by_username_or_email(request.username)
    
    # Check credentials (IMPLEMENT PROPER PASSWORD HASHING IN PRODUCTION!)
    if not user or user["password"] != request.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    # Create token
    token = create_token(user["id"], user["role"])
    
    # Return response matching Learniva format
    return LoginResponse(
        token=token,
        user={
            "id": user["id"],
            "pk": user["pk"],
            "username": user["username"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"]
        }
    )


@router.post("/logout/")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user by invalidating token.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "detail": "Successfully logged out"
        }
    """
    if authorization:
        try:
            _, token = authorization.split(maxsplit=1)
            if token in TOKEN_STORE:
                del TOKEN_STORE[token]
        except:
            pass  # Ignore errors, logout anyway
    
    return {"detail": "Successfully logged out"}


@router.post("/auth/registration/")
async def register(request: RegisterRequest):
    """
    Register new user.
    
    Compatible with Learniva frontend registration flow.
    
    Request Body:
        {
            "username": "johndoe",
            "email": "john@example.com",
            "password": "password123",
            "password2": "password123"
        }
    
    Response:
        {
            "user": {
                "id": 4,
                "username": "johndoe",
                "email": "john@example.com"
            },
            "token": "abc123..."
        }
    """
    # Validate passwords match
    if request.password != request.password2:
        raise HTTPException(
            status_code=400,
            detail={"password2": ["Passwords do not match"]}
        )
    
    # Check if email exists
    if request.email in USERS_DB:
        raise HTTPException(
            status_code=400,
            detail={"email": ["User with this email already exists"]}
        )
    
    # Check if username exists
    if get_user_by_username_or_email(request.username):
        raise HTTPException(
            status_code=400,
            detail={"username": ["User with this username already exists"]}
        )
    
    # Create new user
    new_id = len(USERS_DB) + 1
    USERS_DB[request.email] = {
        "id": new_id,
        "pk": new_id,
        "username": request.username,
        "email": request.email,
        "password": request.password,  # HASH THIS IN PRODUCTION!
        "first_name": "",
        "last_name": "",
        "role": "student"  # Default role
    }
    
    # Create token
    token = create_token(new_id, "student")
    
    return {
        "user": {
            "id": new_id,
            "username": request.username,
            "email": request.email
        },
        "token": token
    }


@router.get("/auth/user/", response_model=UserResponse)
async def get_user(current_user: dict = Depends(get_current_user)):
    """
    Get authenticated user data.
    
    Compatible with Learniva frontend user data flow.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "id": 1,
            "pk": 1,
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "student"
        }
    """
    return UserResponse(
        id=current_user["id"],
        pk=current_user["pk"],
        username=current_user["username"],
        email=current_user["email"],
        first_name=current_user.get("first_name", ""),
        last_name=current_user.get("last_name", ""),
        role=current_user["role"]
    )


# ============================================================================
# Additional Endpoints (Optional - implement as needed)
# ============================================================================

@router.post("/password/reset/")
async def request_password_reset(email: EmailStr):
    """
    Request password reset email.
    
    TODO: Implement email sending
    """
    return {
        "detail": "Password reset email sent (not implemented)"
    }


@router.post("/password/reset/confirm/")
async def confirm_password_reset(
    uid: str,
    token: str,
    new_password1: str,
    new_password2: str
):
    """
    Confirm password reset with token.
    
    TODO: Implement password reset logic
    """
    return {
        "detail": "Password reset successful (not implemented)"
    }


@router.post("/password/change/")
async def change_password(
    old_password: str,
    new_password1: str,
    new_password2: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Change user password.
    
    TODO: Implement password change logic
    """
    return {
        "detail": "Password changed successfully (not implemented)"
    }

