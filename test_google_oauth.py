#!/usr/bin/env python3
"""
Google OAuth Testing Script for Authentication System
This script provides comprehensive testing for Google OAuth integration.
"""

import os
import asyncio
import json
import webbrowser
from datetime import datetime
from typing import Dict, Any
import httpx
from urllib.parse import urlparse, parse_qs
import time

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Or manually export environment variables")

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

class GoogleOAuthTester:
    """Comprehensive Google OAuth testing class."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False  # We want to handle redirects manually
        )
        self.test_results = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"[{timestamp}] {status} {test_name}")
        if details:
            print(f"    📄 {details}")
        if response_data and not success:
            print(f"    📊 Response: {response_data}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data,
            "timestamp": timestamp
        })
        
    async def test_server_health(self) -> bool:
        """Test if the authentication server is running."""
        try:
            response = await self.client.get(f"{API_BASE}/auth/health")
            success = response.status_code == 200
            self.log_test(
                "Server Health Check",
                success,
                f"Server responded with status {response.status_code}",
                response.json() if success else response.text
            )
            return success
        except Exception as e:
            self.log_test("Server Health Check", False, f"Connection error: {e}")
            return False
            
    async def test_google_oauth_config(self) -> bool:
        """Test if Google OAuth is properly configured."""
        try:
            # Try to initiate OAuth flow - should either redirect or show config error
            response = await self.client.get(f"{API_BASE}/auth/google/login/")
            
            if response.status_code == 500:
                # Check if it's a configuration error
                try:
                    error_data = response.json()
                    if "Google OAuth is not configured" in error_data.get("detail", ""):
                        self.log_test(
                            "Google OAuth Configuration",
                            False,
                            "Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment."
                        )
                        return False
                except:
                    pass
                    
            elif response.status_code in [302, 307]:
                # Successful redirect to Google
                redirect_url = response.headers.get("location", "")
                if "accounts.google.com" in redirect_url:
                    self.log_test(
                        "Google OAuth Configuration", 
                        True, 
                        "OAuth endpoint configured correctly - redirects to Google"
                    )
                    return True
                else:
                    self.log_test(
                        "Google OAuth Configuration",
                        False,
                        f"Unexpected redirect URL: {redirect_url}"
                    )
                    return False
                    
            self.log_test(
                "Google OAuth Configuration",
                False,
                f"Unexpected response status: {response.status_code}",
                response.text
            )
            return False
            
        except Exception as e:
            self.log_test("Google OAuth Configuration", False, f"Error testing configuration: {e}")
            return False
    
    async def initiate_oauth_flow(self) -> Dict[str, Any]:
        """Initiate the OAuth flow and return authorization details."""
        try:
            response = await self.client.get(f"{API_BASE}/auth/google/login/")
            
            if response.status_code in [302, 307]:
                auth_url = response.headers.get("location", "")
                if "accounts.google.com" in auth_url:
                    self.log_test(
                        "OAuth Flow Initiation",
                        True,
                        f"Successfully generated Google OAuth URL"
                    )
                    
                    # Parse the authorization URL to extract parameters
                    parsed_url = urlparse(auth_url)
                    params = parse_qs(parsed_url.query)
                    
                    return {
                        "success": True,
                        "auth_url": auth_url,
                        "client_id": params.get("client_id", [None])[0],
                        "redirect_uri": params.get("redirect_uri", [None])[0],
                        "scope": params.get("scope", [None])[0],
                        "response_type": params.get("response_type", [None])[0],
                        "state": params.get("state", [None])[0]
                    }
                else:
                    self.log_test(
                        "OAuth Flow Initiation",
                        False,
                        f"Invalid redirect URL: {auth_url}"
                    )
                    return {"success": False, "error": "Invalid redirect URL"}
            else:
                self.log_test(
                    "OAuth Flow Initiation",
                    False,
                    f"Expected redirect, got status {response.status_code}",
                    response.text
                )
                return {"success": False, "error": f"Status {response.status_code}"}
                
        except Exception as e:
            self.log_test("OAuth Flow Initiation", False, f"Error initiating OAuth: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_callback_endpoint_validation(self) -> bool:
        """Test the callback endpoint with various scenarios."""
        test_cases = [
            {
                "name": "Missing Authorization Code",
                "params": {},
                "expected_status": 422  # FastAPI validation error for missing required param
            },
            {
                "name": "Empty Authorization Code",
                "params": {"code": ""},
                "expected_status": 400
            },
            {
                "name": "Invalid Authorization Code",
                "params": {"code": "invalid_test_code_12345"},
                "expected_status": 400
            }
        ]
        
        all_passed = True
        
        for case in test_cases:
            try:
                response = await self.client.get(
                    f"{API_BASE}/auth/google/callback",
                    params=case["params"]
                )
                
                success = response.status_code == case["expected_status"]
                self.log_test(
                    f"Callback Validation - {case['name']}",
                    success,
                    f"Expected {case['expected_status']}, got {response.status_code}"
                )
                
                if not success:
                    all_passed = False
                    
            except Exception as e:
                self.log_test(
                    f"Callback Validation - {case['name']}",
                    False,
                    f"Error testing callback: {e}"
                )
                all_passed = False
                
        return all_passed
    
    def interactive_oauth_test(self, auth_details: Dict[str, Any]) -> str:
        """Provide interactive OAuth testing instructions."""
        print("\n" + "="*80)
        print("🔐 INTERACTIVE GOOGLE OAUTH TESTING")
        print("="*80)
        
        print("\n📋 OAuth Configuration Details:")
        print(f"   Client ID: {auth_details.get('client_id', 'Not found')}")
        print(f"   Redirect URI: {auth_details.get('redirect_uri', 'Not found')}")
        print(f"   Scope: {auth_details.get('scope', 'Not found')}")
        print(f"   Response Type: {auth_details.get('response_type', 'Not found')}")
        
        print(f"\n🌐 Authorization URL:")
        print(f"   {auth_details['auth_url']}")
        
        print(f"\n📝 MANUAL TESTING STEPS:")
        print(f"   1. Open the authorization URL above in your browser")
        print(f"   2. Sign in with your Google account")
        print(f"   3. Grant permissions to the application")
        print(f"   4. You should be redirected to: {auth_details.get('redirect_uri')}")
        print(f"   5. Check the URL for an authorization code parameter")
        
        print(f"\n🔧 For automated testing, you would need:")
        print(f"   - Valid Google OAuth credentials in environment variables")
        print(f"   - A test Google account")
        print(f"   - Browser automation tools (like Selenium)")
        
        # Ask if user wants to open browser
        try:
            choice = input(f"\n❓ Open authorization URL in browser? (y/n): ").lower().strip()
            if choice in ['y', 'yes']:
                webbrowser.open(auth_details['auth_url'])
                print(f"✅ Browser opened. Complete the OAuth flow manually.")
                
                print(f"\n💡 After completing OAuth:")
                print(f"   - Check browser network tab for the callback request")
                print(f"   - Look for the redirect to your frontend URL")
                print(f"   - Verify JWT token in the callback URL")
                
                return "browser_opened"
            else:
                return "browser_skipped"
        except KeyboardInterrupt:
            print(f"\n❌ Test interrupted by user")
            return "interrupted"
    
    async def print_test_summary(self):
        """Print a comprehensive test summary."""
        print("\n" + "="*80)
        print("📊 GOOGLE OAUTH TESTING SUMMARY")
        print("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"\n📈 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {passed_tests}")
        print(f"   ❌ Failed: {failed_tests}")
        print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "   No tests run")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   • {result['test']}: {result['details']}")
        
        print(f"\n🔧 Environment Setup Required:")
        print(f"   1. Set GOOGLE_CLIENT_ID in environment")
        print(f"   2. Set GOOGLE_CLIENT_SECRET in environment") 
        print(f"   3. Set GOOGLE_REDIRECT_URI (default: http://localhost:8000/api/auth/google/callback/)")
        print(f"   4. Ensure database is running and configured")
        print(f"   5. Start the FastAPI server: uvicorn api.app:app --reload")
        
        print(f"\n📖 Google OAuth Console Setup:")
        print(f"   1. Go to: https://console.developers.google.com/")
        print(f"   2. Create a new project or select existing")
        print(f"   3. Enable Google+ API")
        print(f"   4. Create OAuth 2.0 credentials")
        print(f"   5. Add authorized redirect URIs")
        print(f"   6. Copy Client ID and Secret to environment variables")


async def run_oauth_tests():
    """Run comprehensive Google OAuth tests."""
    print("🚀 Starting Google OAuth Testing Suite")
    print("="*50)
    
    async with GoogleOAuthTester() as tester:
        # Test 1: Server Health
        server_healthy = await tester.test_server_health()
        if not server_healthy:
            print("\n❌ Server is not running. Please start the FastAPI server first:")
            print("   uvicorn api.app:app --reload")
            return
        
        # Test 2: Google OAuth Configuration
        config_valid = await tester.test_google_oauth_config()
        
        # Test 3: OAuth Flow Initiation
        auth_details = await tester.initiate_oauth_flow()
        
        # Test 4: Callback Endpoint Validation
        await tester.test_callback_endpoint_validation()
        
        # Interactive Testing (if configuration is valid)
        if config_valid and auth_details.get("success"):
            tester.interactive_oauth_test(auth_details)
        
        # Print comprehensive summary
        await tester.print_test_summary()


def check_environment_setup():
    """Check if environment variables are properly set."""
    print("🔍 Checking Environment Configuration")
    print("-" * 40)
    
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET", 
        "GOOGLE_REDIRECT_URI"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            display_value = value if var == "GOOGLE_REDIRECT_URI" else f"{value[:8]}..." if len(value) > 8 else "***"
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing required environment variables:")
        for var in missing_vars:
            print(f"   export {var}=your_value_here")
        print(f"\n💡 You can also create a .env file with these variables")
        return False
    
    print(f"\n✅ All required environment variables are set!")
    return True


if __name__ == "__main__":
    print("🔐 Google OAuth Authentication Testing")
    print("=" * 50)
    
    # Check environment setup first
    env_ok = check_environment_setup()
    
    if not env_ok:
        print(f"\n❌ Please configure environment variables before testing")
        exit(1)
    
    # Run the tests
    try:
        asyncio.run(run_oauth_tests())
    except KeyboardInterrupt:
        print(f"\n❌ Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()