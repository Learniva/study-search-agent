"""Debug script to find what's blocking startup."""
import sys
import time

def timed_import(module_name, description=""):
    """Import a module and time it."""
    print(f"⏱️  Importing {module_name}... {description}", flush=True)
    start = time.time()
    try:
        __import__(module_name)
        elapsed = time.time() - start
        print(f"   ✅ Done in {elapsed:.2f}s", flush=True)
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"   ❌ Failed in {elapsed:.2f}s: {e}", flush=True)
        return False

print("=" * 60, flush=True)
print("DEBUGGING SLOW STARTUP", flush=True)
print("=" * 60, flush=True)

# Test basic imports
timed_import("os")
timed_import("dotenv", "environment variables")

# Load .env
from dotenv import load_dotenv
import os
load_dotenv()
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY", "False")
print("✅ Environment loaded", flush=True)

# Test FastAPI
timed_import("fastapi")

# Test database
timed_import("database", "database init")

# Test agents
timed_import("agents.supervisor.core", "SupervisorAgent")

# Try creating SupervisorAgent
print("\n" + "=" * 60, flush=True)
print("CREATING SUPERVISOR AGENT", flush=True)
print("=" * 60, flush=True)

start = time.time()
try:
    from agents.supervisor.core import SupervisorAgent
    print("⏱️  Instantiating SupervisorAgent...", flush=True)
    supervisor = SupervisorAgent(llm_provider="gemini")
    elapsed = time.time() - start
    print(f"✅ SupervisorAgent created in {elapsed:.2f}s", flush=True)
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ Failed in {elapsed:.2f}s: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\n✅ All tests complete!", flush=True)
