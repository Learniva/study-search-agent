"""
Integration test for profile update fix
Tests that database session is properly handled after profile updates
"""
import asyncio
import sys
from uuid import uuid4
from database.core.async_connection import get_session
from database.operations.user_ops import create_user, update_user_profile, get_user_by_id
from database.models.user import User

async def test_profile_update_session():
    """Test that profile update doesn't cause session errors"""
    
    print("=" * 70)
    print("Profile Update Database Session Integration Test")
    print("=" * 70)
    print()
    
    test_user_id = None
    
    try:
        # Step 1: Create a test user
        print("📝 Step 1: Creating test user...")
        async for session in get_session():
            test_user_id = f"test_user_{uuid4().hex[:8]}"
            user = await create_user(
                session=session,
                email=f"{test_user_id}@test.com",
                username=test_user_id,
                password="test_password_123",
                first_name="Test",
                last_name="User"
            )
            print(f"   ✓ Created user: {user.username}")
            print(f"   ✓ User ID: {user.id}")
            print(f"   ✓ Display name: {user.display_name}")
            print()
            break
        
        # Step 2: Update the user profile
        print("📝 Step 2: Updating user profile...")
        async for session in get_session():
            updated_user = await update_user_profile(
                session=session,
                user_id=user.user_id,  # Use user_id (email), not UUID id
                first_name="Updated",
                last_name="Profile",
                location="Lusaka, Zambia",
                website="https://example.com"
            )
            
            if updated_user is None:
                print("   ❌ Update failed - returned None")
                return False
            
            print(f"   ✓ Profile updated successfully")
            print(f"   ✓ New first name: {updated_user.first_name}")
            print(f"   ✓ New last name: {updated_user.last_name}")
            print(f"   ✓ New display name: {updated_user.display_name}")
            print(f"   ✓ New location: {updated_user.location}")
            print(f"   ✓ New website: {updated_user.website}")
            print()
            break
        
        # Step 3: Verify the update persisted
        print("📝 Step 3: Verifying update persisted...")
        async for session in get_session():
            verified_user = await get_user_by_id(session, user.user_id)  # Use user_id (email), not UUID id
            
            if verified_user is None:
                print("   ❌ Could not retrieve user after update")
                return False
            
            # Verify all fields
            assert verified_user.first_name == "Updated", f"Expected 'Updated', got '{verified_user.first_name}'"
            assert verified_user.last_name == "Profile", f"Expected 'Profile', got '{verified_user.last_name}'"
            assert verified_user.display_name == "Updated Profile", f"Expected 'Updated Profile', got '{verified_user.display_name}'"
            assert verified_user.location == "Lusaka, Zambia", f"Expected 'Lusaka, Zambia', got '{verified_user.location}'"
            assert verified_user.website == "https://example.com", f"Expected 'https://example.com', got '{verified_user.website}'"
            
            print(f"   ✓ First name verified: {verified_user.first_name}")
            print(f"   ✓ Last name verified: {verified_user.last_name}")
            print(f"   ✓ Display name verified: {verified_user.display_name}")
            print(f"   ✓ Location verified: {verified_user.location}")
            print(f"   ✓ Website verified: {verified_user.website}")
            print()
            break
        
        # Step 4: Test multiple updates in sequence
        print("📝 Step 4: Testing multiple sequential updates...")
        for i in range(3):
            async for session in get_session():
                updated = await update_user_profile(
                    session=session,
                    user_id=user.user_id,  # Use user_id (email), not UUID id
                    location=f"Update #{i+1}"
                )
                print(f"   ✓ Update #{i+1} successful: location = '{updated.location}'")
                break
        print()
        
        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✓ User creation works correctly")
        print("  ✓ Profile updates don't cause session errors")
        print("  ✓ Updated data persists correctly")
        print("  ✓ Multiple sequential updates work")
        print("  ✓ Display name auto-generation works")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ Test failed with error:")
        print("=" * 70)
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: Delete test user
        if test_user_id:
            try:
                print("🧹 Cleaning up test user...")
                from sqlalchemy import text
                async for session in get_session():
                    await session.execute(
                        text("DELETE FROM users WHERE username = :username"),
                        {"username": test_user_id}
                    )
                    await session.commit()
                    print(f"   ✓ Test user deleted")
                    break
            except Exception as e:
                print(f"   ⚠️ Cleanup warning: {e}")

if __name__ == "__main__":
    success = asyncio.run(test_profile_update_session())
    sys.exit(0 if success else 1)
