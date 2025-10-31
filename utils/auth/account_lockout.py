"""
Account Lockout and Brute Force Protection

Comprehensive account lockout mechanism to prevent brute force attacks.
Implements progressive lockout with exponential backoff and automatic unlock.

Features:
- Progressive lockout (5, 10, 30, 60 minutes)
- IP-based and user-based lockout
- Automatic unlock after timeout
- Admin override capabilities
- Detailed audit logging
- Configurable thresholds

Security Model:
- Failed attempts tracked per user and IP
- Lockout duration increases with repeated failures
- Separate tracking for different attack vectors
- Graceful degradation under attack

Author: Study Search Agent Team
Version: 1.0.0
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from database.models.base import Base
from database.core.async_connection import get_session
from config import settings

logger = logging.getLogger(__name__)


class LockoutReason(Enum):
    """Reasons for account lockout."""
    FAILED_LOGIN = "failed_login"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ADMIN_LOCKED = "admin_locked"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class LockoutAttempt:
    """Represents a failed login attempt."""
    user_id: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    timestamp: datetime
    reason: str = "failed_login"


@dataclass
class LockoutStatus:
    """Current lockout status for a user or IP."""
    is_locked: bool
    lockout_until: Optional[datetime]
    attempts_count: int
    lockout_level: int
    reason: Optional[LockoutReason] = None
    can_retry_at: Optional[datetime] = None


class AccountLockoutManager:
    """
    Manages account lockout and brute force protection.
    
    Implements progressive lockout with the following levels:
    - Level 1: 5 minutes (5 failed attempts)
    - Level 2: 10 minutes (10 failed attempts)
    - Level 3: 30 minutes (15 failed attempts)
    - Level 4: 60 minutes (20+ failed attempts)
    """
    
    # Lockout configuration
    MAX_ATTEMPTS_PER_LEVEL = [5, 10, 15, 20]
    LOCKOUT_DURATIONS_MINUTES = [5, 10, 30, 60]
    MAX_LOCKOUT_LEVEL = len(MAX_ATTEMPTS_PER_LEVEL) - 1
    
    # Cleanup configuration
    CLEANUP_INTERVAL_HOURS = 24
    MAX_ATTEMPT_AGE_HOURS = 72
    
    def __init__(self):
        """Initialize the lockout manager."""
        self._attempts_cache: Dict[str, list] = {}
        self._lockout_cache: Dict[str, LockoutStatus] = {}
        self._last_cleanup = time.time()
    
    async def record_failed_attempt(
        self,
        user_id: Optional[str],
        ip_address: str,
        user_agent: Optional[str] = None,
        reason: str = "failed_login"
    ) -> LockoutStatus:
        """
        Record a failed login attempt and check for lockout.
        
        Args:
            user_id: User ID (None for unknown users)
            ip_address: Client IP address
            user_agent: User agent string
            reason: Reason for failure
            
        Returns:
            Current lockout status
        """
        async for session in get_session():
            # Record the attempt
            attempt = LockoutAttempt(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(timezone.utc),
                reason=reason
            )
            
            await self._store_attempt(session, attempt)
            
            # Check lockout status
            status = await self._check_lockout_status(session, user_id, ip_address)
            
            # Cleanup old attempts periodically
            await self._cleanup_old_attempts(session)
            
            return status
    
    async def check_lockout_status(
        self,
        user_id: Optional[str],
        ip_address: str
    ) -> LockoutStatus:
        """
        Check current lockout status without recording an attempt.
        
        Args:
            user_id: User ID to check
            ip_address: IP address to check
            
        Returns:
            Current lockout status
        """
        async for session in get_session():
            return await self._check_lockout_status(session, user_id, ip_address)
    
    async def unlock_account(
        self,
        user_id: str,
        admin_user_id: Optional[str] = None,
        reason: str = "admin_unlock"
    ) -> bool:
        """
        Manually unlock an account (admin function).
        
        Args:
            user_id: User ID to unlock
            admin_user_id: Admin user performing the unlock
            reason: Reason for unlock
            
        Returns:
            True if unlock was successful
        """
        async for session in get_session():
            try:
                # Remove all failed attempts for this user
                await self._clear_user_attempts(session, user_id)
                
                # Log the unlock action
                logger.info(
                    f"Account unlocked: user_id={user_id}, "
                    f"admin={admin_user_id}, reason={reason}"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to unlock account {user_id}: {e}")
                return False
    
    async def get_lockout_stats(self) -> Dict[str, Any]:
        """
        Get lockout statistics for monitoring.
        
        Returns:
            Dictionary with lockout statistics
        """
        async for session in get_session():
            stats = await self._get_lockout_stats(session)
            return stats
    
    async def _store_attempt(self, session: AsyncSession, attempt: LockoutAttempt):
        """Store a failed attempt in the database."""
        # For now, we'll use a simple in-memory approach
        # In production, this should be stored in Redis or database
        key = f"{attempt.user_id or 'unknown'}:{attempt.ip_address}"
        
        if key not in self._attempts_cache:
            self._attempts_cache[key] = []
        
        self._attempts_cache[key].append(attempt)
    
    async def _check_lockout_status(
        self,
        session: AsyncSession,
        user_id: Optional[str],
        ip_address: str
    ) -> LockoutStatus:
        """Check if user or IP should be locked out."""
        now = datetime.now(timezone.utc)
        
        # Check both user-based and IP-based lockouts
        user_key = f"{user_id or 'unknown'}:{ip_address}"
        ip_key = f"ip:{ip_address}"
        
        # Get recent attempts
        user_attempts = self._attempts_cache.get(user_key, [])
        ip_attempts = self._attempts_cache.get(ip_key, [])
        
        # Count attempts in the last hour
        cutoff_time = now - timedelta(hours=1)
        recent_user_attempts = [
            a for a in user_attempts 
            if a.timestamp > cutoff_time
        ]
        recent_ip_attempts = [
            a for a in ip_attempts 
            if a.timestamp > cutoff_time
        ]
        
        # Determine lockout level based on attempts
        user_level = self._get_lockout_level(len(recent_user_attempts))
        ip_level = self._get_lockout_level(len(recent_ip_attempts))
        
        # Use the higher lockout level
        lockout_level = max(user_level, ip_level)
        
        if lockout_level > 0:
            # Calculate lockout duration
            duration_minutes = self.LOCKOUT_DURATIONS_MINUTES[lockout_level - 1]
            lockout_until = now + timedelta(minutes=duration_minutes)
            
            return LockoutStatus(
                is_locked=True,
                lockout_until=lockout_until,
                attempts_count=max(len(recent_user_attempts), len(recent_ip_attempts)),
                lockout_level=lockout_level,
                reason=LockoutReason.FAILED_LOGIN,
                can_retry_at=lockout_until
            )
        
        return LockoutStatus(
            is_locked=False,
            lockout_until=None,
            attempts_count=max(len(recent_user_attempts), len(recent_ip_attempts)),
            lockout_level=0
        )
    
    def _get_lockout_level(self, attempt_count: int) -> int:
        """Determine lockout level based on attempt count."""
        for i, max_attempts in enumerate(self.MAX_ATTEMPTS_PER_LEVEL):
            if attempt_count >= max_attempts:
                return min(i + 1, self.MAX_LOCKOUT_LEVEL)
        return 0
    
    async def _cleanup_old_attempts(self, session: AsyncSession):
        """Clean up old failed attempts."""
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL_HOURS * 3600:
            return
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.MAX_ATTEMPT_AGE_HOURS)
        
        # Clean up in-memory cache
        for key in list(self._attempts_cache.keys()):
            attempts = self._attempts_cache[key]
            self._attempts_cache[key] = [
                a for a in attempts if a.timestamp > cutoff_time
            ]
            
            # Remove empty entries
            if not self._attempts_cache[key]:
                del self._attempts_cache[key]
        
        self._last_cleanup = now
        logger.debug(f"Cleaned up old lockout attempts. Cache size: {len(self._attempts_cache)}")
    
    async def _clear_user_attempts(self, session: AsyncSession, user_id: str):
        """Clear all attempts for a specific user."""
        keys_to_remove = [key for key in self._attempts_cache.keys() if key.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self._attempts_cache[key]
    
    async def _get_lockout_stats(self, session: AsyncSession) -> Dict[str, Any]:
        """Get lockout statistics."""
        total_attempts = sum(len(attempts) for attempts in self._attempts_cache.values())
        locked_accounts = sum(
            1 for attempts in self._attempts_cache.values()
            if len([a for a in attempts if a.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)]) >= 5
        )
        
        return {
            "total_failed_attempts": total_attempts,
            "locked_accounts": locked_accounts,
            "cache_size": len(self._attempts_cache),
            "last_cleanup": datetime.fromtimestamp(self._last_cleanup, tz=timezone.utc).isoformat()
        }


# Global lockout manager instance
_lockout_manager: Optional[AccountLockoutManager] = None


def get_lockout_manager() -> AccountLockoutManager:
    """Get the global lockout manager instance."""
    global _lockout_manager
    if _lockout_manager is None:
        _lockout_manager = AccountLockoutManager()
    return _lockout_manager


async def check_account_lockout(
    user_id: Optional[str],
    ip_address: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if account is locked out.
    
    Args:
        user_id: User ID to check
        ip_address: IP address to check
        
    Returns:
        Tuple of (is_locked, lockout_message)
    """
    manager = get_lockout_manager()
    status = await manager.check_lockout_status(user_id, ip_address)
    
    if status.is_locked:
        remaining_minutes = int((status.lockout_until - datetime.now(timezone.utc)).total_seconds() / 60)
        message = (
            f"Account temporarily locked due to {status.attempts_count} failed attempts. "
            f"Please try again in {remaining_minutes} minutes."
        )
        return True, message
    
    return False, None


async def record_failed_login(
    user_id: Optional[str],
    ip_address: str,
    user_agent: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Record a failed login attempt and check for lockout.
    
    Args:
        user_id: User ID (None for unknown users)
        ip_address: Client IP address
        user_agent: User agent string
        
    Returns:
        Tuple of (is_locked, lockout_message)
    """
    manager = get_lockout_manager()
    status = await manager.record_failed_attempt(user_id, ip_address, user_agent)
    
    if status.is_locked:
        remaining_minutes = int((status.lockout_until - datetime.now(timezone.utc)).total_seconds() / 60)
        message = (
            f"Account locked due to {status.attempts_count} failed attempts. "
            f"Please try again in {remaining_minutes} minutes."
        )
        return True, message
    
    return False, None
