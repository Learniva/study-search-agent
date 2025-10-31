"""
Security Headers Middleware

Comprehensive security headers middleware for FastAPI applications.
Implements OWASP recommended security headers to protect against
XSS, CSRF, clickjacking, and other common web vulnerabilities.

Security Headers Implemented:
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking attacks
- X-XSS-Protection: Enables XSS filtering
- Strict-Transport-Security: Enforces HTTPS
- Referrer-Policy: Controls referrer information
- Content-Security-Policy: Prevents XSS and data injection
- Permissions-Policy: Controls browser features
- Cross-Origin-Embedder-Policy: Controls cross-origin embedding
- Cross-Origin-Opener-Policy: Controls cross-origin window access
- Cross-Origin-Resource-Policy: Controls cross-origin resource access

Author: Study Search Agent Team
Version: 1.0.0
"""

import logging
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware for comprehensive web security.
    
    Implements OWASP recommended security headers to protect against:
    - Cross-Site Scripting (XSS)
    - Cross-Site Request Forgery (CSRF)
    - Clickjacking attacks
    - MIME type confusion
    - Protocol downgrade attacks
    - Information leakage
    
    The middleware automatically adds security headers to all responses
    and can be configured per environment (dev/staging/prod).
    """
    
    def __init__(
        self,
        app,
        *,
        strict_mode: bool = None,
        hsts_max_age: int = 31536000,  # 1 year
        csp_report_uri: Optional[str] = None,
        allow_insecure_dev: bool = True
    ):
        """
        Initialize security headers middleware.
        
        Args:
            app: FastAPI application instance
            strict_mode: Enable strict security mode (default: based on environment)
            hsts_max_age: HSTS max-age in seconds (default: 1 year)
            csp_report_uri: CSP violation reporting endpoint
            allow_insecure_dev: Allow insecure headers in development
        """
        super().__init__(app)
        
        # Determine strict mode based on environment
        if strict_mode is None:
            strict_mode = not settings.is_development
        
        self.strict_mode = strict_mode
        self.hsts_max_age = hsts_max_age
        self.csp_report_uri = csp_report_uri
        self.allow_insecure_dev = allow_insecure_dev
        
        logger.info(f"SecurityHeadersMiddleware initialized - Strict mode: {strict_mode}")
    
    def _get_security_headers(self, request: Request) -> dict[str, str]:
        """
        Get security headers based on request and configuration.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            Dictionary of security headers to apply
        """
        headers = {}
        
        # X-Content-Type-Options: Prevent MIME type sniffing
        headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options: Prevent clickjacking
        headers["X-Frame-Options"] = "DENY"
        
        # X-XSS-Protection: Enable XSS filtering (legacy browsers)
        headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy: Control referrer information
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy: Control browser features
        headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=(), "
            "vibrate=(), "
            "fullscreen=(self), "
            "sync-xhr=()"
        )
        
        # Cross-Origin policies
        headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
        headers["Cross-Origin-Resource-Policy"] = "same-origin"
        
        # Content Security Policy
        csp_directives = self._build_csp_directives(request)
        if csp_directives:
            headers["Content-Security-Policy"] = csp_directives
        
        # Strict Transport Security (HTTPS only)
        if self._should_apply_hsts(request):
            headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; "
                "includeSubDomains; "
                "preload"
            )
        
        return headers
    
    def _build_csp_directives(self, request: Request) -> str:
        """
        Build Content Security Policy directives.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            CSP directive string
        """
        if not self.strict_mode and self.allow_insecure_dev:
            # Relaxed CSP for development
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        
        # Strict CSP for production
        directives = [
            "default-src 'self'",
            "script-src 'self' 'nonce-{nonce}'",  # Nonce will be replaced
            "style-src 'self' 'unsafe-inline'",  # Required for some CSS frameworks
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' https:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "media-src 'self'",
            "worker-src 'self'",
            "child-src 'self'"
        ]
        
        # Add report-uri if configured
        if self.csp_report_uri:
            directives.append(f"report-uri {self.csp_report_uri}")
        
        return "; ".join(directives)
    
    def _should_apply_hsts(self, request: Request) -> bool:
        """
        Determine if HSTS should be applied to the request.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            True if HSTS should be applied
        """
        # Only apply HSTS in production or when explicitly enabled
        if not self.strict_mode:
            return False
        
        # Check if request is over HTTPS
        is_https = (
            request.url.scheme == "https" or
            request.headers.get("x-forwarded-proto") == "https" or
            request.headers.get("x-forwarded-ssl") == "on"
        )
        
        return is_https
    
    def _generate_nonce(self) -> str:
        """
        Generate a cryptographically secure nonce for CSP.
        
        Returns:
            Random nonce string
        """
        import secrets
        return secrets.token_urlsafe(16)
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and add security headers to response.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain
            
        Returns:
            HTTP response with security headers
        """
        # Generate nonce for CSP if needed
        nonce = self._generate_nonce()
        request.state.csp_nonce = nonce
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        security_headers = self._get_security_headers(request)
        
        # Replace nonce placeholder in CSP
        if "Content-Security-Policy" in security_headers:
            csp = security_headers["Content-Security-Policy"]
            csp = csp.replace("{nonce}", nonce)
            security_headers["Content-Security-Policy"] = csp
        
        # Apply headers to response
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value
        
        # Add nonce to response headers for frontend use
        response.headers["X-CSP-Nonce"] = nonce
        
        return response


def create_security_headers_middleware(
    strict_mode: bool = None,
    hsts_max_age: int = 31536000,
    csp_report_uri: Optional[str] = None
) -> SecurityHeadersMiddleware:
    """
    Factory function to create security headers middleware.
    
    Args:
        strict_mode: Enable strict security mode
        hsts_max_age: HSTS max-age in seconds
        csp_report_uri: CSP violation reporting endpoint
        
    Returns:
        Configured SecurityHeadersMiddleware instance
    """
    def middleware_factory(app):
        return SecurityHeadersMiddleware(
            app,
            strict_mode=strict_mode,
            hsts_max_age=hsts_max_age,
            csp_report_uri=csp_report_uri
        )
    
    return middleware_factory
