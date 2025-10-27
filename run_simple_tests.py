#!/usr/bin/env python3
"""
Simple Authentication Test Runner

Runs the simplified authentication tests without LangChain dependencies.
"""

import subprocess
import sys
from pathlib import Path


def run_simple_auth_tests():
    """Run the simplified authentication tests."""
    
    print("🧪 Running Simplified Authentication Tests")
    print("=" * 50)
    
    # Get the project root directory
    project_root = Path(__file__).parent
    tests_dir = project_root / "tests"
    
    # Run the simplified test file
    test_file = tests_dir / "test_auth_simple.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"📁 Running tests from: {test_file}")
    
    try:
        # Run pytest on the simplified test file
        result = subprocess.run([
            "python", "-m", "pytest",
            str(test_file),
            "-v",
            "--tb=short"
        ], cwd=project_root)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
            return True
        else:
            print(f"\n❌ Tests failed with return code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def main():
    """Main entry point."""
    
    success = run_simple_auth_tests()
    
    if success:
        print("\n🎉 Authentication tests completed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
