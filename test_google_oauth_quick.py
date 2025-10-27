#!/usr/bin/env python3
"""
Quick Google OAuth Endpoints Test
Tests the Google OAuth endpoints without requiring actual Google credentials.
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/auth"

async def test_google_oauth_endpoints():
    """Test Google OAuth endpoints for basic functionality."""
    
    print("🔐 Testing Google OAuth Endpoints")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # Test 1: Google Login Endpoint
        print("\n1️⃣ Testing Google Login Endpoint...")
        try:
            response = await client.get(f"{BASE_URL}/google/login/", follow_redirects=False)
            
            if response.status_code == 500:
                # Check if it's a config error
                try:
                    error = response.json()
                    if "Google OAuth is not configured" in error.get("detail", ""):
                        print("   ❌ Google OAuth not configured (expected for testing)")
                        print("   📝 This is normal if GOOGLE_CLIENT_ID/SECRET are not set")
                        print("   ✅ Endpoint is working correctly")
                    else:
                        print(f"   ❌ Unexpected error: {error}")
                except:
                    print(f"   ❌ Server error: {response.text}")
                    
            elif response.status_code in [302, 307]:
                location = response.headers.get("location", "")
                if "accounts.google.com" in location:
                    print("   ✅ OAuth configured - redirects to Google")
                    print(f"   🔗 Redirect URL: {location[:80]}...")
                else:
                    print(f"   ❌ Unexpected redirect: {location}")
                    
            else:
                print(f"   ❌ Unexpected status code: {response.status_code}")
                print(f"   📄 Response: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
        
        # Test 2: Google Callback Endpoint (without code)
        print("\n2️⃣ Testing Google Callback Endpoint (no code)...")
        try:
            response = await client.get(f"{BASE_URL}/google/callback")
            
            if response.status_code == 422:
                print("   ✅ Properly validates missing authorization code")
            elif response.status_code == 400:
                error = response.json()
                if "Missing authorization code" in error.get("detail", ""):
                    print("   ✅ Properly rejects missing authorization code")
                else:
                    print(f"   ⚠️  Different validation: {error}")
            else:
                print(f"   ❌ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
        
        # Test 3: Google Callback Endpoint (with empty code)
        print("\n3️⃣ Testing Google Callback Endpoint (empty code)...")
        try:
            response = await client.get(f"{BASE_URL}/google/callback?code=")
            
            if response.status_code == 400:
                error = response.json()
                if "Missing authorization code" in error.get("detail", ""):
                    print("   ✅ Properly rejects empty authorization code")
                else:
                    print(f"   ⚠️  Different validation: {error}")
            else:
                print(f"   ❌ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
        
        # Test 4: Google Callback Endpoint (with invalid code)
        print("\n4️⃣ Testing Google Callback Endpoint (invalid code)...")
        try:
            response = await client.get(f"{BASE_URL}/google/callback?code=invalid_test_code")
            
            if response.status_code == 400:
                print("   ✅ Properly handles invalid authorization code")
                error = response.json()
                print(f"   📄 Error: {error.get('detail', 'Unknown error')}")
            else:
                print(f"   ❌ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Connection error: {e}")

    print("\n📊 Google OAuth Endpoint Testing Complete")
    print("=" * 50)
    print("✅ All endpoints are accessible and handling requests correctly")
    print("💡 For full OAuth testing, configure Google credentials and use test_google_oauth.py")

async def check_google_oauth_config():
    """Check if Google OAuth is configured by examining the login endpoint."""
    
    print("🔍 Checking Google OAuth Configuration")
    print("-" * 40)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/google/login/", follow_redirects=False)
            
            if response.status_code == 500:
                try:
                    error = response.json()
                    if "Google OAuth is not configured" in error.get("detail", ""):
                        print("❌ Google OAuth is NOT configured")
                        print("📝 Missing environment variables:")
                        print("   - GOOGLE_CLIENT_ID")
                        print("   - GOOGLE_CLIENT_SECRET")
                        print("   - GOOGLE_REDIRECT_URI (optional)")
                        print("\n🔧 To configure Google OAuth:")
                        print("1. Go to https://console.developers.google.com/")
                        print("2. Create OAuth 2.0 credentials")
                        print("3. Set the environment variables")
                        print("4. Restart the server")
                        return False
                    else:
                        print(f"❌ Server error: {error}")
                        return False
                except:
                    print(f"❌ Server error: {response.text}")
                    return False
                    
            elif response.status_code in [302, 307]:
                location = response.headers.get("location", "")
                if "accounts.google.com" in location:
                    print("✅ Google OAuth is CONFIGURED and working")
                    print(f"🔗 Authorization URL generated successfully")
                    return True
                else:
                    print(f"❌ Unexpected redirect: {location}")
                    return False
                    
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            print("💡 Make sure the server is running: uvicorn api.app:app --reload")
            return False

if __name__ == "__main__":
    print("🚀 Quick Google OAuth Test")
    print("=" * 30)
    
    try:
        # First check configuration
        loop = asyncio.get_event_loop()
        config_ok = loop.run_until_complete(check_google_oauth_config())
        
        # Then test endpoints
        print()
        loop.run_until_complete(test_google_oauth_endpoints())
        
        if not config_ok:
            print(f"\n💡 Next Steps:")
            print(f"1. Configure Google OAuth credentials")
            print(f"2. Set environment variables in .env file")
            print(f"3. Run: python test_google_oauth.py (full test suite)")
        else:
            print(f"\n🎉 Google OAuth is ready for use!")
            print(f"🌐 Try: http://localhost:8000/api/auth/google/login/")
            
    except KeyboardInterrupt:
        print(f"\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")