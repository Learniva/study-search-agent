"""
CSRF Protection Middleware for Cookie-Based Authentication.

Implements Double Submit Cookie pattern to prevent Cross-Site Request Forgery attacks
when using httpOnly cookies for authentication.

Security Model:
1. Server generates CSRF token and sends it in:
   - httpOnly cookie (access_token)
   - Non-httpOnly cookie (csrf_token)
   - Response header (X-CSRF-Token)
2. Client includes CSRF token in request header (X-CSRF-Token)
3. Server validates that cookie and header tokens match

This prevents CSRF because:
- Attacker can't read cookies from other domains (Same-Origin Policy)
- Attacker can't set custom headers on cross-origin requests
- Even if cookies are sent automatically, header token won't match
"""

import secrets
import logging
from typing import Optional, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection using Double Submit Cookie pattern.
    
    Protects state-changing operations (POST, PUT, PATCH, DELETE)
    when using cookie-based authentication.
    """
    
    # HTTP methods that require CSRF protection
    PROTECTED_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}
    
    # Paths exempt from CSRF protection
    DEFAULT_EXEMPT_PATHS: Set[str] = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/google/callback",
        "/api/auth/google/callback/",
        "/auth/login/",
        "/auth/register/",
        "/auth/google/callback",
        "/auth/google/callback/",
    }
    
    def __init__(
        self,
        app,
        exempt_paths: Optional[Set[str]] = None,
        header_name: str = "X-CSRF-Token",
        cookie_name: str = "csrf_token",
    ):
        """
        Initialize CSRF protection middleware.
        
        Args:
            app: FastAPI application
            exempt_paths: Additional paths to exempt from CSRF protection
            header_name: Name of CSRF token header
            cookie_name: Name of CSRF token cookie
        """
        super().__init__(app)
        self.exempt_paths = self.DEFAULT_EXEMPT_PATHS.copy()
        if exempt_paths:
            self.exempt_paths.update(exempt_paths)
        self.header_name = header_name
        self.cookie_name = cookie_name
    
    def _is_exempt(self, path: str) -> bool:
        """
        Check if path is exempt from CSRF protection.
        
        Args:
            path: Request path
            
        Returns:
            True if exempt, False otherwise
        """
        # Exact match
        if path in self.exempt_paths:
            return True
        
        # Prefix match (for paths with trailing slashes or query params)
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path.rstrip("/")):
                return True
        
        return False
    
    def _generate_csrf_token(self) -> str:
        """
        Generate a secure CSRF token.
        
        Returns:
            Random CSRF token
        """
        return secrets.token_urlsafe(32)
    
    def _get_csrf_token_from_cookie(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from cookie.
        
        Args:
            request: FastAPI Request
            
        Returns:
            CSRF token or None
        """
        return request.cookies.get(self.cookie_name)
    
    def _get_csrf_token_from_header(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request header.
        
        Args:
            request: FastAPI Request
            
        Returns:
            CSRF token or None
        """
        return request.headers.get(self.header_name)
    
    def _validate_csrf_token(self, request: Request) -> bool:
        """
        Validate CSRF token using Double Submit Cookie pattern.
        
        Args:
            request: FastAPI Request
            
        Returns:
            True if valid, False otherwise
        """
        cookie_token = self._get_csrf_token_from_cookie(request)
        header_token = self._get_csrf_token_from_header(request)
        
        # Both must be present
        if not cookie_token or not header_token:
            logger.warning(
                f"CSRF validation failed: Missing token "
                f"(cookie={'present' if cookie_token else 'missing'}, "
                f"header={'present' if header_token else 'missing'})"
            )
            return False
        
        # Tokens must match (constant-time comparison)
        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning("CSRF validation failed: Token mismatch")
            return False
        
        return True
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply CSRF protection.
        
        Args:
            request: FastAPI Request
            call_next: Next middleware in chain
            
        Returns:
            Response
        """
        # Skip CSRF check for safe methods
        if request.method not in self.PROTECTED_METHODS:
            response = await call_next(request)
            
            # Generate and set CSRF token for GET requests if not present
            if request.method == "GET":
                csrf_token = self._get_csrf_token_from_cookie(request)
                if not csrf_token:
                    csrf_token = self._generate_csrf_token()
                    response.set_cookie(
                        key=self.cookie_name,
                        value=csrf_token,
                        httponly=False,  # Must be readable by JavaScript
                        secure=True,  # HTTPS only in production
                        samesite="strict",
                        path="/",
                    )
                    # Also send in header for client convenience
                    response.headers[self.header_name] = csrf_token
            
            return response
        
        # Skip CSRF check for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        # Check if request uses cookie-based auth
        has_auth_cookie = "access_token" in request.cookies
        
        # Only enforce CSRF if using cookie-based auth
        # (Header-based auth is not vulnerable to CSRF)
        if has_auth_cookie:
            if not self._validate_csrf_token(request):
                logger.error(
                    f"CSRF attack detected: {request.method} {request.url.path} "
                    f"from {request.client.host if request.client else 'unknown'}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_validation_failed",
                        "message": "CSRF token validation failed",
                        "detail": "Include X-CSRF-Token header with value from csrf_token cookie",
                    },
                )
        
        # Process request
        response = await call_next(request)
        
        return response


def generate_csrf_token() -> str:
    """
    Generate a new CSRF token.
    
    Returns:
        Secure random CSRF token
    """
    return secrets.token_urlsafe(32)


__all__ = ["CSRFProtectionMiddleware", "generate_csrf_token"]
