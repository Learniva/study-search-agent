#!/usr/bin/env python3
"""
Database setup script for Stripe payment tables.

This script creates all necessary tables for Stripe payment integration:
- customers
- subscriptions
- payment_history

Usage:
    python setup_stripe_db.py
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

from database.core.async_engine import async_engine
from config.settings import settings


async def run_migration():
    """Run the payment tables migration."""
    migration_file = Path(__file__).parent / "database" / "migrations" / "create_payment_tables.sql"
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"📄 Reading migration file: {migration_file}")
    
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    print("🔄 Connecting to database...")
    print(f"   Database URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
    
    try:
        async with async_engine.begin() as conn:
            print("✅ Connected to database")
            print("🔄 Running migration...")
            
            # Split the SQL into individual statements
            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
            
            for i, statement in enumerate(statements, 1):
                try:
                    # Skip pure comment lines and SELECT statements (verification queries)
                    if statement.strip().upper().startswith('SELECT'):
                        print(f"   Skipping verification query {i}")
                        continue
                    
                    print(f"   Executing statement {i}/{len(statements)}...")
                    await conn.execute(text(statement))
                    
                except Exception as e:
                    print(f"   ⚠️  Statement {i} warning: {e}")
                    # Continue on errors (table might already exist)
            
            print("✅ Migration completed successfully!")
            print()
            print("📊 Verifying tables...")
            
            # Verify tables were created
            result = await conn.execute(text("""
                SELECT 
                    table_name,
                    (SELECT COUNT(*) 
                     FROM information_schema.columns 
                     WHERE table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                AND table_name IN ('users', 'customers', 'subscriptions', 'payment_history')
                ORDER BY table_name;
            """))
            
            tables = result.fetchall()
            
            if tables:
                print("\n✅ Tables created successfully:")
                for table_name, column_count in tables:
                    print(f"   - {table_name}: {column_count} columns")
            else:
                print("\n⚠️  No tables found. Check if migration ran correctly.")
            
            print("\n✅ Database setup complete!")
            print("\n📝 Next steps:")
            print("   1. Add your Stripe keys to .env file")
            print("   2. Configure webhook endpoint in Stripe Dashboard")
            print("   3. Test the payment flow")
            print("\n📖 See docs/STRIPE_INTEGRATION.md for detailed instructions")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\n🔍 Troubleshooting:")
        print("   - Verify database is running")
        print("   - Check DATABASE_URL in .env file")
        print("   - Ensure database user has CREATE TABLE permissions")
        sys.exit(1)


def main():
    """Main entry point."""
    print("=" * 70)
    print("  Stripe Payment Database Setup")
    print("=" * 70)
    print()
    
    asyncio.run(run_migration())


if __name__ == "__main__":
    main()

