"""
Test Profile Update Database Session Fix

This test verifies that the profile update endpoint correctly handles
database sessions and returns updated user data without session errors.
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from database.models.user import User, Base
from database.operations.user_ops import create_user, update_user_profile, get_user_by_id
import uuid

# Create in-memory SQLite database for testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def setup_test_database():
    """Set up test database and return session factory."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return async_session


async def test_profile_update():
    """Test that profile update doesn't cause session errors."""
    
    print("=" * 70)
    print("Profile Update Database Session Test")
    print("=" * 70)
    print()
    
    # Setup
    SessionLocal = await setup_test_database()
    
    # Test 1: Create a user
    print("✓ Test 1: Creating test user...")
    async with SessionLocal() as session:
        user = await create_user(
            session=session,
            email="test@example.com",
            username="testuser",
            password="SecurePass123!",
            first_name="John",
            last_name="Doe",
            location="New York, USA"
        )
        
        if user:
            print(f"  ✓ User created: {user.username}")
            print(f"  ✓ ID: {user.id}")
            print(f"  ✓ Email: {user.email}")
            print(f"  ✓ Name: {user.first_name} {user.last_name}")
            print(f"  ✓ Display Name: {user.display_name}")
            print(f"  ✓ Location: {user.location}")
            user_id = user.user_id
        else:
            print("  ✗ Failed to create user")
            return
    
    print()
    
    # Test 2: Update user profile
    print("✓ Test 2: Updating user profile...")
    try:
        async with SessionLocal() as session:
            updated_user = await update_user_profile(
                session=session,
                user_id=user_id,
                first_name="Jane",
                last_name="Smith",
                display_name="Jane S.",
                location="San Francisco, CA",
                website="https://example.com"
            )
            
            if updated_user:
                print(f"  ✓ Profile updated successfully")
                print(f"  ✓ New Name: {updated_user.first_name} {updated_user.last_name}")
                print(f"  ✓ New Display Name: {updated_user.display_name}")
                print(f"  ✓ New Location: {updated_user.location}")
                print(f"  ✓ New Website: {updated_user.website}")
            else:
                print("  ✗ Failed to update profile")
                return
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        print(f"  ✗ Session error occurred during profile update")
        return
    
    print()
    
    # Test 3: Verify update persisted
    print("✓ Test 3: Verifying update persisted...")
    async with SessionLocal() as session:
        fetched_user = await get_user_by_id(session, user_id)
        
        if fetched_user:
            print(f"  ✓ User fetched from database")
            print(f"  ✓ Name: {fetched_user.first_name} {fetched_user.last_name}")
            print(f"  ✓ Display Name: {fetched_user.display_name}")
            print(f"  ✓ Location: {fetched_user.location}")
            print(f"  ✓ Website: {fetched_user.website}")
            
            # Verify values
            assert fetched_user.first_name == "Jane"
            assert fetched_user.last_name == "Smith"
            assert fetched_user.display_name == "Jane S."
            assert fetched_user.location == "San Francisco, CA"
            assert fetched_user.website == "https://example.com"
            
            print("  ✓ All values match expected results")
        else:
            print("  ✗ Failed to fetch user")
            return
    
    print()
    
    # Test 4: Multiple updates
    print("✓ Test 4: Testing multiple consecutive updates...")
    for i in range(3):
        async with SessionLocal() as session:
            updated_user = await update_user_profile(
                session=session,
                user_id=user_id,
                location=f"Location Update #{i+1}"
            )
            
            if updated_user:
                print(f"  ✓ Update #{i+1}: {updated_user.location}")
            else:
                print(f"  ✗ Update #{i+1} failed")
                return
    
    print()
    print("=" * 70)
    print("🎉 All tests passed! Database session handling is correct.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_profile_update())
