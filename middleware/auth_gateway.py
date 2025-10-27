"""
Authentication Gateway Middleware

This module provides a comprehensive authentication gateway middleware for FastAPI
applications. It implements a paranoid security model with multiple layers of
protection including tenant validation, JWT verification, and CORS handling.

Security Features:
- Global authentication enforcement for all routes (except exempt paths)
- Tenant-first validation using ULID_STRICT format
- Strict JWT Bearer token validation
- CORS preflight handling with origin whitelisting
- Structured JSON logging for security events
- Environment-aware error responses (silent in prod, detailed in dev)
- Signature anomaly detection and audit logging
- Request context injection for downstream handlers

Architecture:
The middleware follows a tenant-first approach where tenant validation occurs
before JWT verification, ensuring that all requests are properly scoped to
valid tenants before processing authentication tokens.

Usage:
    from middleware.auth_gateway import AuthGatewayMiddleware
    app.add_middleware(AuthGatewayMiddleware, exempt_paths=["/auth/google/callback"])

Author: Study Search Agent Team
Version: 1.0.0
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from utils.auth.jwt_handler import verify_access_token
from utils.auth.tenant_id_validator import validate_tenant_ulid_or_raise

# Module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _log_auth_event(
    status: str,
    reason: str,
    request: Request,
    trace_id: Optional[str] = None,
    extra: Optional[Dict] = None
) -> None:
    """
    Log structured authentication events in JSON format.
    
    This function creates structured log entries for security auditing and
    monitoring purposes. All authentication events are logged with consistent
    structure for easy parsing and analysis.
    
    Args:
        status: Authentication status ("pass", "fail")
        reason: Reason for the status (e.g., "auth_ok", "tenant_validation")
        request: The incoming HTTP request
        trace_id: Optional trace ID for request correlation
        extra: Additional metadata to include in the log entry
        
    Examples:
        >>> _log_auth_event("pass", "auth_ok", request, "trace-123", {"user_id": "user-456"})
        # Logs: {"event": "auth", "status": "pass", "reason": "auth_ok", ...}
    """
    entry = {
        "event": "auth",
        "status": status,
        "reason": reason,
        "path": request.url.path,
        "method": request.method,
        "client": request.client.host if request.client else None,
        "time": datetime.now(timezone.utc).isoformat(),
        "env": getattr(settings, "ENV", "prod"),
    }
    
    if trace_id:
        entry["trace_id"] = trace_id
    
    if extra:
        entry["meta"] = extra
    
    # Emit structured JSON log entry
    logger.info(json.dumps(entry))


def _is_cors_allowed(origin: Optional[str]) -> bool:
    """
    Check if the given origin is allowed for CORS requests.
    
    Args:
        origin: The origin header value from the request
        
    Returns:
        True if the origin is in the allowed list, False otherwise
        
    Examples:
        >>> _is_cors_allowed("https://example.com")
        True
        >>> _is_cors_allowed("https://malicious.com")
        False
        >>> _is_cors_allowed(None)
        False
    """
    if not origin:
        return False
    
    allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
    return origin in allowed_origins


def _create_error_response(
    request: Request,
    status_code: int,
    content: Dict,
    trace_id: Optional[str] = None
) -> Response:
    """
    Create an appropriate error response based on environment and Accept header.
    
    Args:
        request: The incoming HTTP request
        status_code: HTTP status code for the response
        content: Error content dictionary
        trace_id: Optional trace ID for logging
        
    Returns:
        Appropriate Response object (JSON or PlainText)
    """
    env = getattr(settings, "ENV", "prod")
    accept_header = request.headers.get("accept", "")
    
    # In production, return silent 401 responses
    if env == "prod":
        return Response(status_code=status_code)
    
    # In development/staging, return detailed responses
    if "application/json" in accept_header:
        return JSONResponse(status_code=status_code, content=content)
    
    return PlainTextResponse(status_code=status_code, content=content["message"])


class AuthGatewayMiddleware(BaseHTTPMiddleware):
    """
    Authentication Gateway Middleware for FastAPI applications.
    
    This middleware implements a comprehensive authentication system with the
    following security features:
    
    - Tenant validation using ULID_STRICT format
    - JWT Bearer token verification
    - CORS preflight handling
    - Structured security logging
    - Environment-aware error responses
    - Request context injection
    
    The middleware follows a paranoid security model where all requests are
    authenticated unless explicitly exempted.
    
    Attributes:
        exempt_paths: Set of paths that bypass authentication
        
    Examples:
        >>> middleware = AuthGatewayMiddleware(app, exempt_paths=["/health", "/docs"])
        >>> app.add_middleware(AuthGatewayMiddleware, exempt_paths=["/auth/callback"])
    """
    
    def __init__(self, app, *, exempt_paths: Optional[List[str]] = None):
        """
        Initialize the authentication gateway middleware.
        
        Args:
            app: The FastAPI application instance
            exempt_paths: List of paths that should bypass authentication
        """
        super().__init__(app)
        self.exempt_paths = set(exempt_paths or [])
        logger.info(f"AuthGatewayMiddleware initialized with exempt paths: {self.exempt_paths}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process incoming requests through the authentication gateway.
        
        This method implements the main authentication flow:
        1. Check if path is exempt from authentication
        2. Handle CORS preflight requests
        3. Validate tenant ID header
        4. Validate and verify JWT token
        5. Inject user context into request state
        6. Proceed to route handler
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain
            
        Returns:
            HTTP response from the next handler or authentication error response
        """
        # Extract trace ID for request correlation
        trace_id = (
            request.headers.get("X-Correlation-ID") or 
            request.headers.get("X-Trace-ID")
        )
        
        # Check if path is exempt from authentication
        if request.url.path in self.exempt_paths:
            logger.debug(f"Exempt path accessed: {request.url.path}")
            return await call_next(request)
        
        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            origin = request.headers.get("origin")
            if _is_cors_allowed(origin):
                logger.debug(f"CORS preflight allowed for origin: {origin}")
                return await call_next(request)
            else:
                logger.warning(f"CORS preflight denied for origin: {origin}")
                # Fall through to require authentication
        
        # Tenant validation (tenant-first approach)
        tenant_header = request.headers.get("X-Tenant-ID")
        try:
            validated_tenant = validate_tenant_ulid_or_raise(
                tenant_header,
                env=getattr(settings, "ENV", "prod"),
                trace_id=trace_id
            )
        except Exception as e:
            error_detail = getattr(e, "detail", str(e))
            _log_auth_event(
                "fail",
                "tenant_validation",
                request,
                trace_id,
                {"error": str(error_detail)}
            )
            
            content = {
                "code": "AUTH_INVALID_TENANT",
                "message": "Invalid or missing tenant ID",
                "meta": {"hint": "X-Tenant-ID header required with valid ULID"}
            }
            
            return _create_error_response(request, 401, content, trace_id)
        
        # Authorization header validation
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            _log_auth_event("fail", "missing_or_malformed_authorization", request, trace_id)
            
            content = {
                "code": "AUTH_INVALID",
                "message": "Authorization header required",
                "meta": {"hint": "Use exact 'Bearer <token>' header"}
            }
            
            return _create_error_response(request, 401, content, trace_id)
        
        # Extract and validate Bearer token
        auth_parts = auth_header.split(" ", 1)
        if len(auth_parts) != 2:
            _log_auth_event("fail", "malformed_authorization", request, trace_id)
            return Response(status_code=401)
        
        scheme, token = auth_parts
        if scheme != "Bearer":
            _log_auth_event(
                "fail",
                "authorization_scheme_mismatch",
                request,
                trace_id,
                {"scheme": scheme}
            )
            return Response(status_code=401)
        
        # JWT token verification
        try:
            payload = verify_access_token(token)
        except Exception as e:
            # Log signature anomalies and other JWT verification failures
            _log_auth_event(
                "fail",
                "token_verify_failed",
                request,
                trace_id,
                {"error": str(e)}
            )
            
            # TODO: Integrate throttling/IP blacklisting hooks here for active defense
            logger.warning(f"JWT verification failed: {str(e)}")
            return Response(status_code=401)
        
        # Inject user and tenant context into request state
        request.state.user = payload
        request.state.tenant = validated_tenant
        
        # Log successful authentication
        _log_auth_event(
            "pass",
            "auth_ok",
            request,
            trace_id,
            {
                "user_id": payload.get("user_id"),
                "role": payload.get("role"),
                "tenant": validated_tenant
            }
        )
        
        # Proceed to the next handler in the chain
        return await call_next(request)