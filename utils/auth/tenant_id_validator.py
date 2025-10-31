#!/usr/bin/env python3
"""
Tenant ID Validator Module

This module provides ULID (Universally Unique Lexicographically Sortable Identifier) 
validation for tenant authentication. It implements strict ULID validation using 
Crockford Base32 encoding and enforces timestamp-based security policies.

Key Features:
- Validates ULID syntax (26 characters, Crockford Base32 uppercase)
- Enforces timestamp-based security policies:
  - Rejects tokens > 24 hours in the future (clock drift protection)
  - Rejects tokens > 24 hours in the past (replay attack protection)
- Provides detailed error information in non-production environments
- Zero external dependencies for maximum reliability

Security Model:
The validator implements a T3 (Timestamp-based Token) security model that prevents:
- Replay attacks using old tokens
- Clock drift attacks using future-dated tokens
- Invalid token format attacks

Note: This is a lightweight validator intended to be replaced with a database-backed
tenant existence check in production environments.

Author: Study Search Agent Team
Version: 1.0.0
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

# Module-level logger
logger = logging.getLogger(__name__)

# Constants
ULID_LENGTH = 26
TIMESTAMP_LENGTH = 10
RANDOM_LENGTH = 16

# Time windows in seconds
FUTURE_DRIFT_SECONDS = 24 * 3600  # 24 hours for production
PAST_REPLAY_SECONDS = 24 * 3600   # 24 hours for production

# Development time windows (much more permissive)
DEV_FUTURE_DRIFT_SECONDS = 30 * 24 * 3600  # 30 days
DEV_PAST_REPLAY_SECONDS = 30 * 24 * 3600   # 30 days

# Crockford Base32 character set (uppercase only)
CROCKFORD_BASE32_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Compiled regex for ULID validation
ULID_PATTERN = re.compile(rf"^[{CROCKFORD_BASE32_CHARS}]{{{ULID_LENGTH}}}$")

# Crockford Base32 character to integer mapping
CROCKFORD_BASE32_MAP = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "J": 18, "K": 19, "M": 20, "N": 21, "P": 22, "Q": 23, "R": 24, "S": 25,
    "T": 26, "V": 27, "W": 28, "X": 29, "Y": 30, "Z": 31
}


def is_valid_ulid_syntax(value: str) -> bool:
    """
    Validate ULID syntax using Crockford Base32 encoding.
    
    Args:
        value: The string to validate as a ULID
        
    Returns:
        True if the value is a valid ULID format, False otherwise
        
    Examples:
        >>> is_valid_ulid_syntax("01ARZ3NDEKTSV4RRFFQ69G5FAV")
        True
        >>> is_valid_ulid_syntax("invalid")
        False
        >>> is_valid_ulid_syntax("")
        False
    """
    if not value or not isinstance(value, str):
        return False
    
    return bool(ULID_PATTERN.match(value))


def parse_ulid_timestamp_ms(value: str) -> Optional[int]:
    """
    Extract and parse the timestamp portion of a ULID.
    
    The ULID timestamp is the first 10 characters encoded in Crockford Base32,
    representing a 48-bit unsigned integer of milliseconds since Unix epoch.
    
    Args:
        value: The ULID string to parse
        
    Returns:
        The timestamp in milliseconds since Unix epoch, or None if parsing fails
        
    Examples:
        >>> parse_ulid_timestamp_ms("01ARZ3NDEKTSV4RRFFQ69G5FAV")
        1234567890123
        >>> parse_ulid_timestamp_ms("invalid")
        None
    """
    if not value or len(value) < TIMESTAMP_LENGTH:
        return None
        
    try:
        timestamp_chars = value[:TIMESTAMP_LENGTH]
        timestamp_ms = 0
        
        for char in timestamp_chars:
            if char not in CROCKFORD_BASE32_MAP:
                return None
            timestamp_ms = (timestamp_ms << 5) | CROCKFORD_BASE32_MAP[char]
            
        return timestamp_ms
        
    except (KeyError, OverflowError, ValueError):
        logger.debug("Failed to parse ULID timestamp: %s", value)
        return None


def _format_dev_forensics(
    reason: str, 
    parsed_ts_ms: Optional[int], 
    now_ms: int, 
    trace_id: Optional[str]
) -> dict:
    """
    Format detailed error information for development environments.
    
    Args:
        reason: Human-readable reason for validation failure
        parsed_ts_ms: Parsed timestamp from ULID (if available)
        now_ms: Current timestamp in milliseconds
        trace_id: Optional trace ID for request tracking
        
    Returns:
        Dictionary containing detailed error information
    """
    parsed_ts_iso = None
    if parsed_ts_ms is not None:
        parsed_ts_iso = datetime.fromtimestamp(
            parsed_ts_ms / 1000, tz=timezone.utc
        ).isoformat()
    
    now_iso = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).isoformat()
    delta_ms = (parsed_ts_ms - now_ms) if parsed_ts_ms is not None else None
    
    return {
        "code": "AUTH_INVALID_TENANT_ULID",
        "message": reason,
        "meta": {
            "parsed_ts": parsed_ts_iso,
            "now": now_iso,
            "delta_ms": delta_ms,
            "trace_id": trace_id,
        },
    }


def validate_tenant_ulid_or_raise(
    header_value: Optional[str], 
    *, 
    env: str = "prod", 
    trace_id: Optional[str] = None
) -> str:
    """
    Validate a tenant ULID header value with comprehensive security checks.
    
    This function performs the following validations:
    1. Syntax validation (Crockford Base32, 26 characters)
    2. Timestamp parsing validation
    3. Future drift protection (rejects tokens > 24h in future)
    4. Replay attack protection (rejects tokens > 24h in past)
    
    Args:
        header_value: The ULID value from the request header
        env: Environment name ("prod", "dev", "staging") - affects error detail level
        trace_id: Optional trace ID for request tracking
        
    Returns:
        The validated and canonicalized ULID value
        
    Raises:
        HTTPException: 401 Unauthorized if validation fails
        
    Examples:
        >>> validate_tenant_ulid_or_raise("01ARZ3NDEKTSV4RRFFQ69G5FAV")
        "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        >>> validate_tenant_ulid_or_raise("invalid")
        HTTPException: 401 Unauthorized
    """
    # Check for empty or None header value
    if not header_value:
        logger.warning("Empty tenant ULID header value")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Clean and validate syntax
    cleaned_value = header_value.strip()
    if not is_valid_ulid_syntax(cleaned_value):
        logger.warning("Invalid ULID syntax: %s", cleaned_value)
        
        if env != "prod":
            current_time_ms = int(time.time() * 1000)
            error_detail = _format_dev_forensics(
                "ULID syntax invalid", None, current_time_ms, trace_id
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_detail
            )
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Parse timestamp
    parsed_timestamp_ms = parse_ulid_timestamp_ms(cleaned_value)
    if parsed_timestamp_ms is None:
        logger.warning("Failed to parse ULID timestamp: %s", cleaned_value)
        
        if env != "prod":
            current_time_ms = int(time.time() * 1000)
            error_detail = _format_dev_forensics(
                "ULID timestamp parse failure", None, current_time_ms, trace_id
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_detail
            )
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Time-based security checks
    current_time_ms = int(time.time() * 1000)
    
    # Use more permissive time windows for development
    future_drift_ms = (DEV_FUTURE_DRIFT_SECONDS if env != "prod" else FUTURE_DRIFT_SECONDS) * 1000
    past_replay_ms = (DEV_PAST_REPLAY_SECONDS if env != "prod" else PAST_REPLAY_SECONDS) * 1000
    
    # Check for future drift (clock skew protection)
    if parsed_timestamp_ms - current_time_ms > future_drift_ms:
        logger.warning(
            "ULID timestamp too far in future: %d ms ahead", 
            parsed_timestamp_ms - current_time_ms
        )
        
        if env != "prod":
            error_detail = _format_dev_forensics(
                "ULID timestamp too far in future", 
                parsed_timestamp_ms, 
                current_time_ms, 
                trace_id
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_detail
            )
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Check for replay attacks (old token protection)
    if current_time_ms - parsed_timestamp_ms > past_replay_ms:
        logger.warning(
            "ULID timestamp too old (replay attack): %d ms old", 
            current_time_ms - parsed_timestamp_ms
        )
        
        if env != "prod":
            error_detail = _format_dev_forensics(
                "ULID timestamp too old (replay)", 
                parsed_timestamp_ms, 
                current_time_ms, 
                trace_id
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_detail
            )
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # All validations passed
    logger.debug("Successfully validated tenant ULID: %s", cleaned_value)
    return cleaned_value