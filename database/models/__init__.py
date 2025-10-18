"""
Database Models Package

Organized by purpose:
- base: Shared SQLAlchemy base and imports
- user: User authentication and profiles
- grading: Grading sessions, rubrics, configurations, statistics
- rag: Agentic RAG models (L2/L3 memory, query logs)
- audit: Audit logging and compliance
"""

from .base import Base

# User models
from .user import User, UserLearningProfile
from .token import Token

# Grading models
from .grading import (
    GradingSession,
    RubricTemplate,
    ProfessorConfiguration,
    GradingStatistics,
)

# RAG models (Phase 1 - Agentic RAG)
from .rag import (
    DocumentVector,
    GradeException,
    RAGQueryLog,
)

# Audit models
from .audit import AuditLog


# Helper functions
def create_tables(engine):
    """
    Create all database tables.
    
    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """
    Drop all database tables.
    
    WARNING: This will delete all data!
    
    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.drop_all(engine)


__all__ = [
    # Base
    'Base',
    
    # User models
    'User',
    'UserLearningProfile',
    'Token',
    
    # Grading models
    'GradingSession',
    'RubricTemplate',
    'ProfessorConfiguration',
    'GradingStatistics',
    
    # RAG models
    'DocumentVector',
    'GradeException',
    'RAGQueryLog',
    
    # Audit models
    'AuditLog',
    
    # Helper functions
    'create_tables',
    'drop_tables',
]


