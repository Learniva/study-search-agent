"""
Test Configuration and Utilities

Configuration and utilities for running authentication tests including:
- Test database setup
- Mock configurations
- Test data fixtures
- Performance testing utilities

Author: Study Search Agent Team
Version: 1.0.0
"""

import pytest
import asyncio
import os
import tempfile
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import app only when needed to avoid LangChain import issues
# from api.app import app
from database.models.base import Base
from database.models.user import User, UserRole
from database.models.token import Token
from utils.auth.password import hash_password_sync as hash_password


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """Create test database engine."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_db_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_client():
    """Create test client."""
    # Import app dynamically to avoid LangChain import issues
    try:
        from api.app import app
        return TestClient(app)
    except ImportError:
        # Create a minimal FastAPI app for testing
        from fastapi import FastAPI
        test_app = FastAPI()
        
        # Add basic auth routes for testing
        @test_app.post("/api/auth/login/")
        async def mock_login():
            return {"message": "Mock login endpoint"}
        
        @test_app.post("/api/auth/register/")
        async def mock_register():
            return {"message": "Mock register endpoint"}
        
        return TestClient(test_app)


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_users():
    """Sample user data for testing."""
    return [
        {
            "user_id": "student@example.com",
            "email": "student@example.com",
            "username": "student",
            "full_name": "Student User",
            "password_hash": hash_password("StudentPass123!"),
            "role": UserRole.STUDENT,
            "is_active": True,
            "is_verified": True
        },
        {
            "user_id": "teacher@example.com",
            "email": "teacher@example.com",
            "username": "teacher",
            "full_name": "Teacher User",
            "password_hash": hash_password("TeacherPass123!"),
            "role": UserRole.TEACHER,
            "is_active": True,
            "is_verified": True
        },
        {
            "user_id": "admin@example.com",
            "email": "admin@example.com",
            "username": "admin",
            "full_name": "Admin User",
            "password_hash": hash_password("AdminPass123!"),
            "role": UserRole.ADMIN,
            "is_active": True,
            "is_verified": True
        },
        {
            "user_id": "inactive@example.com",
            "email": "inactive@example.com",
            "username": "inactive",
            "full_name": "Inactive User",
            "password_hash": hash_password("InactivePass123!"),
            "role": UserRole.STUDENT,
            "is_active": False,
            "is_verified": False
        }
    ]


@pytest.fixture
def sample_tokens():
    """Sample token data for testing."""
    return [
        {
            "token": "student_token_123",
            "user_id": "student@example.com",
            "is_active": True,
            "device_info": "Chrome Browser",
            "ip_address": "127.0.0.1"
        },
        {
            "token": "teacher_token_456",
            "user_id": "teacher@example.com",
            "is_active": True,
            "device_info": "Firefox Browser",
            "ip_address": "127.0.0.1"
        },
        {
            "token": "expired_token_789",
            "user_id": "student@example.com",
            "is_active": False,
            "device_info": "Safari Browser",
            "ip_address": "127.0.0.1"
        }
    ]


# ============================================================================
# Mock Configurations
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True
    mock_redis.keys.return_value = []
    return mock_redis


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return {
        "enable_account_lockout": True,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 15,
        "password_min_length": 12,
        "password_require_uppercase": True,
        "password_require_lowercase": True,
        "password_require_digits": True,
        "password_require_special_chars": True,
        "password_min_special_chars": 2,
        "enable_session_fingerprinting": True,
        "max_concurrent_sessions": 5,
        "session_timeout_hours": 24,
        "enable_security_headers": True,
        "rate_limit_enabled": True,
        "rate_limit_per_minute": 60,
        "rate_limit_per_hour": 1000
    }


# ============================================================================
# Test Utilities
# ============================================================================

class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_users(count: int, role: UserRole = UserRole.STUDENT) -> List[Dict[str, Any]]:
        """Generate test users."""
        users = []
        for i in range(count):
            users.append({
                "user_id": f"user{i}@example.com",
                "email": f"user{i}@example.com",
                "username": f"user{i}",
                "full_name": f"Test User {i}",
                "password_hash": hash_password(f"Password{i}!"),
                "role": role,
                "is_active": True,
                "is_verified": True
            })
        return users
    
    @staticmethod
    def generate_passwords(count: int) -> List[str]:
        """Generate test passwords."""
        passwords = []
        for i in range(count):
            passwords.append(f"TestPassword{i}!")
        return passwords
    
    @staticmethod
    def generate_tokens(count: int, user_id: str = "test@example.com") -> List[Dict[str, Any]]:
        """Generate test tokens."""
        tokens = []
        for i in range(count):
            tokens.append({
                "token": f"token_{i}_{user_id.replace('@', '_')}",
                "user_id": user_id,
                "is_active": True,
                "device_info": f"Device {i}",
                "ip_address": f"192.168.1.{i % 255}"
            })
        return tokens


class PerformanceTestHelper:
    """Helper for performance testing."""
    
    @staticmethod
    async def measure_time(func, *args, **kwargs):
        """Measure execution time of async function."""
        import time
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time
    
    @staticmethod
    async def run_concurrent_tasks(tasks: List, max_concurrent: int = 10):
        """Run tasks concurrently with limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await task
        
        return await asyncio.gather(*[run_with_semaphore(task) for task in tasks])
    
    @staticmethod
    def assert_performance(execution_time: float, max_time: float, operation: str):
        """Assert performance requirements."""
        assert execution_time < max_time, f"{operation} took {execution_time:.2f}s, expected < {max_time}s"


class SecurityTestHelper:
    """Helper for security testing."""
    
    @staticmethod
    def generate_malicious_inputs() -> List[str]:
        """Generate malicious input strings for testing."""
        return [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "../../etc/passwd",
            "{{7*7}}",
            "${7*7}",
            "{{config}}",
            "{{''.__class__.__mro__[2].__subclasses__()}}",
            "{{request}}",
            "{{self}}",
            "\x00",
            "\x01\x02\x03",
            "test\x00password",
            "test\xffpassword",
            "test\x80password",
            "test\xc0password",
            "test\xe0password",
            "test\xf0password",
            "test\xf8password",
            "test\xfcpassword",
            "test\xfepassword",
            "test\xffpassword"
        ]
    
    @staticmethod
    def generate_sql_injection_attempts() -> List[str]:
        """Generate SQL injection attempt strings."""
        return [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' OR 1=1 --",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --",
            "' UNION SELECT * FROM users --",
            "'; UPDATE users SET password='hacked' WHERE username='admin'; --",
            "' OR EXISTS(SELECT * FROM users WHERE username='admin') --",
            "'; DELETE FROM users WHERE username='admin'; --"
        ]
    
    @staticmethod
    def generate_xss_attempts() -> List[str]:
        """Generate XSS attempt strings."""
        return [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "<iframe src=javascript:alert('xss')></iframe>",
            "<body onload=alert('xss')>",
            "<input onfocus=alert('xss') autofocus>",
            "<select onfocus=alert('xss') autofocus>",
            "<textarea onfocus=alert('xss') autofocus>",
            "<keygen onfocus=alert('xss') autofocus>",
            "<video><source onerror=alert('xss')>",
            "<audio src=x onerror=alert('xss')>",
            "<details open ontoggle=alert('xss')>",
            "<marquee onstart=alert('xss')>",
            "<object data=javascript:alert('xss')>",
            "<embed src=javascript:alert('xss')>",
            "<form><button formaction=javascript:alert('xss')>",
            "<link rel=stylesheet href=javascript:alert('xss')>",
            "<meta http-equiv=refresh content=0;url=javascript:alert('xss')>",
            "<style>@import'javascript:alert(\"xss\")';</style>"
        ]


# ============================================================================
# Test Markers and Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    for item in items:
        # Add markers based on test names
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.performance)
        if "security" in item.name.lower():
            item.add_marker(pytest.mark.security)
        if "integration" in item.name.lower():
            item.add_marker(pytest.mark.integration)
        if "slow" in item.name.lower():
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Test Environment Setup
# ============================================================================

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment."""
    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["JWT_SECRET_KEY"] = "test_secret_key_32_chars_long"
    os.environ["SECRET_KEY"] = "test_secret_key_32_chars_long"
    
    # Mock external services
    with patch('utils.cache.redis_client.RedisClient.get_instance'):
        yield
    
    # Cleanup
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


# ============================================================================
# Test Assertions
# ============================================================================

class TestAssertions:
    """Custom test assertions."""
    
    @staticmethod
    def assert_valid_jwt_token(token: str):
        """Assert that token is a valid JWT format."""
        parts = token.split('.')
        assert len(parts) == 3, "JWT token should have 3 parts"
        assert all(part for part in parts), "JWT token parts should not be empty"
    
    @staticmethod
    def assert_valid_user_data(user_data: Dict[str, Any]):
        """Assert that user data is valid."""
        required_fields = ["user_id", "email", "username", "role", "is_active"]
        for field in required_fields:
            assert field in user_data, f"User data should contain {field}"
        
        assert user_data["is_active"] is True, "User should be active"
        assert "@" in user_data["email"], "Email should be valid format"
    
    @staticmethod
    def assert_valid_password_hash(password_hash: str):
        """Assert that password hash is valid."""
        assert password_hash is not None, "Password hash should not be None"
        assert len(password_hash) > 20, "Password hash should be reasonably long"
        assert password_hash.startswith("$2b$"), "Should use bcrypt format"
    
    @staticmethod
    def assert_security_headers_present(response):
        """Assert that security headers are present."""
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy"
        ]
        
        for header in security_headers:
            assert header in response.headers, f"Security header {header} should be present"
    
    @staticmethod
    def assert_no_sensitive_data_in_response(response_data: Dict[str, Any]):
        """Assert that no sensitive data is exposed in response."""
        sensitive_fields = ["password", "password_hash", "secret", "token"]
        
        def check_dict(data, path=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    assert key.lower() not in sensitive_fields, f"Sensitive field {current_path} should not be exposed"
                    check_dict(value, current_path)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_dict(item, f"{path}[{i}]")
        
        check_dict(response_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
