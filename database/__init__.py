"""
Database package for PostgreSQL integration.
"""

from database.models import (
    Base,
    User,
    GradingSession,
    RubricTemplate,
    ProfessorConfiguration,
    AuditLog,
    GradingStatistics
)
from database.database import (
    get_engine,
    get_session,
    init_db,
    get_db
)
from database.operations import (
    save_grading_session,
    get_grading_history,
    save_rubric_template,
    get_rubric_templates,
    get_or_create_user,
    log_audit,
    update_grading_statistics
)

__all__ = [
    # Models
    "Base",
    "User",
    "GradingSession",
    "RubricTemplate",
    "ProfessorConfiguration",
    "AuditLog",
    "GradingStatistics",
    # Database connection
    "get_engine",
    "get_session",
    "init_db",
    "get_db",
    # Operations
    "save_grading_session",
    "get_grading_history",
    "save_rubric_template",
    "get_rubric_templates",
    "get_or_create_user",
    "log_audit",
    "update_grading_statistics",
]

