#!/usr/bin/env python3
"""
Test script for Stripe payment integration.

This script verifies that your Stripe configuration is correct and can:
1. Connect to Stripe API
2. Create a test checkout session
3. Verify database tables exist
4. Check webhook endpoint configuration

Usage:
    python test_stripe_integration.py
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import stripe
from sqlalchemy import text

from database.core.async_engine import async_engine
from config.settings import settings


def check_env_variables():
    """Check if required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        'STRIPE_SECRET_KEY': settings.stripe_secret_key or os.getenv('STRIPE_SECRET_KEY'),
        'STRIPE_PUBLISHABLE_KEY': settings.stripe_publishable_key or os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'STRIPE_PRICE_ID': settings.stripe_price_id or os.getenv('STRIPE_PRICE_ID'),
    }
    
    optional_vars = {
        'STRIPE_WEBHOOK_SECRET': settings.stripe_webhook_secret or os.getenv('STRIPE_WEBHOOK_SECRET'),
    }
    
    all_ok = True
    
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask the value for security
            masked = f"{var_value[:7]}...{var_value[-4:]}" if len(var_value) > 11 else "***"
            print(f"   ✅ {var_name}: {masked}")
        else:
            print(f"   ❌ {var_name}: NOT SET")
            all_ok = False
    
    for var_name, var_value in optional_vars.items():
        if var_value:
            masked = f"{var_value[:7]}...{var_value[-4:]}" if len(var_value) > 11 else "***"
            print(f"   ✅ {var_name}: {masked}")
        else:
            print(f"   ⚠️  {var_name}: NOT SET (required for webhooks)")
    
    print()
    return all_ok


async def check_database_tables():
    """Check if payment tables exist in database."""
    print("🔍 Checking database tables...")
    
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('customers', 'subscriptions', 'payment_history')
                ORDER BY table_name;
            """))
            
            tables = [row[0] for row in result.fetchall()]
            
            expected_tables = ['customers', 'subscriptions', 'payment_history']
            
            for table in expected_tables:
                if table in tables:
                    print(f"   ✅ Table '{table}' exists")
                else:
                    print(f"   ❌ Table '{table}' NOT FOUND")
            
            print()
            
            if len(tables) == len(expected_tables):
                return True
            else:
                print("   💡 Run 'python setup_stripe_db.py' to create missing tables")
                return False
                
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        print()
        return False


def check_stripe_api():
    """Test connection to Stripe API."""
    print("🔍 Testing Stripe API connection...")
    
    secret_key = settings.stripe_secret_key or os.getenv('STRIPE_SECRET_KEY')
    
    if not secret_key:
        print("   ❌ STRIPE_SECRET_KEY not set")
        print()
        return False
    
    try:
        stripe.api_key = secret_key
        
        # Try to retrieve account info
        account = stripe.Account.retrieve()
        
        print(f"   ✅ Connected to Stripe API")
        print(f"   ℹ️  Account ID: {account.id}")
        print(f"   ℹ️  Mode: {'TEST' if account.id.startswith('acct_') and 'test' in secret_key else 'LIVE'}")
        print()
        return True
        
    except stripe.error.AuthenticationError as e:
        print(f"   ❌ Authentication failed: {e}")
        print("   💡 Check your STRIPE_SECRET_KEY")
        print()
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()
        return False


async def test_create_price():
    """Check if the configured Price ID exists."""
    print("🔍 Verifying Stripe Price ID...")
    
    price_id = settings.stripe_price_id or os.getenv('STRIPE_PRICE_ID')
    
    if not price_id:
        print("   ⚠️  STRIPE_PRICE_ID not set")
        print("   💡 You'll need to provide a price_id when creating checkout sessions")
        print()
        return True  # Not critical
    
    try:
        price = stripe.Price.retrieve(price_id)
        
        product = stripe.Product.retrieve(price.product)
        
        print(f"   ✅ Price ID valid: {price_id}")
        print(f"   ℹ️  Product: {product.name}")
        print(f"   ℹ️  Amount: {price.unit_amount / 100} {price.currency.upper()}")
        print(f"   ℹ️  Interval: {price.recurring.get('interval', 'N/A') if price.recurring else 'one-time'}")
        print()
        return True
        
    except stripe.error.InvalidRequestError as e:
        print(f"   ❌ Invalid Price ID: {e}")
        print("   💡 Create a product in Stripe Dashboard and update STRIPE_PRICE_ID")
        print()
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()
        return False


async def test_checkout_session_creation():
    """Test creating a checkout session (without actually charging)."""
    print("🔍 Testing checkout session creation...")
    
    price_id = settings.stripe_price_id or os.getenv('STRIPE_PRICE_ID')
    
    if not price_id:
        print("   ⚠️  Skipped: STRIPE_PRICE_ID not set")
        print()
        return True
    
    try:
        from utils.payment.stripe_client import create_checkout_session
        
        session = await create_checkout_session(
            customer_email="test@example.com",
            price_id=price_id,
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel",
            metadata={"user_id": "test_user_123"}
        )
        
        print(f"   ✅ Checkout session created")
        print(f"   ℹ️  Session ID: {session.id}")
        print(f"   ℹ️  URL: {session.url}")
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create checkout session: {e}")
        print()
        return False


def print_summary(results):
    """Print summary of all checks."""
    print("=" * 70)
    print("  Test Summary")
    print("=" * 70)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print()
    
    if all_passed:
        print("  🎉 All tests passed! Your Stripe integration is ready.")
        print()
        print("  📝 Next steps:")
        print("     1. Set up webhook endpoint in Stripe Dashboard")
        print("     2. Test the payment flow in your frontend")
        print("     3. Monitor webhook events in the dashboard")
        print()
        print("  📖 See docs/STRIPE_INTEGRATION.md for more details")
    else:
        print("  ⚠️  Some tests failed. Please fix the issues above.")
        print()
        print("  📖 See docs/STRIPE_INTEGRATION.md for setup instructions")
    
    print("=" * 70)
    print()
    
    return all_passed


async def main():
    """Run all tests."""
    print("=" * 70)
    print("  Stripe Integration Test")
    print("=" * 70)
    print()
    
    results = {}
    
    # Check environment variables
    results['Environment Variables'] = check_env_variables()
    
    # Check database tables
    results['Database Tables'] = await check_database_tables()
    
    # Check Stripe API connection
    results['Stripe API Connection'] = check_stripe_api()
    
    # Check Price ID
    results['Price Configuration'] = await test_create_price()
    
    # Test checkout session creation
    results['Checkout Session Creation'] = await test_checkout_session_creation()
    
    # Print summary
    all_passed = print_summary(results)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())

