"""
Database Migration: Add Refresh Tokens Table

Creates the refresh_tokens table for implementing refresh token rotation
with server-side revocation.

Run this migration to add refresh token support to existing databases.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database.core.async_engine import get_async_db
from utils.monitoring import get_logger

logger = get_logger(__name__)


async def create_refresh_tokens_table(session: AsyncSession) -> bool:
    """
    Create refresh_tokens table.
    
    Args:
        session: Database session
    
    Returns:
        True if successful
    """
    try:
        logger.info("📋 Creating refresh_tokens table...")
        
        # Create table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_id VARCHAR(36) PRIMARY KEY,
                token VARCHAR(512) NOT NULL UNIQUE,
                user_id VARCHAR(255) NOT NULL,
                parent_token_id VARCHAR(36),
                rotation_chain_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                used_at TIMESTAMP WITH TIME ZONE,
                is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
                revoked_at TIMESTAMP WITH TIME ZONE,
                revocation_reason VARCHAR(255),
                device_info VARCHAR(500),
                ip_address VARCHAR(45),
                
                -- Foreign key constraints
                CONSTRAINT fk_refresh_tokens_user
                    FOREIGN KEY (user_id) 
                    REFERENCES users(user_id) 
                    ON DELETE CASCADE,
                
                CONSTRAINT fk_refresh_tokens_parent
                    FOREIGN KEY (parent_token_id) 
                    REFERENCES refresh_tokens(token_id) 
                    ON DELETE SET NULL
            )
        """))
        
        logger.info("✅ refresh_tokens table created")
        
        # Create indexes for performance
        logger.info("📋 Creating indexes...")
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token 
            ON refresh_tokens(token)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id 
            ON refresh_tokens(user_id)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_parent 
            ON refresh_tokens(parent_token_id)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_chain 
            ON refresh_tokens(rotation_chain_id)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_is_revoked 
            ON refresh_tokens(is_revoked)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_token_chain_revoked 
            ON refresh_tokens(rotation_chain_id, is_revoked)
        """))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_token_user_active 
            ON refresh_tokens(user_id, is_revoked, expires_at)
        """))
        
        logger.info("✅ All indexes created")
        
        await session.commit()
        
        logger.info("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        await session.rollback()
        return False


async def verify_table_exists(session: AsyncSession) -> bool:
    """
    Verify that the refresh_tokens table exists.
    
    Args:
        session: Database session
    
    Returns:
        True if table exists
    """
    try:
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'refresh_tokens'
            )
        """))
        exists = result.scalar()
        return exists
    except Exception as e:
        logger.error(f"❌ Error checking table existence: {e}")
        return False


async def run_migration():
    """Run the migration."""
    logger.info("🚀 Starting refresh tokens migration...")
    
    async for session in get_async_db():
        try:
            # Check if table already exists
            exists = await verify_table_exists(session)
            
            if exists:
                logger.info("ℹ️  refresh_tokens table already exists, skipping migration")
                return True
            
            # Create table
            success = await create_refresh_tokens_table(session)
            
            if success:
                # Verify creation
                exists = await verify_table_exists(session)
                if exists:
                    logger.info("✅ Migration verified successfully!")
                    return True
                else:
                    logger.error("❌ Table creation verification failed")
                    return False
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Migration error: {e}")
            return False
        finally:
            await session.close()


async def rollback_migration():
    """Rollback the migration (drop table)."""
    logger.warning("⚠️  Rolling back refresh tokens migration...")
    
    async for session in get_async_db():
        try:
            await session.execute(text("DROP TABLE IF EXISTS refresh_tokens CASCADE"))
            await session.commit()
            logger.info("✅ Rollback completed successfully!")
            return True
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            await session.rollback()
            return False
        finally:
            await session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Refresh Tokens Migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (drop table)"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        print("\n⚠️  WARNING: This will drop the refresh_tokens table and all data!")
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == "yes":
            asyncio.run(rollback_migration())
        else:
            print("Rollback cancelled")
    else:
        asyncio.run(run_migration())
