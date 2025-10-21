#!/usr/bin/env python3
"""
Test Authentication & Payment Configuration

This script tests your Google OAuth and Stripe setup without starting the server.

Usage:
    python test_auth.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from utils.auth.config_validator import AuthConfigValidator


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}\n")


def print_section(title):
    """Print a section title."""
    print(f"\n{title}")
    print("-" * len(title))


async def test_database_connection():
    """Test database connection."""
    print_section("Testing Database Connection")
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        # Try async URL first, fall back to sync URL
        db_url = os.getenv("DATABASE_URL_ASYNC") or os.getenv("DATABASE_URL")
        if not db_url:
            print("❌ DATABASE_URL not set in environment")
            return False
        
        print(f"✓ DATABASE_URL found: {db_url.split('@')[0]}@...")
        
        # Ensure it's an async URL
        if db_url.startswith("postgresql://") and "+asyncpg://" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        # Try to connect
        try:
            engine = create_async_engine(db_url, echo=False)
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                db_result = await conn.execute(text("SELECT current_database()"))
                db_name = db_result.scalar()
                print(f"✅ Database connection successful")
                print(f"   Connected to: {db_name}")
            await engine.dispose()
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import database modules: {str(e)}")
        return False


def test_auth_endpoints():
    """Test that auth endpoints are importable."""
    print_section("Testing Auth Endpoints")
    
    try:
        from api.routers.auth import router
        print("✅ Auth router imported successfully")
        print(f"   Routes: {len(router.routes)} endpoints")
        
        # List endpoints
        for route in router.routes:
            if hasattr(route, 'path'):
                print(f"   - {route.methods} {route.path}")
        
        return True
    except ImportError as e:
        print(f"❌ Failed to import auth router: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error checking auth endpoints: {str(e)}")
        return False


def test_payment_endpoints():
    """Test that payment endpoints are importable."""
    print_section("Testing Payment Endpoints")
    
    try:
        from api.routers.payments import router
        print("✅ Payment router imported successfully")
        print(f"   Routes: {len(router.routes)} endpoints")
        
        # List endpoints
        for route in router.routes:
            if hasattr(route, 'path'):
                print(f"   - {route.methods} {route.path}")
        
        return True
    except ImportError as e:
        print(f"❌ Failed to import payment router: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error checking payment endpoints: {str(e)}")
        return False


def test_jwt_functionality():
    """Test JWT token creation and verification."""
    print_section("Testing JWT Functionality")
    
    try:
        from utils.auth.jwt_handler import create_access_token, verify_access_token
        
        # Create a test token
        test_data = {
            "user_id": "test123",
            "email": "test@example.com",
            "role": "student"
        }
        
        token = create_access_token(test_data)
        print("✅ JWT token created successfully")
        print(f"   Token length: {len(token)} characters")
        
        # Verify the token
        decoded = verify_access_token(token)
        print("✅ JWT token verified successfully")
        print(f"   Decoded data: {decoded.get('email')}, role: {decoded.get('role')}")
        
        return True
    except Exception as e:
        print(f"❌ JWT test failed: {str(e)}")
        return False


def print_env_file_status():
    """Print status of environment file."""
    print_section("Environment File Status")
    
    env_file = Path(__file__).parent / ".env"
    
    if env_file.exists():
        print(f"✅ .env file found at: {env_file}")
        
        # Count non-empty, non-comment lines
        with open(env_file) as f:
            lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
        
        print(f"   Variables set: {len(lines)}")
    else:
        print(f"❌ .env file not found")
        print(f"   Expected at: {env_file}")
        print(f"   Run: cp env_example.txt .env")


async def main():
    """Run all tests."""
    print_header("Authentication & Payment Configuration Test")
    
    # Print environment file status
    print_env_file_status()
    
    # Validate configuration
    print_section("Configuration Validation")
    config_valid = AuthConfigValidator.print_validation_report()
    
    # Run tests
    tests = [
        ("Auth Endpoints", test_auth_endpoints),
        ("Payment Endpoints", test_payment_endpoints),
        ("JWT Functionality", test_jwt_functionality),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results[test_name] = False
    
    # Database test (async)
    try:
        results["Database Connection"] = await test_database_connection()
    except Exception as e:
        print(f"❌ Database test crashed: {str(e)}")
        results["Database Connection"] = False
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print(f"\n{'='*70}")
    print(f"Total: {passed}/{total} tests passed")
    print(f"{'='*70}\n")
    
    if passed == total and config_valid:
        print("✅ All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Start the backend: source study_agent/bin/activate && python3 -m api.app")
        print("  2. Visit: http://localhost:8000/docs")
        print("  3. Test OAuth: http://localhost:8000/auth/google/login")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Update .env with your actual API keys")
        print("  - Ensure PostgreSQL is running")
        print("  - Check database connection string")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

