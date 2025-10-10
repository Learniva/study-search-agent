"""
Database Models Base

Shared SQLAlchemy base and common imports for all model modules.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, Boolean,
    ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import uuid

# Shared declarative base for all models
Base = declarative_base()

__all__ = [
    'Base',
    'Column',
    'String',
    'Integer',
    'Float',
    'DateTime',
    'Text',
    'JSON',
    'Boolean',
    'ForeignKey',
    'Index',
    'relationship',
    'UUID',
    'JSONB',
    'Vector',
    'datetime',
    'uuid',
]

