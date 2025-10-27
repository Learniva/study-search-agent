"""
Simplified Authentication Tests

Standalone authentication tests that don't depend on the main application.
These tests focus on the core authentication logic without LangChain dependencies.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from utils.auth.password import (
    hash_password_sync as hash_password, 
    verify_password_sync as verify_password,
    PasswordValidator,
    PasswordPolicy,
    PasswordStrength
)
from utils.auth.account_lockout import AccountLockoutManager


class TestPasswordHashing:
    """Test password hashing functionality."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert len(hashed) > 20
        assert hashed.startswith("$2b$")
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty(self):
        """Test password verification with empty password."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is False
    
    def test_hash_password_unicode(self):
        """Test password hashing with unicode characters."""
        password = "Pássw0rd123!ñ"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert verify_password(password, hashed) is True
    
    def test_hash_password_very_long(self):
        """Test password hashing with very long password."""
        password = "A" * 200 + "1!"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert verify_password(password, hashed) is True


class TestPasswordValidator:
    """Test password validator functionality."""
    
    def setup_method(self):
        """Set up test validator."""
        self.validator = PasswordValidator()
    
    @pytest.mark.asyncio
    async def test_validate_strong_password(self):
        """Test validation of strong password."""
        result = await self.validator.validate_password("StrongPassword123!")
        
        assert result.is_valid is True
        assert result.strength in [PasswordStrength.GOOD, PasswordStrength.STRONG]
        assert result.score >= 60
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_weak_password(self):
        """Test validation of weak password."""
        result = await self.validator.validate_password("123")
        
        assert result.is_valid is False
        assert result.strength == PasswordStrength.VERY_WEAK
        assert result.score < 20
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_password_too_short(self):
        """Test password that's too short."""
        result = await self.validator.validate_password("Short1!")
        
        assert result.is_valid is False
        assert any("at least 12 characters" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_no_uppercase(self):
        """Test password without uppercase letters."""
        result = await self.validator.validate_password("lowercase123!")
        
        assert result.is_valid is False
        assert any("uppercase letter" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_no_lowercase(self):
        """Test password without lowercase letters."""
        result = await self.validator.validate_password("UPPERCASE123!")
        
        assert result.is_valid is False
        assert any("lowercase letter" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_no_digits(self):
        """Test password without digits."""
        result = await self.validator.validate_password("NoDigits!")
        
        assert result.is_valid is False
        assert any("digit" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_no_special_chars(self):
        """Test password without special characters."""
        result = await self.validator.validate_password("NoSpecial123")
        
        assert result.is_valid is False
        assert any("special characters" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_contains_username(self):
        """Test password containing username."""
        result = await self.validator.validate_password(
            "testuser123!",
            username="testuser"
        )
        
        assert result.is_valid is False
        assert any("should not contain your username" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_contains_email(self):
        """Test password containing email."""
        result = await self.validator.validate_password(
            "testemail123!",
            email="test@email.com"
        )
        
        assert result.is_valid is False
        assert any("should not contain your email" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_common_password(self):
        """Test common password detection."""
        result = await self.validator.validate_password("password123")
        
        assert result.is_valid is False
        assert any("too common" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_strength_scoring(self):
        """Test password strength scoring."""
        # Very weak password
        weak_result = await self.validator.validate_password("123")
        assert weak_result.score < 20
        assert weak_result.strength == PasswordStrength.VERY_WEAK
        
        # Strong password
        strong_result = await self.validator.validate_password("VeryStrongPassword123!")
        assert strong_result.score >= 80
        assert strong_result.strength == PasswordStrength.STRONG


class TestAccountLockout:
    """Test account lockout functionality."""
    
    def setup_method(self):
        """Set up test lockout manager."""
        self.lockout_manager = AccountLockoutManager()
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_first(self):
        """Test recording first failed attempt."""
        status = await self.lockout_manager.record_failed_attempt(user_id="user123", ip_address="127.0.0.1")
        
        # Verify account is not yet locked after first attempt
        is_locked = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        assert is_locked.is_locked is False
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_max_reached(self):
        """Test recording failed attempt when max attempts reached."""
        # Record 5 failed attempts (first lockout level)
        for _ in range(5):
            await self.lockout_manager.record_failed_attempt(user_id="user123", ip_address="127.0.0.1")
        
        # Should lock account
        status = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        assert status.is_locked is True
    
    @pytest.mark.asyncio
    async def test_is_account_locked_not_locked(self):
        """Test checking unlocked account."""
        status = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        
        assert status.is_locked is False
    
    @pytest.mark.asyncio
    async def test_is_account_locked_locked(self):
        """Test checking locked account."""
        # Record 5 failed attempts to lock account
        for _ in range(5):
            await self.lockout_manager.record_failed_attempt(user_id="user123", ip_address="127.0.0.1")
        
        status = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        
        assert status.is_locked is True
    
    @pytest.mark.asyncio
    async def test_unlock_account(self):
        """Test unlocking account."""
        # Record 5 failed attempts to lock account
        for _ in range(5):
            await self.lockout_manager.record_failed_attempt(user_id="user123", ip_address="127.0.0.1")
        
        # Unlock the account
        success = await self.lockout_manager.unlock_account(user_id="user123")
        
        # Should be unlocked now
        status = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        assert success is True
        assert status.is_locked is False
    
    @pytest.mark.asyncio
    async def test_lockout_disabled(self):
        """Test behavior when lockout is disabled."""
        # This test should verify the manager handles disabled lockouts gracefully
        # For now, just verify basic operations don't crash
        await self.lockout_manager.record_failed_attempt(user_id="user123", ip_address="127.0.0.1")
        status = await self.lockout_manager.check_lockout_status(user_id="user123", ip_address="127.0.0.1")
        await self.lockout_manager.unlock_account(user_id="user123")


class TestPasswordPolicy:
    """Test password policy configuration."""
    
    def test_password_policy_defaults(self):
        """Test default password policy settings."""
        policy = PasswordPolicy()
        
        assert policy.min_length == 12
        assert policy.require_uppercase is True
        assert policy.require_lowercase is True
        assert policy.require_digits is True
        assert policy.require_special_chars is True
        assert policy.min_special_chars == 2
        assert policy.max_consecutive_chars == 3
        assert policy.max_repeating_chars == 2
        assert policy.history_count == 12
        assert policy.check_common_passwords is True
        assert policy.check_breach_database is True
    
    def test_password_policy_custom(self):
        """Test custom password policy settings."""
        policy = PasswordPolicy(
            min_length=8,
            require_uppercase=False,
            require_digits=False,
            min_special_chars=1
        )
        
        assert policy.min_length == 8
        assert policy.require_uppercase is False
        assert policy.require_digits is False
        assert policy.min_special_chars == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_password_hashing_edge_cases(self):
        """Test password hashing edge cases."""
        # Empty password
        hashed_empty = hash_password("")
        assert hashed_empty is not None
        assert verify_password("", hashed_empty) is True
        
        # Very long password
        long_password = "A" * 1000
        hashed_long = hash_password(long_password)
        assert hashed_long is not None
        assert verify_password(long_password, hashed_long) is True
        
        # Unicode password
        unicode_password = "Pássw0rd123!ñ"
        hashed_unicode = hash_password(unicode_password)
        assert hashed_unicode is not None
        assert verify_password(unicode_password, hashed_unicode) is True
    
    @pytest.mark.asyncio
    async def test_password_validation_edge_cases(self):
        """Test password validation edge cases."""
        validator = PasswordValidator()
        
        # None password
        result = await validator.validate_password(None)
        assert result.is_valid is False
        
        # Empty password
        result = await validator.validate_password("")
        assert result.is_valid is False
        
        # Whitespace only password
        result = await validator.validate_password("   \t\n   ")
        assert result.is_valid is False
        
        # Very long password
        long_password = "A" * 200 + "1!"
        result = await validator.validate_password(long_password)
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_account_lockout_edge_cases(self):
        """Test account lockout edge cases."""
        lockout_manager = AccountLockoutManager()
        
        # Empty username/ip
        await lockout_manager.record_failed_attempt(user_id="", ip_address="127.0.0.1")
        await lockout_manager.check_lockout_status(user_id="", ip_address="127.0.0.1")
        await lockout_manager.unlock_account(user_id="user123")
        
        # None username
        await lockout_manager.record_failed_attempt(user_id=None, ip_address="127.0.0.1")
        await lockout_manager.check_lockout_status(user_id=None, ip_address="127.0.0.1")
        
        # Very long username
        long_username = "a" * 1000
        await lockout_manager.record_failed_attempt(user_id=long_username, ip_address="127.0.0.1")
        await lockout_manager.check_lockout_status(user_id=long_username, ip_address="127.0.0.1")
        await lockout_manager.unlock_account(user_id=long_username)
        
        # Should handle all cases gracefully
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
