"""
Cookie-based Authentication Configuration.

Provides secure httpOnly cookie settings for token storage,
eliminating client-side token exposure and XSS vulnerabilities.

Security Features:
- httpOnly: Prevents JavaScript access to cookies
- Secure: HTTPS-only transmission (disabled in dev for localhost)
- SameSite=strict: CSRF protection
- Short-lived access tokens
- Path restrictions
"""

import os
from typing import Optional
from datetime import timedelta
from fastapi import Response, Request
from config.settings import settings


class CookieConfig:
    """Secure cookie configuration for authentication tokens."""
    
    # Cookie names
    ACCESS_TOKEN_COOKIE = "access_token"
    REFRESH_TOKEN_COOKIE = "refresh_token"
    CSRF_TOKEN_COOKIE = "csrf_token"
    
    # Cookie settings
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # None = current domain
    COOKIE_PATH = "/"
    
    # Security settings
    HTTP_ONLY = True  # Prevent JavaScript access (XSS protection)
    SECURE = not settings.is_development  # HTTPS-only in production
    SAME_SITE = "strict"  # CSRF protection (strict/lax/none)
    
    # Token lifetimes
    ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")) * 60  # 15 minutes in seconds
    REFRESH_TOKEN_MAX_AGE = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")) * 24 * 60 * 60  # 7 days in seconds
    CSRF_TOKEN_MAX_AGE = ACCESS_TOKEN_MAX_AGE  # Same as access token
    
    @classmethod
    def set_access_token_cookie(
        cls,
        response: Response,
        token: str,
        max_age: Optional[int] = None
    ) -> None:
        """
        Set access token as httpOnly cookie.
        
        Args:
            response: FastAPI Response object
            token: Access token value
            max_age: Optional custom max age in seconds
        """
        response.set_cookie(
            key=cls.ACCESS_TOKEN_COOKIE,
            value=token,
            max_age=max_age or cls.ACCESS_TOKEN_MAX_AGE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=cls.HTTP_ONLY,
            samesite=cls.SAME_SITE,
        )
    
    @classmethod
    def set_refresh_token_cookie(
        cls,
        response: Response,
        token: str,
        max_age: Optional[int] = None
    ) -> None:
        """
        Set refresh token as httpOnly cookie.
        
        Args:
            response: FastAPI Response object
            token: Refresh token value
            max_age: Optional custom max age in seconds
        """
        response.set_cookie(
            key=cls.REFRESH_TOKEN_COOKIE,
            value=token,
            max_age=max_age or cls.REFRESH_TOKEN_MAX_AGE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=cls.HTTP_ONLY,
            samesite=cls.SAME_SITE,
        )
    
    @classmethod
    def set_csrf_token_cookie(
        cls,
        response: Response,
        token: str
    ) -> None:
        """
        Set CSRF token cookie (NOT httpOnly - needs to be readable by JS).
        
        Args:
            response: FastAPI Response object
            token: CSRF token value
        """
        response.set_cookie(
            key=cls.CSRF_TOKEN_COOKIE,
            value=token,
            max_age=cls.CSRF_TOKEN_MAX_AGE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=False,  # Must be readable by JavaScript for CSRF protection
            samesite=cls.SAME_SITE,
        )
    
    @classmethod
    def get_access_token_from_cookie(cls, request: Request) -> Optional[str]:
        """
        Extract access token from cookie.
        
        Args:
            request: FastAPI Request object
            
        Returns:
            Access token or None if not present
        """
        return request.cookies.get(cls.ACCESS_TOKEN_COOKIE)
    
    @classmethod
    def get_refresh_token_from_cookie(cls, request: Request) -> Optional[str]:
        """
        Extract refresh token from cookie.
        
        Args:
            request: FastAPI Request object
            
        Returns:
            Refresh token or None if not present
        """
        return request.cookies.get(cls.REFRESH_TOKEN_COOKIE)
    
    @classmethod
    def get_csrf_token_from_cookie(cls, request: Request) -> Optional[str]:
        """
        Extract CSRF token from cookie.
        
        Args:
            request: FastAPI Request object
            
        Returns:
            CSRF token or None if not present
        """
        return request.cookies.get(cls.CSRF_TOKEN_COOKIE)
    
    @classmethod
    def clear_auth_cookies(cls, response: Response) -> None:
        """
        Clear all authentication cookies (logout).
        
        Args:
            response: FastAPI Response object
        """
        # Clear access token
        response.delete_cookie(
            key=cls.ACCESS_TOKEN_COOKIE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=cls.HTTP_ONLY,
            samesite=cls.SAME_SITE,
        )
        
        # Clear refresh token
        response.delete_cookie(
            key=cls.REFRESH_TOKEN_COOKIE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=cls.HTTP_ONLY,
            samesite=cls.SAME_SITE,
        )
        
        # Clear CSRF token
        response.delete_cookie(
            key=cls.CSRF_TOKEN_COOKIE,
            path=cls.COOKIE_PATH,
            domain=cls.COOKIE_DOMAIN,
            secure=cls.SECURE,
            httponly=False,
            samesite=cls.SAME_SITE,
        )
    
    @classmethod
    def get_token_from_cookie_or_header(
        cls,
        request: Request,
        authorization: Optional[str] = None
    ) -> Optional[str]:
        """
        Get token from cookie first, fall back to Authorization header.
        This supports backward compatibility during migration.
        
        Args:
            request: FastAPI Request object
            authorization: Optional Authorization header value
            
        Returns:
            Token string or None
        """
        # Try cookie first (preferred method)
        token = cls.get_access_token_from_cookie(request)
        if token:
            return token
        
        # Fall back to Authorization header for backward compatibility
        if authorization:
            try:
                parts = authorization.split(maxsplit=1)
                if len(parts) == 2:
                    scheme, token = parts
                    if scheme.lower() in ["token", "bearer"]:
                        return token
                else:
                    return authorization
            except (ValueError, AttributeError):
                pass
        
        return None


# Convenience functions
def set_auth_cookies(
    response: Response,
    access_token: str,
    csrf_token: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> None:
    """
    Set all authentication cookies at once.
    
    Args:
        response: FastAPI Response object
        access_token: Access token value
        csrf_token: Optional CSRF token value
        refresh_token: Optional refresh token value
    """
    CookieConfig.set_access_token_cookie(response, access_token)
    
    if csrf_token:
        CookieConfig.set_csrf_token_cookie(response, csrf_token)
    
    if refresh_token:
        CookieConfig.set_refresh_token_cookie(response, refresh_token)


def clear_auth_cookies(response: Response) -> None:
    """
    Clear all authentication cookies (logout).
    
    Args:
        response: FastAPI Response object
    """
    CookieConfig.clear_auth_cookies(response)


__all__ = [
    "CookieConfig",
    "set_auth_cookies",
    "clear_auth_cookies",
]
