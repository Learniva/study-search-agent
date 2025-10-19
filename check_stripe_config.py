#!/usr/bin/env python3
"""
Quick script to check Stripe configuration and identify issues.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 70)
print("  Stripe Configuration Check")
print("=" * 70)
print()

def check_env_var(name, value, placeholder=None):
    """Check if an environment variable is properly set."""
    if not value:
        print(f"❌ {name}: NOT SET")
        return False
    elif placeholder and value == placeholder:
        print(f"⚠️  {name}: PLACEHOLDER VALUE")
        print(f"   Current: {value}")
        print(f"   Action Required: Replace with actual value")
        return False
    else:
        # Mask sensitive values
        if len(value) > 15:
            masked = f"{value[:10]}...{value[-4:]}"
        else:
            masked = value[:4] + "..."
        print(f"✅ {name}: {masked}")
        return True

# Check all Stripe environment variables
print("Environment Variables:")
print("-" * 70)

all_good = True

all_good &= check_env_var(
    "STRIPE_SECRET_KEY",
    os.getenv("STRIPE_SECRET_KEY"),
)

all_good &= check_env_var(
    "STRIPE_PUBLISHABLE_KEY",
    os.getenv("STRIPE_PUBLISHABLE_KEY"),
)

all_good &= check_env_var(
    "STRIPE_PRICE_ID",
    os.getenv("STRIPE_PRICE_ID"),
    placeholder="price_your_price_id_here"
)

webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
if not webhook_secret or webhook_secret == "whsec_your_webhook_secret_here":
    print(f"⚠️  STRIPE_WEBHOOK_SECRET: PLACEHOLDER (OK for now, required for production)")
else:
    masked = webhook_secret[:10] + "..." if len(webhook_secret) > 10 else "..."
    print(f"✅ STRIPE_WEBHOOK_SECRET: {masked}")

print()
print("=" * 70)

if all_good:
    print("✅ Configuration looks good!")
    print()
    print("Next step: Run test script to verify")
    print("  python test_stripe_integration.py")
else:
    print("⚠️  Configuration issues detected")
    print()
    print("🔧 Quick Fix:")
    print()
    
    price_id = os.getenv("STRIPE_PRICE_ID")
    if not price_id or price_id == "price_your_price_id_here":
        print("1. Create a product in Stripe Dashboard:")
        print("   https://dashboard.stripe.com/test/products")
        print()
        print("2. Copy the Price ID (starts with 'price_')")
        print()
        print("3. Update .env file:")
        print("   STRIPE_PRICE_ID=price_YOUR_ACTUAL_PRICE_ID")
        print()
        print("4. Restart your backend server")
        print()
        print("📖 See FIX_STRIPE_PRICE_ID.md for detailed instructions")

print("=" * 70)

