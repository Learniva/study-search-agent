#!/usr/bin/env python3
"""
Quick test script to verify authentication endpoints work
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoints():
    print("🧪 Testing Authentication Endpoints")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   ✅ GET / -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 Response: {data.get('message', 'No message')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Auth config
    print("\n2. Testing auth config...")
    try:
        response = requests.get(f"{BASE_URL}/api/auth/config/")
        print(f"   ✅ GET /api/auth/config/ -> {response.status_code}")
        if response.status_code == 200:
            print(f"   📊 Config loaded successfully")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Password validation (weak)
    print("\n3. Testing password validation (weak password)...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/validate-password/",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"password": "weak"})
        )
        print(f"   ✅ POST /api/auth/validate-password/ -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 Valid: {data.get('is_valid', 'unknown')}, Score: {data.get('score', 'unknown')}")
        else:
            print(f"   ⚠️  Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Password validation (strong)  
    print("\n4. Testing password validation (strong password)...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/validate-password/",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"password": "SuperSecure123!@#"})
        )
        print(f"   ✅ POST /api/auth/validate-password/ -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 Valid: {data.get('is_valid', 'unknown')}, Score: {data.get('score', 'unknown')}")
        else:
            print(f"   ⚠️  Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 5: Registration
    print("\n5. Testing user registration...")
    try:
        import time
        timestamp = int(time.time())
        user_data = {
            "username": f"testuser{timestamp}",
            "email": f"test{timestamp}@example.com",
            "password": "SuperSecure123!@#",
            "full_name": "Test User"
        }
        response = requests.post(
            f"{BASE_URL}/api/auth/register/",
            headers={"Content-Type": "application/json"},
            data=json.dumps(user_data)
        )
        print(f"   ✅ POST /api/auth/register/ -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 User created: {data.get('username', 'unknown')}")
            print(f"   🔑 Token received: {'Yes' if 'access_token' in data else 'No'}")
        else:
            print(f"   ⚠️  Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Test completed! Check results above.")

if __name__ == "__main__":
    test_endpoints()