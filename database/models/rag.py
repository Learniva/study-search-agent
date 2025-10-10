"""
RAG Models - Agentic RAG Memory Architecture 

Models for the self-improving RAG system:
- L2 Vector Store: Semantic document retrieval
- L3 Learning Store: Self-correction and learning
- RAG Query Logs: Performance tracking
"""

from .base import (
    Base, Column, String, Integer, Float, DateTime, Text, Boolean,
    ForeignKey, UUID, JSONB, Vector, Index, datetime, uuid
)


class DocumentVector(Base):
    """
    L2 Vector Store - Semantic vector storage for documents.
    
    This is the core of the Agentic RAG system's memory layer.
    Uses pgvector for efficient similarity search.
    
    Phase 1.1: PostgreSQL pgvector Setup
    - Enables hybrid retrieval (semantic + keyword)
    - Stores document embeddings with metadata
    - Supports similarity search for RAG
    """
    __tablename__ = "document_vectors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Document identification
    document_id = Column(String(255), nullable=False, index=True)
    document_name = Column(String(500))
    document_type = Column(String(50))  # pdf, docx, notes, etc.
    
    # Content
    content = Column(Text, nullable=False)  # Original text chunk
    chunk_index = Column(Integer)  # Position in document
    
    # Vector embedding (768 dimensions for Google Gemini models/embedding-001)
    # Provides effective semantic search for autonomous agent learning
    embedding = Column(Vector(768))  # pgvector column for semantic search
    
    # Metadata for context (renamed from 'metadata' to avoid SQLAlchemy conflict)
    doc_metadata = Column(JSONB)  # Additional metadata (page, section, etc.)
    
    # Usage tracking
    retrieval_count = Column(Integer, default=0)  # How many times retrieved
    last_retrieved = Column(DateTime, nullable=True)
    
    # Quality metrics (for self-improving RAG)
    relevance_score = Column(Float, default=0.5)  # Learned relevance
    feedback_positive = Column(Integer, default=0)  # Positive feedback count
    feedback_negative = Column(Integer, default=0)  # Negative feedback count
    
    # Ownership (optional - for user-specific documents)
    user_id = Column(String(255), index=True, nullable=True)
    course_id = Column(String(255), index=True, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for efficient retrieval
    __table_args__ = (
        Index("idx_document_chunk", "document_id", "chunk_index"),
        Index("idx_user_course", "user_id", "course_id"),
        Index("idx_retrieval_score", "retrieval_count", "relevance_score"),
    )
    
    def __repr__(self):
        return f"<DocumentVector(doc={self.document_name}, chunk={self.chunk_index})>"


class GradeException(Base):
    """
    L3 Learning Store - Stores grading exceptions for self-correction loop.
    
    This table captures cases where:
    - AI grading was corrected by professor
    - RAG retrieved irrelevant context
    - Routing decisions were suboptimal
    
    Phase 1.1: PostgreSQL pgvector Setup
    - Enables self-improving grading through learning from corrections
    - Feeds into adaptive rubric system
    - Used for grade_retrieval node to critique context quality
    """
    __tablename__ = "grade_exceptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Exception type
    exception_type = Column(String(50), nullable=False, index=True)
    # Types: 'grading_correction', 'rag_failure', 'routing_error', 'rubric_mismatch'
    
    # Context
    user_id = Column(String(255), index=True)
    user_role = Column(String(50))
    
    # For grading corrections
    grading_session_id = Column(UUID(as_uuid=True), ForeignKey("grading_sessions.id"), nullable=True)
    rubric_type = Column(String(50))
    
    # Original vs Corrected data
    ai_decision = Column(JSONB)  # Original AI output
    correct_decision = Column(JSONB)  # Corrected output
    
    # RAG context quality (for self-correction)
    retrieved_context = Column(JSONB, nullable=True)  # What RAG retrieved
    context_quality_score = Column(Float)  # 0-1 score
    should_have_retrieved = Column(Text, nullable=True)  # What should have been retrieved
    
    # Learning metadata
    query = Column(Text)  # Original query
    intent = Column(String(50))  # Detected intent
    agent_used = Column(String(100))  # Which agent processed it
    
    # Error details
    error_category = Column(String(100))  # Specific error type
    error_description = Column(Text)
    correction_reason = Column(Text)  # Why was correction needed
    
    # Impact metrics
    score_difference = Column(Float, nullable=True)  # For grading corrections
    confidence_before = Column(Float)
    confidence_after = Column(Float, nullable=True)
    
    # Resolution status
    status = Column(String(50), default='pending')  # pending, analyzed, resolved, learned
    learned_pattern = Column(JSONB, nullable=True)  # What pattern was learned
    applied_to_model = Column(Boolean, default=False)  # Whether correction was applied
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Indexes for learning queries
    __table_args__ = (
        Index("idx_exception_type_status", "exception_type", "status"),
        Index("idx_user_exceptions", "user_id", "exception_type"),
        Index("idx_rubric_corrections", "rubric_type", "exception_type"),
    )
    
    def __repr__(self):
        return f"<GradeException(type={self.exception_type}, status={self.status})>"


class RAGQueryLog(Base):
    """
    RAG Query Performance Tracking.
    
    Logs every RAG retrieval for performance analysis and self-improvement.
    Used by the agentic RAG system to decide when to retrieve context.
    
    Phase 1.1: Supports adaptive retrieval decisions
    """
    __tablename__ = "rag_query_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Query details
    user_id = Column(String(255), index=True)
    query = Column(Text, nullable=False)
    query_type = Column(String(50))  # study, grading, general
    
    # Retrieval decision (Agentic RAG)
    should_retrieve = Column(Boolean)  # Did agent decide to retrieve?
    retrieval_reason = Column(String(255))  # Why retrieve or not
    confidence_threshold = Column(Float)  # Confidence in decision
    
    # Retrieval results
    retrieved_count = Column(Integer, default=0)  # Number of chunks retrieved
    top_similarity_score = Column(Float)  # Best match score
    avg_similarity_score = Column(Float)  # Average match score
    
    # Retrieved document IDs (for analysis)
    retrieved_doc_ids = Column(JSONB)  # List of document_vector IDs
    
    # Performance metrics
    retrieval_time_ms = Column(Float)  # Time to retrieve
    total_time_ms = Column(Float)  # Total query time
    
    # Quality assessment (self-correcting)
    context_used = Column(Boolean, default=False)  # Was context actually used?
    context_helpful = Column(Boolean, nullable=True)  # User feedback
    context_quality_score = Column(Float, nullable=True)  # Auto-assessed quality
    
    # Outcome
    answer_generated = Column(Boolean, default=True)
    user_satisfied = Column(Boolean, nullable=True)  # Explicit feedback
    
    # Learning feedback
    exception_created = Column(Boolean, default=False)  # If retrieval failed
    exception_id = Column(UUID(as_uuid=True), ForeignKey("grade_exceptions.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_user_query_time", "user_id", "created_at"),
        Index("idx_retrieval_performance", "should_retrieve", "context_helpful"),
        Index("idx_quality_analysis", "context_quality_score", "user_satisfied"),
    )
    
    def __repr__(self):
        return f"<RAGQueryLog(query={self.query[:50]}, retrieved={self.retrieved_count})>"


__all__ = [
    'DocumentVector',
    'GradeException',
    'RAGQueryLog',
]

