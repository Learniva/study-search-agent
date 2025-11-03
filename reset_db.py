#!/usr/bin/env python3
"""
Database Reset Script

This script will completely reset the database by:
1. Dropping all existing tables
2. Recreating all tables from models
3. Optionally creating test data

WARNING: This will DELETE ALL DATA in the database!
Use with caution, primarily for development/testing purposes.
"""

import sys
import os
from typing import Optional

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.core.connection import engine, init_db
from database.models import Base
from sqlalchemy import text


def confirm_reset() -> bool:
    """
    Ask user to confirm the database reset.
    
    Returns:
        True if user confirms, False otherwise
    """
    print("\n" + "=" * 60)
    print("  DATABASE RESET WARNING")
    print("=" * 60)
    print("\nThis will DELETE ALL DATA in the database:")
    print("  • All users and authentication data")
    print("  • All grading sessions and results")
    print("  • All payment and subscription records")
    print("  • All audit logs and RAG data")
    print("  • All tokens and sessions")
    print("\n THIS ACTION CANNOT BE UNDONE!")
    print("=" * 60)
    
    response = input("\nType 'RESET' to confirm: ").strip()
    return response == 'RESET'


def drop_all_tables():
    """Drop all tables in the database."""
    print("\n  Dropping all tables (CASCADE)...")
    try:
        with engine.connect() as conn:
            # Get all table names
            result = conn.execute(text("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public';
            """))
            tables = [row[0] for row in result]
            if tables:
                # Disable referential integrity
                conn.execute(text("SET session_replication_role = 'replica';"))
                # Drop all tables with CASCADE
                for table in tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE;'))
                conn.execute(text("SET session_replication_role = 'origin';"))
                conn.commit()
                print(f" Dropped tables: {', '.join(tables)}")
            else:
                print("ℹ No tables found to drop.")
        # Also call SQLAlchemy drop_all for metadata consistency
        Base.metadata.drop_all(bind=engine)
        print(" All tables dropped successfully (CASCADE)")
        return True
    except Exception as e:
        print(f" Error dropping tables: {e}")
        return False


def create_all_tables():
    """Create all tables from models."""
    print("\n Creating all tables...")
    try:
        # Enable pgvector extension first
        with engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print(" pgvector extension enabled")
            except Exception as e:
                print(f"  Could not enable pgvector: {e}")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print(" All tables created successfully")
        
        # List created tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
        print(f"\n Created {len(tables)} tables:")
        for table in tables:
            print(f"   • {table}")
        
        return True
    except Exception as e:
        print(f" Error creating tables: {e}")
        return False


def verify_database():
    """Verify database connection and structure."""
    print("\n Verifying database...")
    try:
        with engine.connect() as conn:
            # Check connection
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f" Connected to PostgreSQL: {version.split(',')[0]}")
            
            # Check tables
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            print(f" Database has {table_count} tables")
            
            # Check pgvector
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """))
            has_pgvector = result.scalar()
            if has_pgvector:
                print(" pgvector extension is enabled")
            else:
                print("  pgvector extension is NOT enabled")
            
        return True
    except Exception as e:
        print(f" Verification failed: {e}")
        return False


def create_test_data():
    """Create minimal test data (optional)."""
    print("\n Creating test data...")
    try:
        from database.core.connection import get_db
        from database.models import User
        from datetime import datetime
        import hashlib
        
        with get_db() as db:
            # Create a test user
            test_user = User(
                email="test@example.com",
                username="testuser",
                hashed_password=hashlib.sha256("password123".encode()).hexdigest(),
                full_name="Test User",
                subscription_tier="free",
                is_verified=True,
                created_at=datetime.utcnow()
            )
            db.add(test_user)
            db.commit()
            print(" Created test user: test@example.com")
        
        return True
    except Exception as e:
        print(f"  Could not create test data: {e}")
        return False


def main():
    """Main function to reset the database."""
    print("\n Database Reset Script")
    print(f" Database URL: {os.getenv('DATABASE_URL', 'postgresql://localhost/grading_system')}")
    
    # Check if running with --force flag (skip confirmation)
    force = '--force' in sys.argv or '-f' in sys.argv
    create_test = '--test-data' in sys.argv or '-t' in sys.argv
    
    if not force:
        if not confirm_reset():
            print("\n Database reset cancelled")
            sys.exit(0)
    
    print("\n Starting database reset...")
    
    # Step 1: Drop all tables
    if not drop_all_tables():
        print("\n Reset failed at drop tables step")
        sys.exit(1)
    
    # Step 2: Create all tables
    if not create_all_tables():
        print("\n Reset failed at create tables step")
        sys.exit(1)
    
    # Step 3: Verify database
    if not verify_database():
        print("\n Reset failed at verification step")
        sys.exit(1)
    
    # Step 4: Create test data (optional)
    if create_test:
        create_test_data()
    
    print("\n" + "=" * 60)
    print(" DATABASE RESET COMPLETE")
    print("=" * 60)
    print("\n Next steps:")
    print("  1. Start the application: python main.py")
    print("  2. Create your first user via the API")
    print("  3. Configure your environment variables")
    
    if create_test:
        print("\n Test data created:")
        print("  • Email: test@example.com")
        print("  • Password: password123")
    
    print("\n")


if __name__ == "__main__":
    # Show help if requested
    if '--help' in sys.argv or '-h' in sys.argv:
        print("""
Database Reset Script

Usage:
  python reset_db.py [OPTIONS]

Options:
  -h, --help       Show this help message
  -f, --force      Skip confirmation prompt (use with caution!)
  -t, --test-data  Create test data after reset
  
Examples:
  python reset_db.py                 # Interactive reset
  python reset_db.py --force         # Reset without confirmation
  python reset_db.py -f -t           # Reset and create test data
  
WARNING: This will DELETE ALL DATA in the database!
        """)
        sys.exit(0)
    
    main()
