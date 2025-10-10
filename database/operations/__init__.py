"""
Database Operations Package

High-level database operations organized by purpose:
- grading: Grading sessions, rubrics, configurations
- rag: RAG operations (L2/L3 memory stores)
"""

# Grading operations
from .grading import (
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
    log_audit as log_audit_action,
    get_audit_logs,
    get_grading_statistics,
    create_or_update_statistics,
)

# Backward compatibility alias
log_audit = log_audit_action

# RAG operations (Phase 1 - Agentic RAG)
from .rag import (
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

__all__ = [
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
    'log_audit_action',
    'log_audit',  # Alias for backward compatibility
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
]

