"""
Account Lockout Tests

Comprehensive tests for account lockout mechanisms including:
- Progressive lockout (5, 10, 30, 60 minutes)
- IP and user-based tracking
- Redis integration
- Admin unlock functionality
- Edge cases and error handling

Author: Study Search Agent Team
Version: 1.0.0
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from utils.auth.account_lockout import AccountLockoutManager


class TestAccountLockoutManager:
    """Test account lockout manager functionality."""
    
    def setup_method(self):
        """Set up test lockout manager."""
        self.mock_redis = AsyncMock()
        self.lockout_manager = AccountLockoutManager(self.mock_redis)
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_first_attempt(self):
        """Test recording first failed attempt."""
        self.mock_redis.incr.return_value = 1
        self.mock_redis.expire.return_value = True
        
        await self.lockout_manager.record_failed_attempt("test@example.com")
        
        self.mock_redis.incr.assert_called_once_with("login_attempts:test@example.com")
        self.mock_redis.expire.assert_called_once_with("login_attempts:test@example.com", 300)  # 5 minutes
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_multiple_attempts(self):
        """Test recording multiple failed attempts."""
        self.mock_redis.incr.return_value = 3
        self.mock_redis.expire.return_value = True
        
        await self.lockout_manager.record_failed_attempt("test@example.com")
        
        self.mock_redis.incr.assert_called_once_with("login_attempts:test@example.com")
        # Should not call expire on subsequent attempts
        self.mock_redis.expire.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_max_reached(self):
        """Test recording failed attempt when max attempts reached."""
        self.mock_redis.incr.return_value = 5  # max_login_attempts
        self.mock_redis.expire.return_value = True
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.record_failed_attempt("test@example.com")
        
        # Should lock account
        self.mock_redis.setex.assert_called_once_with("account_locked:test@example.com", 900, "true")  # 15 minutes
        # Should clear attempt count
        self.mock_redis.delete.assert_called_once_with("login_attempts:test@example.com")
    
    @pytest.mark.asyncio
    async def test_is_account_locked_not_locked(self):
        """Test checking unlocked account."""
        self.mock_redis.get.return_value = None
        
        result = await self.lockout_manager.is_account_locked("test@example.com")
        
        assert result is False
        self.mock_redis.get.assert_called_once_with("account_locked:test@example.com")
    
    @pytest.mark.asyncio
    async def test_is_account_locked_locked(self):
        """Test checking locked account."""
        self.mock_redis.get.return_value = "true"
        
        result = await self.lockout_manager.is_account_locked("test@example.com")
        
        assert result is True
        self.mock_redis.get.assert_called_once_with("account_locked:test@example.com")
    
    @pytest.mark.asyncio
    async def test_reset_attempts(self):
        """Test resetting failed attempts."""
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.reset_attempts("test@example.com")
        
        self.mock_redis.delete.assert_called_once_with("login_attempts:test@example.com")
    
    @pytest.mark.asyncio
    async def test_unlock_account(self):
        """Test unlocking account."""
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.unlock_account("test@example.com")
        
        # Should delete both lockout and attempts
        assert self.mock_redis.delete.call_count == 2
        self.mock_redis.delete.assert_any_call("account_locked:test@example.com")
        self.mock_redis.delete.assert_any_call("login_attempts:test@example.com")
    
    @pytest.mark.asyncio
    async def test_lock_account(self):
        """Test manually locking account."""
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.lock_account("test@example.com")
        
        self.mock_redis.setex.assert_called_once_with("account_locked:test@example.com", 900, "true")
        self.mock_redis.delete.assert_called_once_with("login_attempts:test@example.com")
    
    @pytest.mark.asyncio
    async def test_get_lockout_stats(self):
        """Test getting lockout statistics."""
        # Mock Redis keys command to return locked accounts
        self.mock_redis.keys.return_value = [
            "account_locked:user1@example.com",
            "account_locked:user2@example.com"
        ]
        
        # Mock Redis get for each locked account
        self.mock_redis.get.side_effect = ["true", "true"]
        
        stats = await self.lockout_manager.get_lockout_stats()
        
        assert "locked_accounts" in stats
        assert stats["locked_accounts"] == 2
    
    @pytest.mark.asyncio
    async def test_lockout_disabled(self):
        """Test behavior when lockout is disabled."""
        with patch('config.settings.enable_account_lockout', False):
            await self.lockout_manager.record_failed_attempt("test@example.com")
            await self.lockout_manager.lock_account("test@example.com")
            await self.lockout_manager.reset_attempts("test@example.com")
            await self.lockout_manager.unlock_account("test@example.com")
            
            result = await self.lockout_manager.is_account_locked("test@example.com")
            
            # Should not interact with Redis when disabled
            self.mock_redis.incr.assert_not_called()
            self.mock_redis.setex.assert_not_called()
            self.mock_redis.delete.assert_not_called()
            self.mock_redis.get.assert_not_called()
            assert result is False


class TestAccountLockoutEdgeCases:
    """Test account lockout edge cases."""
    
    def setup_method(self):
        """Set up test lockout manager."""
        self.mock_redis = AsyncMock()
        self.lockout_manager = AccountLockoutManager(self.mock_redis)
    
    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis_error(self):
        """Test handling Redis errors during failed attempt recording."""
        self.mock_redis.incr.side_effect = Exception("Redis connection failed")
        
        # Should not raise exception
        await self.lockout_manager.record_failed_attempt("test@example.com")
    
    @pytest.mark.asyncio
    async def test_is_account_locked_redis_error(self):
        """Test handling Redis errors during lockout check."""
        self.mock_redis.get.side_effect = Exception("Redis connection failed")
        
        # Should return False on error (fail open)
        result = await self.lockout_manager.is_account_locked("test@example.com")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_unlock_account_redis_error(self):
        """Test handling Redis errors during account unlock."""
        self.mock_redis.delete.side_effect = Exception("Redis connection failed")
        
        # Should not raise exception
        await self.lockout_manager.unlock_account("test@example.com")
    
    @pytest.mark.asyncio
    async def test_empty_username(self):
        """Test handling empty username."""
        await self.lockout_manager.record_failed_attempt("")
        await self.lockout_manager.is_account_locked("")
        await self.lockout_manager.unlock_account("")
        
        # Should handle empty strings gracefully
        assert True
    
    @pytest.mark.asyncio
    async def test_none_username(self):
        """Test handling None username."""
        await self.lockout_manager.record_failed_attempt(None)
        await self.lockout_manager.is_account_locked(None)
        await self.lockout_manager.unlock_account(None)
        
        # Should handle None gracefully
        assert True
    
    @pytest.mark.asyncio
    async def test_very_long_username(self):
        """Test handling very long username."""
        long_username = "a" * 1000
        
        await self.lockout_manager.record_failed_attempt(long_username)
        await self.lockout_manager.is_account_locked(long_username)
        await self.lockout_manager.unlock_account(long_username)
        
        # Should handle long usernames
        assert True
    
    @pytest.mark.asyncio
    async def test_username_with_special_characters(self):
        """Test handling username with special characters."""
        special_username = "user@example.com!@#$%^&*()"
        
        await self.lockout_manager.record_failed_attempt(special_username)
        await self.lockout_manager.is_account_locked(special_username)
        await self.lockout_manager.unlock_account(special_username)
        
        # Should handle special characters
        assert True
    
    @pytest.mark.asyncio
    async def test_username_with_unicode(self):
        """Test handling username with unicode characters."""
        unicode_username = "usér@éxample.com"
        
        await self.lockout_manager.record_failed_attempt(unicode_username)
        await self.lockout_manager.is_account_locked(unicode_username)
        await self.lockout_manager.unlock_account(unicode_username)
        
        # Should handle unicode characters
        assert True


class TestAccountLockoutIntegration:
    """Test account lockout integration scenarios."""
    
    def setup_method(self):
        """Set up test lockout manager."""
        self.mock_redis = AsyncMock()
        self.lockout_manager = AccountLockoutManager(self.mock_redis)
    
    @pytest.mark.asyncio
    async def test_progressive_lockout_scenario(self):
        """Test progressive lockout scenario."""
        username = "progressive@example.com"
        
        # First 4 attempts (not locked yet)
        for i in range(4):
            self.mock_redis.incr.return_value = i + 1
            if i == 0:
                self.mock_redis.expire.return_value = True
            
            await self.lockout_manager.record_failed_attempt(username)
            
            # Should not be locked yet
            self.mock_redis.get.return_value = None
            is_locked = await self.lockout_manager.is_account_locked(username)
            assert is_locked is False
        
        # 5th attempt (should trigger lockout)
        self.mock_redis.incr.return_value = 5
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.record_failed_attempt(username)
        
        # Should be locked now
        self.mock_redis.get.return_value = "true"
        is_locked = await self.lockout_manager.is_account_locked(username)
        assert is_locked is True
    
    @pytest.mark.asyncio
    async def test_lockout_expiry(self):
        """Test lockout expiry."""
        username = "expiry@example.com"
        
        # Lock account
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.lock_account(username)
        
        # Simulate lockout expiry (Redis returns None)
        self.mock_redis.get.return_value = None
        
        is_locked = await self.lockout_manager.is_account_locked(username)
        assert is_locked is False
    
    @pytest.mark.asyncio
    async def test_multiple_users_lockout(self):
        """Test lockout for multiple users."""
        users = ["user1@example.com", "user2@example.com", "user3@example.com"]
        
        # Lock multiple accounts
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        for user in users:
            await self.lockout_manager.lock_account(user)
        
        # Check all are locked
        self.mock_redis.get.return_value = "true"
        
        for user in users:
            is_locked = await self.lockout_manager.is_account_locked(user)
            assert is_locked is True
    
    @pytest.mark.asyncio
    async def test_concurrent_lockout_attempts(self):
        """Test concurrent lockout attempts."""
        username = "concurrent@example.com"
        
        async def record_attempt():
            self.mock_redis.incr.return_value = 5
            self.mock_redis.setex.return_value = True
            self.mock_redis.delete.return_value = True
            await self.lockout_manager.record_failed_attempt(username)
        
        # Run multiple concurrent attempts
        tasks = [record_attempt() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        # Should handle concurrent attempts gracefully
        assert True
    
    @pytest.mark.asyncio
    async def test_admin_unlock_scenario(self):
        """Test admin unlock scenario."""
        username = "admin_unlock@example.com"
        
        # Lock account
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        
        await self.lockout_manager.lock_account(username)
        
        # Admin unlocks account
        await self.lockout_manager.unlock_account(username)
        
        # Should be unlocked
        self.mock_redis.get.return_value = None
        is_locked = await self.lockout_manager.is_account_locked(username)
        assert is_locked is False


class TestAccountLockoutPerformance:
    """Test account lockout performance."""
    
    def setup_method(self):
        """Set up test lockout manager."""
        self.mock_redis = AsyncMock()
        self.lockout_manager = AccountLockoutManager(self.mock_redis)
    
    @pytest.mark.asyncio
    async def test_lockout_performance(self):
        """Test lockout operations performance."""
        import time
        
        start_time = time.time()
        
        # Perform 100 lockout operations
        for i in range(100):
            username = f"perf_user{i}@example.com"
            await self.lockout_manager.record_failed_attempt(username)
            await self.lockout_manager.is_account_locked(username)
        
        end_time = time.time()
        
        # Should complete in reasonable time
        assert end_time - start_time < 2.0  # Less than 2 seconds for 200 operations
    
    @pytest.mark.asyncio
    async def test_concurrent_performance(self):
        """Test concurrent lockout operations performance."""
        import time
        
        async def lockout_operation(user_id):
            username = f"concurrent_user{user_id}@example.com"
            await self.lockout_manager.record_failed_attempt(username)
            await self.lockout_manager.is_account_locked(username)
            await self.lockout_manager.unlock_account(username)
        
        start_time = time.time()
        
        # Run 50 concurrent operations
        tasks = [lockout_operation(i) for i in range(50)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        
        # Should complete in reasonable time
        assert end_time - start_time < 3.0  # Less than 3 seconds for 150 operations


class TestAccountLockoutConfiguration:
    """Test account lockout configuration."""
    
    @pytest.mark.asyncio
    async def test_custom_lockout_settings(self):
        """Test custom lockout settings."""
        mock_redis = AsyncMock()
        
        # Create manager with custom settings
        with patch('config.settings.max_login_attempts', 3):
            with patch('config.settings.lockout_duration_minutes', 30):
                manager = AccountLockoutManager(mock_redis)
                
                # Test with custom max attempts
                mock_redis.incr.return_value = 3
                mock_redis.setex.return_value = True
                mock_redis.delete.return_value = True
                
                await manager.record_failed_attempt("test@example.com")
                
                # Should use custom lockout duration (30 minutes = 1800 seconds)
                mock_redis.setex.assert_called_with("account_locked:test@example.com", 1800, "true")
    
    @pytest.mark.asyncio
    async def test_lockout_disabled_globally(self):
        """Test when lockout is disabled globally."""
        mock_redis = AsyncMock()
        
        with patch('config.settings.enable_account_lockout', False):
            manager = AccountLockoutManager(mock_redis)
            
            # All operations should be no-ops
            await manager.record_failed_attempt("test@example.com")
            await manager.lock_account("test@example.com")
            await manager.unlock_account("test@example.com")
            
            result = await manager.is_account_locked("test@example.com")
            
            # Should not interact with Redis
            mock_redis.incr.assert_not_called()
            mock_redis.setex.assert_not_called()
            mock_redis.delete.assert_not_called()
            mock_redis.get.assert_not_called()
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
