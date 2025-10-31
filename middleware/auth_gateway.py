"""
Authentication Gateway Middleware.

Enforces tenant-aware authentication for all requests:
- Validates X-Tenant-ID header presence
- Validates tenant_id claim in JWT token
- Ensures tenant_id consistency between header and token
- Treats missing tenant context as hard failure (401)

Security Invariants:
- No partial authentication allowed
- Missing tenant guard reflected in logs
- Tenant validation occurs before application logic
- All authentication failures are logged

Issue Reference: #10
"""

import logging
import json
from typing import Set, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from utils.auth.jwt_handler import verify_access_token

logger = logging.getLogger(__name__)


def _log_auth_event(
    event_type: str,
    request: Request,
    details: Dict[str, Any],
    status_code: int = 200
) -> None:
    """
    Log authentication events in structured format.
    
    Args:
        event_type: Type of auth event (e.g., "auth_success", "auth_failure")
        request: FastAPI request object
        details: Additional event details
        status_code: HTTP status code
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "path": request.url.path,
        "method": request.method,
        "status_code": status_code,
        **details
    }
    
    if status_code >= 400:
        logger.warning(f"🔒 Auth Event: {json.dumps(log_entry)}")
    else:
        logger.debug(f"✅ Auth Event: {json.dumps(log_entry)}")


class AuthGatewayMiddleware(BaseHTTPMiddleware):
    """
    Authentication Gateway Middleware with Tenant Validation.
    
    Enforces tenant-aware authentication:
    - Validates X-Tenant-ID header
    - Validates tenant_id in JWT token
    - Ensures consistency between header and token
    - Rejects requests without valid tenant context
    """
    
    def __init__(
        self,
        app,
        exempt_paths: Optional[Set[str]] = None,
    ):
        """
        Initialize authentication gateway middleware.
        
        Args:
            app: FastAPI application
            exempt_paths: Paths exempt from authentication
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or set()
    
    def _is_exempt(self, path: str) -> bool:
        """
        Check if path is exempt from authentication.
        
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
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request through authentication gateway.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response from next middleware or error response
        """
        # Skip exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        # Extract X-Tenant-ID header
        tenant_id_header = request.headers.get("X-Tenant-ID")
        
        # Extract Authorization header
        authorization = request.headers.get("Authorization")
        
        # Validate tenant_id header presence
        if not tenant_id_header or not tenant_id_header.strip():
            _log_auth_event(
                "auth_failure",
                request,
                {"reason": "missing_tenant_header", "message": "X-Tenant-ID header is required"},
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "X-Tenant-ID header is required"
                }
            )
        
        # Validate Authorization header presence
        if not authorization:
            _log_auth_event(
                "auth_failure",
                request,
                {
                    "reason": "missing_authorization",
                    "message": "Authorization header is required",
                    "tenant_id": tenant_id_header
                },
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Authorization header is required"
                }
            )
        
        # Extract JWT token
        try:
            parts = authorization.split(maxsplit=1)
            if len(parts) == 2:
                scheme, token = parts
                if scheme.lower() not in ["bearer", "token"]:
                    raise ValueError("Invalid scheme")
            else:
                token = authorization
        except (ValueError, AttributeError):
            _log_auth_event(
                "auth_failure",
                request,
                {
                    "reason": "invalid_authorization_format",
                    "message": "Invalid authorization header format",
                    "tenant_id": tenant_id_header
                },
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid authorization header format"
                }
            )
        
        # Verify JWT token and extract tenant_id
        try:
            payload = verify_access_token(token)
            tenant_id_token = payload.get("tenant_id")
        except Exception as e:
            _log_auth_event(
                "auth_failure",
                request,
                {
                    "reason": "invalid_token",
                    "message": "Invalid or expired token",
                    "tenant_id": tenant_id_header,
                    "error": str(e)
                },
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid or expired token"
                }
            )
        
        # Validate tenant_id claim in token
        if not tenant_id_token or not str(tenant_id_token).strip():
            _log_auth_event(
                "auth_failure",
                request,
                {
                    "reason": "missing_tenant_claim",
                    "message": "tenant_id claim is missing or empty in token",
                    "tenant_id": tenant_id_header
                },
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid token: missing tenant_id claim"
                }
            )
        
        # Validate tenant_id consistency
        if str(tenant_id_header).strip() != str(tenant_id_token).strip():
            _log_auth_event(
                "auth_failure",
                request,
                {
                    "reason": "tenant_mismatch",
                    "message": "tenant_id mismatch between header and token",
                    "header_tenant_id": tenant_id_header,
                    "token_tenant_id": tenant_id_token
                },
                401
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Tenant ID mismatch between header and token"
                }
            )
        
        # Authentication successful
        _log_auth_event(
            "auth_success",
            request,
            {
                "tenant_id": tenant_id_header,
                "user_id": payload.get("user_id"),
                "email": payload.get("email")
            },
            200
        )
        
        # Attach tenant_id and user info to request state for downstream use
        request.state.tenant_id = tenant_id_header
        request.state.user_id = payload.get("user_id")
        request.state.user_email = payload.get("email")
        request.state.user_role = payload.get("role")
        
        return await call_next(request)
