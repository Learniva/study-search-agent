"""
API Utilities Package

REST API-specific utilities:
- auth: Authentication, authorization (JWT, RBAC, LMS integration)
- streaming: Response streaming (SSE, async generators)
"""

from .auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_teacher,
    require_role,
    authenticate_user,
    create_token_for_user,
    validate_canvas_token,
    validate_google_classroom_token,
    RateLimiter,
    rate_limiter,
    TokenData,
    User,
)

from .streaming import (
    StreamingResponse,
    stream_llm_response,
    format_sse_message,
    stream_with_progress,
    stream_with_metadata,
    ChunkedStreamBuffer,
    simulate_streaming,
    is_streaming_supported,
    STREAMING_CONFIG,
)

__all__ = [
    # Auth
    'create_access_token',
    'decode_access_token',
    'get_current_user',
    'get_current_teacher',
    'require_role',
    'authenticate_user',
    'create_token_for_user',
    'validate_canvas_token',
    'validate_google_classroom_token',
    'RateLimiter',
    'rate_limiter',
    'TokenData',
    'User',
    
    # Streaming
    'StreamingResponse',
    'stream_llm_response',
    'format_sse_message',
    'stream_with_progress',
    'stream_with_metadata',
    'ChunkedStreamBuffer',
    'simulate_streaming',
    'is_streaming_supported',
    'STREAMING_CONFIG',
]

