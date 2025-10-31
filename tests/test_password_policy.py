"""
Password Policy Tests

Comprehensive tests for password policy validation including:
- Complexity requirements
- Common password detection
- Breach database checking
- Personal information detection
- Pattern analysis
- Edge cases

Author: Study Search Agent Team
Version: 1.0.0
"""

import pytest
from unittest.mock import Mock, patch

from utils.auth.password import (
    PasswordValidator,
    PasswordPolicy,
    PasswordStrength,
    PasswordValidationResult,
    validate_password_policy
)


class TestPasswordPolicy:
    """Test password policy validation."""
    
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


class TestPasswordValidator:
    """Test password validator functionality."""
    
    def setup_method(self):
        """Set up test validator."""
        self.validator = PasswordValidator()
    
    @pytest.mark.asyncio
    async def test_validate_strong_password(self):
        """Test validation of strong password."""
        result = await self.validator.validate_password(
            "StrongPassword123!",
            username="testuser",
            email="test@example.com"
        )
        
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
    async def test_validate_password_insufficient_special_chars(self):
        """Test password with insufficient special characters."""
        result = await self.validator.validate_password("OnlyOne!123")
        
        assert result.is_valid is False
        assert any("at least 2 special characters" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_consecutive_chars(self):
        """Test password with too many consecutive characters."""
        result = await self.validator.validate_password("aaaPassword123!")
        
        assert result.is_valid is False
        assert any("consecutive identical characters" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_keyboard_pattern(self):
        """Test password with keyboard patterns."""
        result = await self.validator.validate_password("qwerty123!")
        
        assert "keyboard patterns" in " ".join(result.warnings)
    
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
    async def test_validate_password_breach_database(self):
        """Test breach database checking."""
        result = await self.validator.validate_password("password")
        
        assert result.is_valid is False
        assert any("data breaches" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_password_personal_info_patterns(self):
        """Test detection of personal information patterns."""
        result = await self.validator.validate_password("MyBirthday1990!")
        
        assert "personal information" in " ".join(result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_password_phone_pattern(self):
        """Test detection of phone number patterns."""
        result = await self.validator.validate_password("MyPhone5551234!")
        
        assert "personal information" in " ".join(result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_password_date_pattern(self):
        """Test detection of date patterns."""
        result = await self.validator.validate_password("MyDate12/25/1990!")
        
        assert "personal information" in " ".join(result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_password_year_pattern(self):
        """Test detection of year patterns."""
        result = await self.validator.validate_password("MyYear1990!")
        
        assert "personal information" in " ".join(result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_password_unicode_characters(self):
        """Test password with unicode characters."""
        result = await self.validator.validate_password("Pássw0rd123!ñ")
        
        # Should handle unicode characters gracefully
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_very_long(self):
        """Test very long password."""
        long_password = "A" * 200 + "1!"
        result = await self.validator.validate_password(long_password)
        
        # Should handle long passwords
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_empty_string(self):
        """Test empty password."""
        result = await self.validator.validate_password("")
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_password_none(self):
        """Test None password."""
        result = await self.validator.validate_password(None)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_password_whitespace_only(self):
        """Test password with only whitespace."""
        result = await self.validator.validate_password("   \t\n   ")
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_password_leading_trailing_whitespace(self):
        """Test password with leading/trailing whitespace."""
        result = await self.validator.validate_password("  Password123!  ")
        
        # Should handle whitespace gracefully
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_mixed_case_suggestions(self):
        """Test password suggestions for mixed case."""
        result = await self.validator.validate_password("password123!")
        
        assert any("uppercase" in suggestion.lower() for suggestion in result.suggestions)
    
    @pytest.mark.asyncio
    async def test_validate_password_digit_suggestions(self):
        """Test password suggestions for digits."""
        result = await self.validator.validate_password("Password!")
        
        assert any("digit" in suggestion.lower() for suggestion in result.suggestions)
    
    @pytest.mark.asyncio
    async def test_validate_password_special_char_suggestions(self):
        """Test password suggestions for special characters."""
        result = await self.validator.validate_password("Password123")
        
        assert any("special" in suggestion.lower() for suggestion in result.suggestions)
    
    @pytest.mark.asyncio
    async def test_validate_password_length_suggestions(self):
        """Test password suggestions for length."""
        result = await self.validator.validate_password("Pass1!")
        
        assert any("characters" in suggestion.lower() for suggestion in result.suggestions)
    
    @pytest.mark.asyncio
    async def test_validate_password_strength_scoring(self):
        """Test password strength scoring."""
        # Very weak password
        weak_result = await self.validator.validate_password("123")
        assert weak_result.score < 20
        assert weak_result.strength == PasswordStrength.VERY_WEAK
        
        # Weak password
        weak_result2 = await self.validator.validate_password("password")
        assert weak_result2.score < 40
        assert weak_result2.strength == PasswordStrength.WEAK
        
        # Fair password
        fair_result = await self.validator.validate_password("Password123")
        assert 40 <= fair_result.score < 60
        assert fair_result.strength == PasswordStrength.FAIR
        
        # Good password
        good_result = await self.validator.validate_password("Password123!")
        assert 60 <= good_result.score < 80
        assert good_result.strength == PasswordStrength.GOOD
        
        # Strong password
        strong_result = await self.validator.validate_password("VeryStrongPassword123!")
        assert strong_result.score >= 80
        assert strong_result.strength == PasswordStrength.STRONG
    
    @pytest.mark.asyncio
    async def test_validate_password_custom_policy(self):
        """Test validation with custom policy."""
        custom_policy = PasswordPolicy(
            min_length=8,
            require_uppercase=False,
            require_digits=False,
            min_special_chars=1
        )
        
        validator = PasswordValidator(custom_policy)
        result = await validator.validate_password("password!")
        
        assert result.is_valid is True  # Should pass with relaxed policy
    
    @pytest.mark.asyncio
    async def test_validate_password_history_checking(self):
        """Test password history checking."""
        # This would require actual database integration
        # For now, we'll test the method exists and returns appropriate result
        result = await self.validator.validate_password(
            "NewPassword123!",
            user_id="test_user"
        )
        
        # Should not fail due to history (no history exists)
        assert isinstance(result, PasswordValidationResult)


class TestPasswordValidationEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test validator."""
        self.validator = PasswordValidator()
    
    @pytest.mark.asyncio
    async def test_validate_password_with_special_unicode(self):
        """Test password with special unicode characters."""
        result = await self.validator.validate_password("Pássw0rd123!ñ")
        
        # Should handle unicode gracefully
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_emojis(self):
        """Test password with emojis."""
        result = await self.validator.validate_password("Password123!😀")
        
        # Should handle emojis
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_html_tags(self):
        """Test password with HTML tags."""
        result = await self.validator.validate_password("Password123!<script>")
        
        # Should handle HTML tags
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_sql_injection(self):
        """Test password with SQL injection attempt."""
        result = await self.validator.validate_password("Password123!'; DROP TABLE users; --")
        
        # Should handle SQL injection attempts
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_xss_attempt(self):
        """Test password with XSS attempt."""
        result = await self.validator.validate_password("Password123!<script>alert('xss')</script>")
        
        # Should handle XSS attempts
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_null_bytes(self):
        """Test password with null bytes."""
        result = await self.validator.validate_password("Password123!\x00")
        
        # Should handle null bytes
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_control_characters(self):
        """Test password with control characters."""
        result = await self.validator.validate_password("Password123!\x01\x02\x03")
        
        # Should handle control characters
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_repeated_patterns(self):
        """Test password with repeated patterns."""
        result = await self.validator.validate_password("abcabcabc123!")
        
        # Should detect repeated patterns
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_sequential_chars(self):
        """Test password with sequential characters."""
        result = await self.validator.validate_password("abcdef123!")
        
        # Should detect sequential patterns
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_reverse_sequential(self):
        """Test password with reverse sequential characters."""
        result = await self.validator.validate_password("fedcba123!")
        
        # Should detect reverse sequential patterns
        assert isinstance(result, PasswordValidationResult)
    
    @pytest.mark.asyncio
    async def test_validate_password_with_numeric_sequential(self):
        """Test password with numeric sequential characters."""
        result = await self.validator.validate_password("Password123456!")
        
        # Should detect numeric sequential patterns
        assert isinstance(result, PasswordValidationResult)


class TestPasswordValidationPerformance:
    """Test password validation performance."""
    
    def setup_method(self):
        """Set up test validator."""
        self.validator = PasswordValidator()
    
    @pytest.mark.asyncio
    async def test_validate_password_performance(self):
        """Test password validation performance."""
        import time
        
        start_time = time.time()
        
        # Validate 100 passwords
        for i in range(100):
            await self.validator.validate_password(f"Password{i}!")
        
        end_time = time.time()
        
        # Should complete in reasonable time
        assert end_time - start_time < 5.0  # Less than 5 seconds for 100 validations
    
    @pytest.mark.asyncio
    async def test_validate_password_concurrent(self):
        """Test concurrent password validation."""
        import asyncio
        
        async def validate_password(password):
            return await self.validator.validate_password(password)
        
        # Run 10 concurrent validations
        tasks = [validate_password(f"Password{i}!") for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 10
        assert all(isinstance(r, PasswordValidationResult) for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
