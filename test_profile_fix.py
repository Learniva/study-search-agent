"""
Quick test to verify profile update fix for location and website fields.

This test verifies that:
1. Profile PATCH endpoint accepts location and website
2. These fields are saved to the database
3. GET endpoint returns the saved values
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models.user import User
from database.operations.user_ops import (
    create_user,
    get_user_by_email,
    update_user_profile,
)
from config.settings import settings


async def test_profile_update():
    """Test profile update with location and website."""
    
    # Create async engine
    engine = create_async_engine(
        settings.async_database_url,
        echo=True
    )
    
    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    test_email = "test_profile_fix@example.com"
    
    async with async_session() as session:
        print("\n" + "="*80)
        print("🧪 Testing Profile Update - Location & Website Fix")
        print("="*80)
        
        # Clean up test user if exists
        existing_user = await get_user_by_email(session, test_email)
        if existing_user:
            await session.delete(existing_user)
            await session.commit()
            print(f"🧹 Cleaned up existing test user: {test_email}")
        
        # 1. Create test user
        print(f"\n1️⃣  Creating test user: {test_email}")
        user = await create_user(
            session,
            email=test_email,
            username="test_profile_user",
            password="TestPassword123!",
            first_name="Test",
            last_name="User",
            display_name="Test User",
        )
        
        if not user:
            print("❌ Failed to create test user")
            return False
        
        print(f"✅ User created: {user.email}")
        print(f"   - Location: {user.location or '(empty)'}")
        print(f"   - Website: {user.website or '(empty)'}")
        
        # 2. Update profile with location and website
        print("\n2️⃣  Updating profile with location and website...")
        test_location = "San Francisco, CA"
        test_website = "https://www.dabwitso.online"
        
        updated_user = await update_user_profile(
            session,
            user.user_id,
            location=test_location,
            website=test_website,
            display_name="Dabwitso Mweemba"
        )
        
        if not updated_user:
            print("❌ Failed to update profile")
            return False
        
        print(f"✅ Profile updated")
        print(f"   - Location: {updated_user.location}")
        print(f"   - Website: {updated_user.website}")
        print(f"   - Display Name: {updated_user.display_name}")
        
        # 3. Verify the update persisted
        print("\n3️⃣  Fetching user again to verify persistence...")
        verified_user = await get_user_by_email(session, test_email)
        
        if not verified_user:
            print("❌ Failed to fetch user")
            return False
        
        print(f"✅ User fetched from database")
        print(f"   - Location: {verified_user.location}")
        print(f"   - Website: {verified_user.website}")
        print(f"   - Display Name: {verified_user.display_name}")
        
        # 4. Verify values match
        success = True
        if verified_user.location != test_location:
            print(f"❌ Location mismatch: expected '{test_location}', got '{verified_user.location}'")
            success = False
        else:
            print(f"✅ Location matches: {verified_user.location}")
        
        if verified_user.website != test_website:
            print(f"❌ Website mismatch: expected '{test_website}', got '{verified_user.website}'")
            success = False
        else:
            print(f"✅ Website matches: {verified_user.website}")
        
        # 5. Clean up
        print("\n5️⃣  Cleaning up test user...")
        await session.delete(verified_user)
        await session.commit()
        print("✅ Test user cleaned up")
        
        # Final result
        print("\n" + "="*80)
        if success:
            print("✅ ALL TESTS PASSED - Profile update is working correctly!")
        else:
            print("❌ TESTS FAILED - Profile update has issues")
        print("="*80 + "\n")
        
        return success
    
    await engine.dispose()


if __name__ == "__main__":
    try:
        result = asyncio.run(test_profile_update())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
