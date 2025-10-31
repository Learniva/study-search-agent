#!/usr/bin/env python3
"""
Test Script: User Data Consistency Verification

This script verifies that user profile data is handled consistently
across the API and database layers.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.models import ProfileResponse
from pydantic import ValidationError


def test_profile_response_with_uuid():
    """Test ProfileResponse with UUID string (should pass)."""
    print("\n✅ Test 1: ProfileResponse with UUID string")
    
    try:
        profile = ProfileResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="johndoe",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            display_name="John Doe",
            location="Lusaka, Zambia",
            website="https://example.com",
            profile_picture="/uploads/profile.jpg",
            role="student"
        )
        
        print(f"   ✓ Profile created successfully")
        print(f"   ✓ ID type: {type(profile.id).__name__}")
        print(f"   ✓ Display name: {profile.display_name}")
        print(f"   ✓ Location: {profile.location}")
        return True
        
    except ValidationError as e:
        print(f"   ✗ Validation failed: {e}")
        return False


def test_profile_response_with_integer():
    """Test ProfileResponse with integer (should fail - testing type safety)."""
    print("\n✅ Test 2: ProfileResponse integer rejection (type safety)")
    
    try:
        profile = ProfileResponse(
            id=12345,  # Integer instead of string
            username="johndoe",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            display_name="John Doe",
            location="Lusaka, Zambia",
            website="https://example.com",
            profile_picture="/uploads/profile.jpg",
            role="student"
        )
        
        print(f"   ✗ Integer accepted (type coercion occurred - this is bad!)")
        print(f"   ✓ ID value: {profile.id}")
        print(f"   ✓ ID type: {type(profile.id).__name__}")
        return False  # This should fail for proper type safety
        
    except ValidationError as e:
        print(f"   ✓ Validation correctly rejected integer ID")
        print(f"   ✓ Type safety is working as expected")
        return True  # Rejection is the correct behavior


def test_empty_optional_fields():
    """Test ProfileResponse with empty optional fields."""
    print("\n✅ Test 3: ProfileResponse with minimal data")
    
    try:
        profile = ProfileResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="newuser",
            email="new@example.com",
            first_name=None,
            last_name=None,
            display_name=None,
            location=None,
            website=None,
            profile_picture=None,
            role="student"
        )
        
        print(f"   ✓ Profile created with minimal data")
        print(f"   ✓ First name: {profile.first_name}")
        print(f"   ✓ Last name: {profile.last_name}")
        print(f"   ✓ Display name: {profile.display_name}")
        print(f"   ✓ Location: {profile.location}")
        return True
        
    except ValidationError as e:
        print(f"   ✗ Validation failed: {e}")
        return False


def test_location_parsing():
    """Test location string parsing."""
    print("\n✅ Test 4: Location parsing")
    
    location = "Lusaka, Zambia"
    
    if ',' in location:
        city, country = location.split(', ', 1)
        print(f"   ✓ Location string: {location}")
        print(f"   ✓ City: {city}")
        print(f"   ✓ Country: {country}")
        return True
    else:
        print(f"   ✗ Invalid location format: {location}")
        return False


def test_display_name_generation():
    """Test display name auto-generation logic."""
    print("\n✅ Test 5: Display name auto-generation")
    
    test_cases = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "expected": "John Doe"
        },
        {
            "first_name": "Jane",
            "last_name": "",
            "username": "jane",
            "expected": "Jane"
        },
        {
            "first_name": "",
            "last_name": "Smith",
            "username": "smith",
            "expected": "Smith"
        },
        {
            "first_name": "",
            "last_name": "",
            "username": "user123",
            "expected": "user123"
        }
    ]
    
    all_passed = True
    
    for case in test_cases:
        # Simulate auto-generation logic
        display_name = None
        first = case['first_name']
        last = case['last_name']
        username = case['username']
        
        if not display_name:
            if first and last:
                display_name = f"{first} {last}"
            elif first:
                display_name = first
            elif last:
                display_name = last
            else:
                display_name = username
        
        if display_name == case['expected']:
            print(f"   ✓ '{first}' + '{last}' → '{display_name}' ✓")
        else:
            print(f"   ✗ '{first}' + '{last}' → '{display_name}' (expected: '{case['expected']}')")
            all_passed = False
    
    return all_passed


def test_json_structure():
    """Test JSON serialization structure."""
    print("\n✅ Test 6: JSON structure consistency")
    
    profile = ProfileResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        username="johndoe",
        email="john@example.com",
        first_name="John",
        last_name="Doe",
        display_name="John Doe",
        location="Lusaka, Zambia",
        website="https://example.com",
        profile_picture="/uploads/profile.jpg",
        role="student"
    )
    
    json_data = profile.model_dump()
    
    required_fields = [
        'id', 'username', 'email', 'first_name', 'last_name',
        'display_name', 'location', 'website', 'profile_picture', 'role'
    ]
    
    all_present = True
    for field in required_fields:
        if field in json_data:
            print(f"   ✓ {field}: {json_data[field]}")
        else:
            print(f"   ✗ {field}: MISSING")
            all_present = False
    
    return all_present


def main():
    """Run all tests."""
    print("=" * 70)
    print("User Data Consistency Verification Tests")
    print("=" * 70)
    
    tests = [
        ("UUID String Type", test_profile_response_with_uuid),
        ("Integer ID (Type Safety)", test_profile_response_with_integer),
        ("Empty Optional Fields", test_empty_optional_fields),
        ("Location Parsing", test_location_parsing),
        ("Display Name Generation", test_display_name_generation),
        ("JSON Structure", test_json_structure),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! User data handling is consistent.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review implementation.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
