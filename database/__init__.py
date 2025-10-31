"""
Database Package

Organized by purpose for better modularity:
- core: Database connection and session management
- models: SQLAlchemy models (user, grading, rag, audit)
- operations: High-level database operations
- checkpointing: LangGraph checkpointing for conversation memory

All modules provide backward-compatible exports through this __init__.py.
"""

# Core database connection
from .core import (
    engine,
    SessionLocal,
    get_engine,
    get_db,
    get_db_dependency,
    init_db,
    close_db,
    check_db_connection,
)

# Models
from .models import (
    Base,
    User,
    GradingSession,
    RubricTemplate,
    ProfessorConfiguration,
    GradingStatistics,
    AuditLog,
    DocumentVector,
    GradeException,
    RAGQueryLog,
    create_tables,
    drop_tables,
)

# Operations
from .operations import (
    # Grading operations
    get_or_create_user,
    save_grading_session,
    get_grading_history,
    update_grading_session,
    get_rubric_templates,
    save_rubric_template,
    update_rubric_template,
    delete_rubric_template,
    get_or_create_professor_configuration,
    update_professor_configuration,
    log_audit,
    log_audit_action,
    get_audit_logs,
    get_grading_statistics,
    create_or_update_statistics,
    
    # RAG operations
    store_document_vectors,
    search_similar_documents,
    update_document_feedback,
    delete_document_vectors,
    get_document_by_id,
    log_grade_exception,
    get_grade_exceptions,
    update_grade_exception,
    analyze_grade_exceptions,
    log_rag_query,
    get_rag_query_logs,
    analyze_rag_performance,
)

# Checkpointing (Optional - requires langgraph)
try:
    from .checkpointing import (
        PostgresCheckpointSaver,
        get_postgres_checkpointer,
        DATABASE_AVAILABLE as CHECKPOINTING_AVAILABLE,
    )
    CHECKPOINTING_AVAILABLE = True
except ImportError:
    CHECKPOINTING_AVAILABLE = False

__all__ = [
    # Core
    'engine',
    'SessionLocal',
    'get_engine',
    'get_db',
    'get_db_dependency',
    'init_db',
    'close_db',
    'check_db_connection',
    
    # Models
    'Base',
    'User',
    'GradingSession',
    'RubricTemplate',
    'ProfessorConfiguration',
    'GradingStatistics',
    'AuditLog',
    'DocumentVector',
    'GradeException',
    'RAGQueryLog',
    'create_tables',
    'drop_tables',
    
    # Grading operations
    'get_or_create_user',
    'save_grading_session',
    'get_grading_history',
    'update_grading_session',
    'get_rubric_templates',
    'save_rubric_template',
    'update_rubric_template',
    'delete_rubric_template',
    'get_or_create_professor_configuration',
    'update_professor_configuration',
    'log_audit',
    'log_audit_action',
    'get_audit_logs',
    'get_grading_statistics',
    'create_or_update_statistics',
    
    # RAG operations
    'store_document_vectors',
    'search_similar_documents',
    'update_document_feedback',
    'delete_document_vectors',
    'get_document_by_id',
    'log_grade_exception',
    'get_grade_exceptions',
    'update_grade_exception',
    'analyze_grade_exceptions',
    'log_rag_query',
    'get_rag_query_logs',
    'analyze_rag_performance',
    
    # Feature flags
    'CHECKPOINTING_AVAILABLE',
]

# Add checkpointing exports if available
if CHECKPOINTING_AVAILABLE:
    __all__.extend([
        'PostgresCheckpointSaver',
        'get_postgres_checkpointer',
    ])

