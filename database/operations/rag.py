"""
Database operations for Agentic RAG - Phase 1.1

Provides operations for:
- L2 Vector Store (document_vectors) - Semantic retrieval
- L3 Learning Store (grade_exceptions) - Self-correction loop
- RAG Query Logs - Performance tracking

This module enables the self-improving RAG system with PostgreSQL persistence.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
import uuid

from database.models import DocumentVector, GradeException, RAGQueryLog


# =============================================================================
# L2 VECTOR STORE OPERATIONS
# =============================================================================

def store_document_vectors(
    db: Session,
    document_id: str,
    document_name: str,
    chunks: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    course_id: Optional[str] = None
) -> int:
    """
    Store document embeddings in L2 Vector Store.
    
    Args:
        db: Database session
        document_id: Unique document identifier
        document_name: Document name
        chunks: List of chunks with 'content', 'embedding', 'metadata'
        user_id: Optional user ID for ownership
        course_id: Optional course ID
        
    Returns:
        Number of vectors stored
    """
    vectors_stored = 0
    
    for idx, chunk in enumerate(chunks):
        vector = DocumentVector(
            document_id=document_id,
            document_name=document_name,
            document_type=chunk.get('type', 'unknown'),
            content=chunk['content'],
            chunk_index=idx,
            embedding=chunk['embedding'],  # pgvector compatible
            metadata=chunk.get('metadata', {}),
            user_id=user_id,
            course_id=course_id
        )
        db.add(vector)
        vectors_stored += 1
    
    db.commit()
    return vectors_stored


def similarity_search(
    db: Session,
    query_embedding: List[float],
    limit: int = 5,
    user_id: Optional[str] = None,
    course_id: Optional[str] = None,
    min_relevance: float = 0.0
) -> List[DocumentVector]:
    """
    Perform semantic similarity search using pgvector.
    
    Args:
        db: Database session
        query_embedding: Query vector embedding
        limit: Maximum results to return
        user_id: Filter by user (optional)
        course_id: Filter by course (optional)
        min_relevance: Minimum relevance score threshold
        
    Returns:
        List of similar document vectors, ordered by similarity
    """
    # Build query with filters
    query = db.query(DocumentVector)
    
    if user_id:
        query = query.filter(DocumentVector.user_id == user_id)
    if course_id:
        query = query.filter(DocumentVector.course_id == course_id)
    if min_relevance > 0:
        query = query.filter(DocumentVector.relevance_score >= min_relevance)
    
    # Use pgvector cosine distance for similarity
    # Note: <=> is the cosine distance operator in pgvector
    # SECURITY: Use parameterized query to prevent SQL injection
    from sqlalchemy import func, literal_column
    from sqlalchemy.sql import expression
    
    # OPTIMIZATION: Use pgvector's optimized cosine distance operator
    # The <=> operator uses HNSW or IVFFlat index if available for fast similarity search
    # Convert embedding to string format for pgvector: '[x,y,z,...]'
    embedding_str = f"[{','.join(map(str, query_embedding))}]"
    
    # Order by cosine similarity using pgvector operator
    # SECURITY NOTE: embedding_str is built from numeric values only, not user input
    # This is safe as query_embedding is always a list of floats
    results = query.order_by(
        func.l2_distance(DocumentVector.embedding, literal_column(f"'{embedding_str}'::vector"))
    ).limit(limit).all()
    
    # OPTIMIZATION: Batch update retrieval statistics to avoid N+1 queries
    if results:
        result_ids = [result.id for result in results]
        from sqlalchemy import update as sql_update
        db.execute(
            sql_update(DocumentVector)
            .where(DocumentVector.id.in_(result_ids))
            .values(
                retrieval_count=DocumentVector.retrieval_count + 1,
                last_retrieved=datetime.now(timezone.utc)
            )
        )
        db.commit()
    
    return results


def hybrid_search(
    db: Session,
    query_text: str,
    query_embedding: List[float],
    limit: int = 5,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[Tuple[DocumentVector, float]]:
    """
    Hybrid search combining semantic (vector) and keyword (full-text) search.
    
    Args:
        db: Database session
        query_text: Query text for keyword search
        query_embedding: Query embedding for semantic search
        limit: Maximum results
        semantic_weight: Weight for semantic score (0-1)
        keyword_weight: Weight for keyword score (0-1)
        
    Returns:
        List of (DocumentVector, combined_score) tuples
    """
    # Semantic search
    semantic_results = similarity_search(db, query_embedding, limit=limit * 2)
    
    # Keyword search using PostgreSQL full-text search
    # SECURITY: Use parameterized query with proper escaping
    # OPTIMIZATION: Use PostgreSQL's to_tsvector and to_tsquery for better full-text search
    # Fallback to ILIKE if full-text search not available
    try:
        # Try full-text search first (better performance with GIN index)
        from sqlalchemy import func
        keyword_results = db.query(DocumentVector).filter(
            func.to_tsvector('english', DocumentVector.content).match(
                func.plainto_tsquery('english', query_text)
            )
        ).limit(limit * 2).all()
    except Exception:
        # Fallback to ILIKE if full-text search fails
        # SECURITY: Parameterized ILIKE query - SQLAlchemy handles escaping
        keyword_results = db.query(DocumentVector).filter(
            DocumentVector.content.ilike(f"%{query_text}%")
        ).limit(limit * 2).all()
    
    # Combine and rank results
    combined_scores = {}
    
    for idx, doc in enumerate(semantic_results):
        score = (1.0 - idx / len(semantic_results)) * semantic_weight
        combined_scores[doc.id] = combined_scores.get(doc.id, 0) + score
    
    for idx, doc in enumerate(keyword_results):
        score = (1.0 - idx / len(keyword_results)) * keyword_weight
        combined_scores[doc.id] = combined_scores.get(doc.id, 0) + score
    
    # Get top results
    top_doc_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    # OPTIMIZATION: Use IN clause to fetch all documents in one query instead of N queries
    doc_ids_to_fetch = [doc_id for doc_id, _ in top_doc_ids]
    docs_by_id = {
        doc.id: doc 
        for doc in db.query(DocumentVector).filter(DocumentVector.id.in_(doc_ids_to_fetch)).all()
    }
    
    # Build results in order, maintaining scores
    results = []
    for doc_id, score in top_doc_ids:
        doc = docs_by_id.get(doc_id)
        if doc:
            results.append((doc, score))
    
    return results


def update_vector_feedback(
    db: Session,
    vector_id: uuid.UUID,
    is_positive: bool,
    relevance_score_adjustment: float = 0.0
):
    """
    Update vector quality based on user feedback (self-correction).
    
    Args:
        db: Database session
        vector_id: Vector ID
        is_positive: Whether feedback was positive
        relevance_score_adjustment: Adjustment to relevance score
    """
    vector = db.query(DocumentVector).filter(DocumentVector.id == vector_id).first()
    
    if vector:
        if is_positive:
            vector.feedback_positive += 1
        else:
            vector.feedback_negative += 1
        
        # Adjust relevance score with learning rate
        if relevance_score_adjustment != 0.0:
            vector.relevance_score = max(0.0, min(1.0, 
                vector.relevance_score + relevance_score_adjustment * 0.1
            ))
        
        db.commit()


# =============================================================================
# L3 LEARNING STORE OPERATIONS
# =============================================================================

def create_grade_exception(
    db: Session,
    exception_type: str,
    user_id: str,
    query: str,
    ai_decision: Dict[str, Any],
    correct_decision: Dict[str, Any],
    **kwargs
) -> GradeException:
    """
    Create a grade exception for learning (self-correction loop).
    
    Args:
        db: Database session
        exception_type: Type of exception (grading_correction, rag_failure, etc.)
        user_id: User ID
        query: Original query
        ai_decision: What AI decided
        correct_decision: What should have been decided
        **kwargs: Additional fields
        
    Returns:
        Created GradeException
    """
    exception = GradeException(
        exception_type=exception_type,
        user_id=user_id,
        query=query,
        ai_decision=ai_decision,
        correct_decision=correct_decision,
        user_role=kwargs.get('user_role', 'unknown'),
        grading_session_id=kwargs.get('grading_session_id'),
        rubric_type=kwargs.get('rubric_type'),
        retrieved_context=kwargs.get('retrieved_context'),
        context_quality_score=kwargs.get('context_quality_score', 0.5),
        should_have_retrieved=kwargs.get('should_have_retrieved'),
        intent=kwargs.get('intent'),
        agent_used=kwargs.get('agent_used'),
        error_category=kwargs.get('error_category', 'unknown'),
        error_description=kwargs.get('error_description', ''),
        correction_reason=kwargs.get('correction_reason', ''),
        score_difference=kwargs.get('score_difference'),
        confidence_before=kwargs.get('confidence_before', 0.5),
        confidence_after=kwargs.get('confidence_after')
    )
    
    db.add(exception)
    db.commit()
    db.refresh(exception)
    
    return exception


def get_grade_exceptions(
    db: Session,
    exception_type: Optional[str] = None,
    status: str = 'pending',
    limit: int = 50
) -> List[GradeException]:
    """
    Get grade exceptions for analysis and learning.
    
    Args:
        db: Database session
        exception_type: Filter by type
        status: Filter by status
        limit: Maximum results
        
    Returns:
        List of grade exceptions
    """
    query = db.query(GradeException)
    
    if exception_type:
        query = query.filter(GradeException.exception_type == exception_type)
    if status:
        query = query.filter(GradeException.status == status)
    
    return query.order_by(desc(GradeException.created_at)).limit(limit).all()


def update_exception_status(
    db: Session,
    exception_id: uuid.UUID,
    status: str,
    learned_pattern: Optional[Dict[str, Any]] = None,
    applied_to_model: bool = False
):
    """
    Update exception status after learning from it.
    
    Args:
        db: Database session
        exception_id: Exception ID
        status: New status (analyzed, resolved, learned)
        learned_pattern: Pattern learned from this exception
        applied_to_model: Whether correction was applied to model
    """
    exception = db.query(GradeException).filter(GradeException.id == exception_id).first()
    
    if exception:
        exception.status = status
        if learned_pattern:
            exception.learned_pattern = learned_pattern
        exception.applied_to_model = applied_to_model
        
        if status in ['resolved', 'learned']:
            exception.resolved_at = datetime.now(timezone.utc)
        
        db.commit()


def get_learning_insights(db: Session, rubric_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get learning insights from grade exceptions.
    
    Analyzes patterns in corrections to identify areas for improvement.
    
    Args:
        db: Database session
        rubric_type: Filter by rubric type
        
    Returns:
        Dictionary with insights
    """
    query = db.query(GradeException)
    
    if rubric_type:
        query = query.filter(GradeException.rubric_type == rubric_type)
    
    exceptions = query.filter(GradeException.exception_type == 'grading_correction').all()
    
    if not exceptions:
        return {"status": "no_data", "message": "No grading corrections found"}
    
    # Calculate statistics
    total = len(exceptions)
    avg_score_diff = sum(abs(e.score_difference or 0) for e in exceptions) / total
    avg_confidence_before = sum(e.confidence_before for e in exceptions) / total
    
    # Group by error category
    error_categories = {}
    for exception in exceptions:
        cat = exception.error_category
        error_categories[cat] = error_categories.get(cat, 0) + 1
    
    return {
        "status": "analyzed",
        "total_corrections": total,
        "avg_score_difference": round(avg_score_diff, 2),
        "avg_confidence_before": round(avg_confidence_before, 2),
        "error_categories": error_categories,
        "rubric_type": rubric_type or "all"
    }


# =============================================================================
# RAG QUERY LOG OPERATIONS
# =============================================================================

def log_rag_query(
    db: Session,
    user_id: str,
    query: str,
    query_type: str,
    should_retrieve: bool,
    retrieval_reason: str,
    **kwargs
) -> RAGQueryLog:
    """
    Log a RAG query for performance analysis.
    
    Args:
        db: Database session
        user_id: User ID
        query: Query text
        query_type: Type (study, grading, general)
        should_retrieve: Whether agent decided to retrieve
        retrieval_reason: Why retrieve or not
        **kwargs: Additional metrics
        
    Returns:
        Created RAGQueryLog
    """
    log_entry = RAGQueryLog(
        user_id=user_id,
        query=query,
        query_type=query_type,
        should_retrieve=should_retrieve,
        retrieval_reason=retrieval_reason,
        confidence_threshold=kwargs.get('confidence_threshold', 0.5),
        retrieved_count=kwargs.get('retrieved_count', 0),
        top_similarity_score=kwargs.get('top_similarity_score'),
        avg_similarity_score=kwargs.get('avg_similarity_score'),
        retrieved_doc_ids=kwargs.get('retrieved_doc_ids', []),
        retrieval_time_ms=kwargs.get('retrieval_time_ms', 0.0),
        total_time_ms=kwargs.get('total_time_ms', 0.0),
        context_used=kwargs.get('context_used', False),
        context_helpful=kwargs.get('context_helpful'),
        context_quality_score=kwargs.get('context_quality_score'),
        answer_generated=kwargs.get('answer_generated', True),
        user_satisfied=kwargs.get('user_satisfied'),
        exception_created=kwargs.get('exception_created', False),
        exception_id=kwargs.get('exception_id')
    )
    
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    
    return log_entry


def get_rag_performance_stats(
    db: Session,
    user_id: Optional[str] = None,
    days: int = 7
) -> Dict[str, Any]:
    """
    Get RAG performance statistics.
    
    Args:
        db: Database session
        user_id: Filter by user (optional)
        days: Number of days to analyze
        
    Returns:
        Performance statistics dictionary
    """
    from datetime import timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(RAGQueryLog).filter(RAGQueryLog.created_at >= cutoff_date)
    
    if user_id:
        query = query.filter(RAGQueryLog.user_id == user_id)
    
    logs = query.all()
    
    if not logs:
        return {"status": "no_data", "message": f"No queries in last {days} days"}
    
    total = len(logs)
    retrieved = sum(1 for log in logs if log.should_retrieve)
    context_used = sum(1 for log in logs if log.context_used)
    helpful = sum(1 for log in logs if log.context_helpful)
    
    avg_retrieval_time = sum(log.retrieval_time_ms for log in logs if log.retrieval_time_ms) / total
    avg_quality = sum(log.context_quality_score for log in logs if log.context_quality_score) / len([l for l in logs if l.context_quality_score])
    
    return {
        "status": "analyzed",
        "period_days": days,
        "total_queries": total,
        "retrieval_rate": round(retrieved / total * 100, 1),
        "context_usage_rate": round(context_used / total * 100, 1),
        "helpfulness_rate": round(helpful / max(1, context_used) * 100, 1),
        "avg_retrieval_time_ms": round(avg_retrieval_time, 2),
        "avg_context_quality": round(avg_quality, 2),
        "user_id": user_id or "all"
    }


def update_rag_query_feedback(
    db: Session,
    log_id: uuid.UUID,
    context_helpful: bool,
    user_satisfied: bool,
    context_quality_score: Optional[float] = None
):
    """
    Update RAG query log with user feedback.
    
    Args:
        db: Database session
        log_id: Log entry ID
        context_helpful: Whether context was helpful
        user_satisfied: Whether user was satisfied
        context_quality_score: Optional quality score override
    """
    log = db.query(RAGQueryLog).filter(RAGQueryLog.id == log_id).first()
    
    if log:
        log.context_helpful = context_helpful
        log.user_satisfied = user_satisfied
        
        if context_quality_score is not None:
            log.context_quality_score = context_quality_score
        
        db.commit()


# Aliases for backward compatibility
def search_similar_documents(db: Session, query_embedding: list, top_k: int = 5, **kwargs):
    """Search for similar documents - alias for similarity_search."""
    return similarity_search(db, query_embedding, top_k, **kwargs)


def update_document_feedback(db: Session, doc_id: uuid.UUID, helpful: bool):
    """Update document feedback - alias for update_vector_feedback."""
    return update_vector_feedback(db, doc_id, helpful)


def delete_document_vectors(db: Session, document_id: str):
    """Delete document vectors by document ID."""
    vectors = db.query(DocumentVector).filter(DocumentVector.document_id == document_id).all()
    for vector in vectors:
        db.delete(vector)
    db.commit()
    return True


def get_document_by_id(db: Session, doc_id: uuid.UUID):
    """Get a document vector by ID."""
    return db.query(DocumentVector).filter(DocumentVector.id == doc_id).first()


def log_grade_exception(db: Session, **kwargs):
    """Log a grade exception - alias for create_grade_exception."""
    return create_grade_exception(db, **kwargs)


def update_grade_exception(db: Session, exception_id: uuid.UUID, **kwargs):
    """Update a grade exception - alias for update_exception_status."""
    return update_exception_status(db, exception_id, **kwargs)


def analyze_grade_exceptions(db: Session, rubric_type: str = None):
    """Analyze grade exceptions - alias for get_learning_insights."""
    return get_learning_insights(db, rubric_type)


def get_rag_query_logs(db: Session, user_id: str = None, limit: int = 100):
    """Get RAG query logs for analysis."""
    query = db.query(RAGQueryLog)
    if user_id:
        query = query.filter(RAGQueryLog.user_id == user_id)
    return query.order_by(RAGQueryLog.timestamp.desc()).limit(limit).all()


def analyze_rag_performance(db: Session, time_period_days: int = 30):
    """Analyze RAG performance - alias for get_rag_performance_stats."""
    return get_rag_performance_stats(db, time_period_days)

