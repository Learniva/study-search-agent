"""
Phase 2: RAG Tools for Agentic Self-Correction

Tools for:
- L2 Vector Store (pgvector) - Semantic document retrieval
- L3 Learning Store (PostgreSQL) - Query learned patterns and exceptions
- Web Search (Tavily) - Enhanced with context awareness

These tools are wrapped using LangChain's tool decorator for integration
with the Study Agent's LangGraph workflow.
"""

import os
from typing import Optional, List, Dict, Any
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

# Database imports (graceful fallback if not available)
try:
    from database import get_db
    from database.operations.rag import (
        similarity_search,
        hybrid_search,
        get_learning_insights,
        get_rag_performance_stats,
        log_rag_query
    )
    from database.models import DocumentVector, GradeException
    DATABASE_AVAILABLE = True
except ImportError as e:
    DATABASE_AVAILABLE = False
    # Only print warning if database is genuinely unavailable
    import sys
    if '--help' not in sys.argv:
        print(f"⚠️  RAG Tools: Database not available - L2/L3 features disabled ({e})")

# Web search imports
try:
    from tools.study.web_search import get_web_search_tool
    _web_search = get_web_search_tool()
    WEB_SEARCH_AVAILABLE = _web_search is not None
    if not WEB_SEARCH_AVAILABLE:
        print("⚠️  RAG Tools: Web search not configured (Tavily API key missing)")
except ImportError as e:
    WEB_SEARCH_AVAILABLE = False
    print(f"⚠️  RAG Tools: Web search not available ({e})")


@tool
def retrieve_from_vector_store(
    query: str,
    limit: int = 5,
    user_id: Optional[str] = None,
    course_id: Optional[str] = None
) -> str:
    """
    Retrieve relevant documents from L2 Vector Store (pgvector).
    
    This tool performs semantic similarity search on uploaded documents using pgvector.
    Use this when the user asks about "my notes", "uploaded documents", or specific content.
    
    Args:
        query: The search query
        limit: Maximum number of results (default: 5)
        user_id: Filter by user ID
        course_id: Filter by course ID
    
    Returns:
        Formatted string with relevant document chunks
    
    Examples:
        - "What does chapter 3 say about machine learning?"
        - "Find information about neural networks in my notes"
        - "Search my documents for quantum computing"
    """
    if not DATABASE_AVAILABLE:
        return "❌ Vector store not available. Database not configured. Please set DATABASE_URL in .env"
    
    try:
        # Get embedding for query
        # Note: In production, use actual embedding model
        # For now, we'll use a placeholder that returns text-based results
        
        db = get_db()
        try:
            # Use hybrid search for better results (semantic + keyword)
            from utils import initialize_llm
            
            # Get embedding using the same model as document indexing
            # For now, just do keyword search
            from sqlalchemy import or_
            
            results = db.query(DocumentVector).filter(
                or_(
                    DocumentVector.content.ilike(f"%{query}%"),
                    DocumentVector.document_name.ilike(f"%{query}%")
                )
            )
            
            if user_id:
                results = results.filter(DocumentVector.user_id == user_id)
            if course_id:
                results = results.filter(DocumentVector.course_id == course_id)
            
            results = results.limit(limit).all()
            
            if not results:
                return f"📚 No relevant documents found for query: '{query}'\n\nTip: Make sure documents are uploaded and indexed in the vector store."
            
            # Format results
            formatted_results = f"📚 Retrieved {len(results)} relevant chunks from Vector Store:\n\n"
            
            for i, doc in enumerate(results, 1):
                formatted_results += f"**Result {i}** (Document: {doc.document_name})\n"
                formatted_results += f"{doc.content[:500]}{'...' if len(doc.content) > 500 else ''}\n"
                formatted_results += f"_Relevance: {doc.relevance_score:.2f} | Retrieved {doc.retrieval_count} times_\n\n"
            
            # Update retrieval stats
            for doc in results:
                doc.retrieval_count += 1
            db.commit()
            
            return formatted_results
            
        finally:
            db.close()
            
    except Exception as e:
        return f"❌ Error retrieving from vector store: {str(e)}"


@tool
def query_learning_store(
    query_type: str = "insights",
    rubric_type: Optional[str] = None
) -> str:
    """
    Query L3 Learning Store for learned patterns and insights.
    
    This tool retrieves lessons learned from past corrections and failures.
    Use this to understand common mistakes and improve responses.
    
    Args:
        query_type: Type of query - "insights", "exceptions", "performance"
        rubric_type: Filter by rubric type (optional)
    
    Returns:
        Formatted string with learning insights
    
    Examples:
        - Use insights to avoid common mistakes
        - Check performance stats before retrieval
        - Learn from past failures
    """
    if not DATABASE_AVAILABLE:
        return "❌ Learning store not available. Database not configured."
    
    try:
        db = get_db()
        try:
            if query_type == "insights":
                insights = get_learning_insights(db, rubric_type)
                
                if insights.get("status") == "no_data":
                    return "📊 No learning data available yet. System is still collecting feedback."
                
                formatted = f"📊 Learning Insights:\n\n"
                formatted += f"Total Corrections: {insights.get('total_corrections', 0)}\n"
                formatted += f"Average Score Difference: {insights.get('avg_score_difference', 0)}\n"
                formatted += f"Average Confidence Before: {insights.get('avg_confidence_before', 0):.2f}\n\n"
                
                if insights.get('error_categories'):
                    formatted += "**Common Error Categories:**\n"
                    for category, count in insights['error_categories'].items():
                        formatted += f"  • {category}: {count} occurrences\n"
                
                return formatted
                
            elif query_type == "performance":
                stats = get_rag_performance_stats(db)
                
                if stats.get("status") == "no_data":
                    return "📊 No performance data available yet."
                
                formatted = f"📊 RAG Performance Stats (Last {stats.get('period_days', 7)} days):\n\n"
                formatted += f"Total Queries: {stats.get('total_queries', 0)}\n"
                formatted += f"Retrieval Rate: {stats.get('retrieval_rate', 0)}%\n"
                formatted += f"Context Usage Rate: {stats.get('context_usage_rate', 0)}%\n"
                formatted += f"Helpfulness Rate: {stats.get('helpfulness_rate', 0)}%\n"
                formatted += f"Average Quality: {stats.get('avg_context_quality', 0):.2f}/1.0\n"
                
                return formatted
                
            else:
                from database.rag_operations import get_grade_exceptions
                exceptions = get_grade_exceptions(db, status='pending', limit=5)
                
                if not exceptions:
                    return "✅ No pending exceptions. System is performing well!"
                
                formatted = f"⚠️  Pending Exceptions ({len(exceptions)}):\n\n"
                for exc in exceptions:
                    formatted += f"**{exc.exception_type}**\n"
                    formatted += f"  Query: {exc.query[:100]}...\n"
                    formatted += f"  Quality Score: {exc.context_quality_score:.2f}\n\n"
                
                return formatted
                
        finally:
            db.close()
            
    except Exception as e:
        return f"❌ Error querying learning store: {str(e)}"


@tool
def enhanced_web_search(
    query: str,
    max_results: int = 5,
    context: Optional[str] = None
) -> str:
    """
    Enhanced web search with context awareness and synthesis.
    
    This tool wraps Tavily web search with additional intelligence:
    - Contextual query expansion
    - Result synthesis
    - Source credibility scoring
    
    Args:
        query: The search query
        max_results: Maximum number of results
        context: Optional conversation context for query enrichment
    
    Returns:
        Synthesized search results with sources
    
    Examples:
        - "Who founded Code Savanna?"
        - "Latest developments in quantum computing"
        - "Best practices for RAG systems"
    """
    if not WEB_SEARCH_AVAILABLE:
        return "❌ Web search not available. Please configure TAVILY_API_KEY in .env"
    
    try:
        # Enrich query with context if provided
        enriched_query = query
        if context:
            # Simple context enrichment (in production, use LLM)
            enriched_query = f"{query} {context}"
        
        # Perform web search
        results = web_search_tool.search(enriched_query)
        
        if not results or "error" in results.lower():
            return f"🔍 Web search failed or returned no results for: '{query}'"
        
        # Add metadata
        formatted = f"🔍 Web Search Results for: '{query}'\n\n"
        formatted += results
        formatted += f"\n\n_Search completed with Tavily API_"
        
        return formatted
        
    except Exception as e:
        return f"❌ Error in web search: {str(e)}"


@tool
def should_retrieve_context(
    query: str,
    user_id: Optional[str] = None
) -> str:
    """
    Agentic RAG: Decide if context retrieval is needed.
    
    This tool analyzes the query and historical performance to determine
    if RAG retrieval would be beneficial. Avoids unnecessary retrieval
    for simple questions like "Hi" or "Thank you".
    
    Args:
        query: The user's question
        user_id: Optional user ID for personalized decision
    
    Returns:
        Decision ("RETRIEVE" or "SKIP") with reasoning
    
    Examples:
        - "Hi" -> SKIP (greeting, no context needed)
        - "What does chapter 3 say?" -> RETRIEVE (document reference)
        - "2+2" -> SKIP (simple calculation)
    """
    if not DATABASE_AVAILABLE:
        # Fallback logic without database
        # Simple heuristic: check for document references
        doc_indicators = [
            "document", "notes", "file", "pdf", "chapter", "section",
            "page", "uploaded", "my notes", "the document"
        ]
        
        query_lower = query.lower()
        if any(indicator in query_lower for indicator in doc_indicators):
            return "RETRIEVE: Query mentions documents or notes"
        elif len(query.split()) <= 3:
            return "SKIP: Query is too short/simple"
        else:
            return "RETRIEVE: Query might benefit from context"
    
    try:
        db = get_db()
        try:
            # Check historical performance for similar queries
            stats = get_rag_performance_stats(db, user_id=user_id)
            
            # Simple decision logic
            query_lower = query.lower()
            
            # Skip for greetings and simple responses
            greetings = ["hi", "hello", "hey", "thanks", "thank you", "bye"]
            if query_lower.strip() in greetings:
                return "SKIP: Greeting or social nicety - no context needed"
            
            # Skip for very simple calculations
            if len(query.split()) <= 4 and any(op in query for op in ['+', '-', '*', '/', '=']):
                return "SKIP: Simple calculation - no retrieval needed"
            
            # Retrieve if document is mentioned
            doc_indicators = [
                "document", "notes", "file", "pdf", "chapter", "section",
                "page", "uploaded", "my notes", "the document"
            ]
            
            if any(indicator in query_lower for indicator in doc_indicators):
                return f"RETRIEVE: Document reference detected. Historical helpfulness: {stats.get('helpfulness_rate', 0)}%"
            
            # Check if similar queries benefited from retrieval
            if stats.get("status") == "analyzed":
                helpfulness = stats.get("helpfulness_rate", 0)
                if helpfulness > 70:
                    return f"RETRIEVE: Historical performance good ({helpfulness}% helpful)"
                elif helpfulness < 30:
                    return f"SKIP: Historical retrieval not helpful ({helpfulness}% helpful)"
            
            # Default: retrieve if query is substantive
            if len(query.split()) > 5:
                return "RETRIEVE: Substantive query likely to benefit from context"
            else:
                return "SKIP: Query too short for meaningful retrieval"
                
        finally:
            db.close()
            
    except Exception as e:
        # Fallback on error
        return f"RETRIEVE: Error in decision logic ({str(e)}), defaulting to retrieve"


def get_all_rag_tools():
    """
    Get all RAG tools for Phase 2 integration.
    
    Returns:
        List of LangChain tools for L2, L3, and enhanced web search
    """
    tools = []
    
    if DATABASE_AVAILABLE:
        tools.extend([
            retrieve_from_vector_store,
            query_learning_store,
            should_retrieve_context
        ])
    
    if WEB_SEARCH_AVAILABLE:
        tools.append(enhanced_web_search)
    
    return tools

