#!/usr/bin/env python3
"""
Simple Test Runner for Authentication Tests

A simplified version to test the authentication system.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_simple_tests():
    """Run a simple test to verify the test setup."""
    
    print("🧪 Running Simple Authentication Tests")
    print("=" * 50)
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Check if tests directory exists
    tests_dir = current_dir / "tests"
    if not tests_dir.exists():
        print("❌ Tests directory not found!")
        return False
    
    print(f"✅ Tests directory found: {tests_dir}")
    
    # List test files
    test_files = list(tests_dir.glob("test_*.py"))
    print(f"📁 Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"  - {test_file.name}")
    
    # Try to run a simple test
    try:
        print("\n🔍 Testing import of test modules...")
        
        # Test if we can import the test modules
        sys.path.insert(0, str(current_dir))
        
        # Try importing test modules
        try:
            import tests.test_authentication
            print("✅ test_authentication.py imports successfully")
        except ImportError as e:
            print(f"❌ test_authentication.py import failed: {e}")
        
        try:
            import tests.test_password_policy
            print("✅ test_password_policy.py imports successfully")
        except ImportError as e:
            print(f"❌ test_password_policy.py import failed: {e}")
        
        try:
            import tests.test_account_lockout
            print("✅ test_account_lockout.py imports successfully")
        except ImportError as e:
            print(f"❌ test_account_lockout.py import failed: {e}")
        
        print("\n🎯 Running pytest discovery...")
        
        # Run pytest discovery
        result = subprocess.run([
            "python", "-m", "pytest", 
            "tests/", 
            "--collect-only", 
            "-q"
        ], capture_output=True, text=True, cwd=current_dir)
        
        if result.returncode == 0:
            print("✅ pytest discovery successful")
            print("📋 Discovered tests:")
            lines = result.stdout.split('\n')
            for line in lines:
                if 'test_' in line and '::' in line:
                    print(f"  {line.strip()}")
        else:
            print(f"❌ pytest discovery failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    
    print("\n🔍 Checking Dependencies...")
    
    required_packages = [
        "pytest",
        "pytest-asyncio", 
        "pytest-cov",
        "fastapi",
        "sqlalchemy",
        "pydantic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All required packages are installed")
    return True


def main():
    """Main entry point."""
    
    print("🚀 Authentication Test Setup Checker")
    print("=" * 50)
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Run simple tests
    tests_ok = run_simple_tests()
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    if deps_ok and tests_ok:
        print("🎉 Test setup is ready!")
        print("\nTo run tests:")
        print("  python run_auth_tests.py")
        print("  python -m pytest tests/ -v")
    else:
        print("⚠️  Test setup needs attention")
        if not deps_ok:
            print("  - Install missing dependencies")
        if not tests_ok:
            print("  - Fix test configuration issues")
    
    return 0 if (deps_ok and tests_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
