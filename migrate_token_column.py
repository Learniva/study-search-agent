#!/usr/bin/env python3
"""
Migration Script: Increase Token Column Size

This script increases the token column size from 64 to 128 characters
to fix the token validation bug where tokens were being truncated.

Issue: Tokens generated with secrets.token_urlsafe(48) can be longer than 64 chars,
causing them to be truncated when saved, which breaks validation.

Run this script ONCE before restarting the application.
"""

import asyncio
import sys
from sqlalchemy import text
from database.core.async_connection import async_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_token_column():
    """Increase token column size from 64 to 128 characters."""
    
    try:
        async with async_engine.begin() as conn:
            logger.info("🔄 Starting token column migration...")
            
            # Check if tokens table exists
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'tokens'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("ℹ️  Tokens table doesn't exist yet. Will be created with correct size.")
                return True
            
            # Get current column size
            result = await conn.execute(text("""
                SELECT character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'tokens' 
                AND column_name = 'token';
            """))
            current_size = result.scalar()
            
            if current_size == 128:
                logger.info("✅ Token column is already 128 characters. No migration needed.")
                return True
            
            logger.info(f"📊 Current token column size: {current_size}")
            logger.info("🔧 Altering token column to VARCHAR(128)...")
            
            # Alter the column
            await conn.execute(text("""
                ALTER TABLE tokens 
                ALTER COLUMN token TYPE VARCHAR(128);
            """))
            
            logger.info("✅ Token column successfully migrated to VARCHAR(128)")
            
            # Verify the change
            result = await conn.execute(text("""
                SELECT character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'tokens' 
                AND column_name = 'token';
            """))
            new_size = result.scalar()
            
            logger.info(f"✅ Verified: Token column is now {new_size} characters")
            
            # Clear existing tokens (they may be truncated)
            result = await conn.execute(text("DELETE FROM tokens;"))
            deleted_count = result.rowcount
            logger.info(f"🗑️  Cleared {deleted_count} existing tokens (they may have been truncated)")
            logger.info("ℹ️  Users will need to log in again after this migration")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error("Please check your database connection and try again.")
        return False


async def main():
    """Main migration function."""
    logger.info("=" * 60)
    logger.info("Token Column Migration Script")
    logger.info("=" * 60)
    
    success = await migrate_token_column()
    
    if success:
        logger.info("=" * 60)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("Next steps:")
        logger.info("1. Restart your application")
        logger.info("2. All users will need to log in again")
        logger.info("3. New tokens will be saved correctly")
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("❌ Migration failed!")
        logger.error("=" * 60)
        logger.error("Please fix the errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
