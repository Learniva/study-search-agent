"""
Phase 2.3: PostgreSQL Checkpointer for LangGraph

Implements persistent conversation memory using PostgreSQL instead of in-memory MemorySaver.
This enables context-aware follow-up questions across sessions.

Example:
  User: "Who founded Code Savanna?"
  Agent: "Anthony Maniko founded Code Savanna..."
  User: "What else did he create?"  # Uses previous context
  Agent: "Anthony Maniko also created..."  # Knows "he" = "Anthony Maniko"
"""

import json
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from contextlib import contextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata

# Database imports
try:
    from sqlalchemy import Column, String, DateTime, Text, create_engine, Index
    from sqlalchemy.orm import Session, sessionmaker, declarative_base
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from database.core import engine, SessionLocal
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


if DATABASE_AVAILABLE:
    Base = declarative_base()
    
    class CheckpointRecord(Base):
        """
        Table for storing LangGraph checkpoints (conversation state).
        
        Enables persistent multi-turn conversations with full state management.
        """
        __tablename__ = "langgraph_checkpoints"
        
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        thread_id = Column(String(255), nullable=False, index=True)
        checkpoint_id = Column(String(255), nullable=False, index=True)
        parent_checkpoint_id = Column(String(255), nullable=True)
        
        # Checkpoint data (full conversation state)
        checkpoint_data = Column(JSONB, nullable=False)
        checkpoint_metadata = Column(JSONB, default={})
        
        # Timestamps
        created_at = Column(DateTime, default=datetime.utcnow, index=True)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        __table_args__ = (
            Index("idx_thread_checkpoint", "thread_id", "checkpoint_id"),
        )


class PostgresCheckpointSaver(BaseCheckpointSaver):
    """
    PostgreSQL-backed checkpoint saver for LangGraph.
    
    Phase 2.3: Enables persistent conversation memory across sessions.
    
    Features:
    - Stores full conversation state in PostgreSQL
    - Supports multi-turn context-aware conversations
    - Enables follow-up questions like "What else did he create?"
    - Persistent across application restarts
    """
    
    def __init__(self):
        """Initialize PostgreSQL checkpointer."""
        if not DATABASE_AVAILABLE:
            raise ImportError("PostgreSQL checkpointer requires database module")
        
        # Create checkpoint table if it doesn't exist
        Base.metadata.create_all(bind=engine)
        
        self.session_factory = SessionLocal
        
        print("✅ PostgreSQL Checkpointer initialized")
    
    @contextmanager
    def _get_session(self):
        """Context manager for database sessions."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata
    ) -> Dict[str, Any]:
        """
        Save a checkpoint to PostgreSQL.
        
        Args:
            config: Configuration dict with thread_id
            checkpoint: Checkpoint data to save
            metadata: Checkpoint metadata
            
        Returns:
            Updated config with checkpoint information
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        
        with self._get_session() as session:
            # Check if checkpoint already exists
            existing = session.query(CheckpointRecord).filter_by(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id
            ).first()
            
            if existing:
                # Update existing checkpoint
                existing.checkpoint_data = checkpoint
                existing.checkpoint_metadata = metadata
                existing.updated_at = datetime.utcnow()
            else:
                # Create new checkpoint
                record = CheckpointRecord(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=checkpoint.get("parent_id"),
                    checkpoint_data=checkpoint,
                    checkpoint_metadata=metadata
                )
                session.add(record)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """
        Retrieve a checkpoint from PostgreSQL.
        
        Args:
            config: Configuration dict with thread_id (and optional checkpoint_id)
            
        Returns:
            Checkpoint data or None if not found
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")
        
        with self._get_session() as session:
            if checkpoint_id:
                # Get specific checkpoint
                record = session.query(CheckpointRecord).filter_by(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id
                ).first()
            else:
                # Get latest checkpoint for thread
                record = session.query(CheckpointRecord).filter_by(
                    thread_id=thread_id
                ).order_by(CheckpointRecord.created_at.desc()).first()
            
            if record:
                return record.checkpoint_data
            return None
    
    def list(
        self,
        config: Dict[str, Any],
        limit: Optional[int] = None,
        before: Optional[str] = None
    ) -> List[Checkpoint]:
        """
        List checkpoints for a thread.
        
        Args:
            config: Configuration dict with thread_id
            limit: Maximum number of checkpoints to return
            before: Only return checkpoints before this checkpoint_id
            
        Returns:
            List of checkpoints
        """
        thread_id = config["configurable"]["thread_id"]
        
        with self._get_session() as session:
            query = session.query(CheckpointRecord).filter_by(
                thread_id=thread_id
            ).order_by(CheckpointRecord.created_at.desc())
            
            if before:
                before_record = session.query(CheckpointRecord).filter_by(
                    thread_id=thread_id,
                    checkpoint_id=before
                ).first()
                if before_record:
                    query = query.filter(
                        CheckpointRecord.created_at < before_record.created_at
                    )
            
            if limit:
                query = query.limit(limit)
            
            records = query.all()
            return [record.checkpoint_data for record in records]


def get_postgres_checkpointer():
    """
    Get or create a PostgreSQL checkpointer instance.
    
    Returns:
        PostgresCheckpointSaver instance or None if database not available
    """
    if not DATABASE_AVAILABLE:
        print("⚠️  PostgreSQL checkpointer not available - using in-memory fallback")
        return None
    
    try:
        return PostgresCheckpointSaver()
    except Exception as e:
        print(f"⚠️  Failed to initialize PostgreSQL checkpointer: {e}")
        return None

