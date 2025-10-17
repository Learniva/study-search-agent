"""
Phase 2: RAG Tools for Agentic Self-Correction

Tools for:
- L2 Vector Store (pgvector) - Semantic document retrieval
- L3 Learning Store (PostgreSQL) - Query learned patterns and exceptions
- Web Search (Google/Tavily) - Enhanced with context awareness and fallback

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
        print("⚠️  RAG Tools: Web search not configured (Google Custom Search or Tavily API key missing)")
except ImportError as e:
    WEB_SEARCH_AVAILABLE = False
    print(f"⚠️  RAG Tools: Web search not available ({e})")


def _extract_topic_from_document_context(conversation_history: Optional[str] = None) -> str:
    """
    Extract main topic from conversation history for document QA.
    Similar to web search but optimized for document queries.
    """
    if not conversation_history:
        return ""
    
    import re
    
    # Strategy 1: Look for document references in recent messages
    # "What does chapter 12 say?" → extract "chapter 12"
    patterns = [
        (r'(?:chapter|ch\.?)\s*(\d+)', lambda m: f"chapter {m.group(1)}"),
        (r'(?:section|sec\.?)\s*(\d+(?:\.\d+)?)', lambda m: f"section {m.group(1)}"),
        (r'(?:page|p\.?)\s*(\d+)', lambda m: f"page {m.group(1)}"),
        (r'what\s+(?:is|are)\s+(?:a|an|the)?\s*([^?,.!]+?)(?:\?|$)', lambda m: m.group(1).strip()),
        (r'tell\s+me\s+about\s+([^?,.!]+)', lambda m: m.group(1).strip()),
        (r'explain\s+(?:the\s+)?([^?,.!]+)', lambda m: m.group(1).strip()),
    ]
    
    for pattern, extractor in patterns:
        match = re.search(pattern, conversation_history.lower())
        if match:
            topic = extractor(match)
            if len(topic) > 3:  # Valid topic
                return topic.strip(' ,.!?:;')
    
    return ""


def _reformulate_document_query(query: str, extracted_topic: str) -> str:
    """
    Intelligently reformulate document queries based on context.
    Handles pronouns and contextual references for document QA.
    """
    import re
    query_lower = query.lower()
    
    # Document-specific reformulation patterns
    doc_patterns = [
        # Chapter/Section queries with pronouns
        (r'what\s+(?:is|are)\s+(?:it|this|that)\s+about', f"what is {extracted_topic} about"),
        (r'what\s+does\s+(?:it|this|that)\s+say', f"what does {extracted_topic} say"),
        (r'what\s+does\s+(?:it|this|that)\s+cover', f"what does {extracted_topic} cover"),
        (r'what\s+(?:is|are)\s+(?:the\s+)?(?:main|key)\s+(?:points|topics|ideas)', f"main points in {extracted_topic}"),
        
        # Summary queries
        (r'summarize\s+(?:it|this|that)', f"summarize {extracted_topic}"),
        (r'give\s+me\s+a\s+summary', f"summary of {extracted_topic}"),
        
        # Content queries
        (r'what\s+(?:topics|subjects)\s+(?:does\s+)?(?:it|this|that)\s+discuss', f"topics in {extracted_topic}"),
        (r'what\s+information\s+(?:does\s+)?(?:it|this|that)\s+(?:have|contain)', f"information in {extracted_topic}"),
        
        # Specific entity queries
        (r'what\s+companies\s+(?:does\s+)?(?:it|this|that)\s+mention', f"companies mentioned in {extracted_topic}"),
        (r'what\s+(?:people|authors|researchers)\s+(?:does\s+)?(?:it|this|that)\s+mention', f"people mentioned in {extracted_topic}"),
        (r'what\s+examples\s+(?:does\s+)?(?:it|this|that)\s+(?:give|provide)', f"examples in {extracted_topic}"),
    ]
    
    # Try each pattern
    for pattern, replacement in doc_patterns:
        if re.search(pattern, query_lower):
            print(f"🔍 [DOC QA] Reformulated: '{query}' → '{replacement}'")
            return replacement
    
    # Generic pronoun replacement for document queries
    pronouns = ['it', 'this', 'that', 'them', 'these', 'those']
    for pronoun in pronouns:
        if f' {pronoun} ' in f' {query_lower} ':
            reformulated = re.sub(rf'\b{pronoun}\b', extracted_topic, query, flags=re.IGNORECASE)
            print(f"🔍 [DOC QA] Pronoun replaced: '{query}' → '{reformulated}'")
            return reformulated
    
    # If query contains chapter/section but is vague, add context
    if any(word in query_lower for word in ['chapter', 'section', 'page']) and len(query.split()) <= 5:
        enhanced = f"{query} content and main topics"
        print(f"🔍 [DOC QA] Enhanced vague query: '{query}' → '{enhanced}'")
        return enhanced
    
    return query


@tool("Document_QA")
def retrieve_from_vector_store(
    query: str,
    limit: int = 15,  # Increased default for better coverage
    user_id: Optional[str] = None,
    course_id: Optional[str] = None,
    conversation_history: Optional[str] = None  # NEW: For context-aware queries
) -> str:
    """
    Retrieve relevant documents from L2 Vector Store (pgvector) with INTELLIGENT CONTEXT AWARENESS.
    
    This tool performs semantic similarity search on uploaded documents using pgvector,
    with advanced query reformulation for natural follow-up questions.
    
    🧠 Context-Aware Features:
    - Extracts topic from conversation history
    - Handles pronouns (it, this, that, them)
    - Reformulates vague follow-up questions
    - Understands chapter/section references
    
    Args:
        query: The search query
        limit: Maximum number of results (default: 15)
        user_id: Filter by user ID
        course_id: Filter by course ID
        conversation_history: Recent conversation for context extraction
    
    Returns:
        Formatted string with relevant document chunks
    
    Examples:
        Direct queries:
        - "What does chapter 3 say about machine learning?"
        - "Find information about neural networks in my notes"
        
        Follow-up queries (context-aware):
        - "What is it about?" → "What is chapter 3 about?"
        - "What companies does it mention?" → "companies mentioned in chapter 3"
        - "Summarize it" → "summarize chapter 3"
    """
    if not DATABASE_AVAILABLE:
        return "❌ Vector store not available. Database not configured. Please set DATABASE_URL in .env"
    
    # INTELLIGENT CONTEXT-AWARE QUERY REFORMULATION
    original_query = query
    has_pronoun = any(f' {word} ' in f' {query.lower()} ' for word in ['it', 'this', 'that', 'them', 'these', 'those'])
    is_vague = len(query.split()) <= 5 and has_pronoun
    
    print(f"\n{'='*70}")
    print(f"🔍 INTELLIGENT DOCUMENT QA")
    print(f"{'='*70}")
    print(f"📝 Original query: '{query}'")
    print(f"🎯 Has pronoun: {has_pronoun}, Is vague: {is_vague}")
    
    if (has_pronoun or is_vague) and conversation_history:
        # Extract topic from conversation history
        extracted_topic = _extract_topic_from_document_context(conversation_history)
        
        if extracted_topic:
            print(f"💡 Extracted topic: '{extracted_topic}'")
            # Reformulate query with context
            query = _reformulate_document_query(query, extracted_topic)
            print(f"✨ Reformulated query: '{query}'")
        else:
            print(f"⚠️  No topic extracted from conversation history")
    else:
        print(f"✅ Direct question - no reformulation needed")
    
    print(f"{'='*70}\n")
    
    try:
        # First, check if any documents exist in the vector store
        with get_db() as db:
            from sqlalchemy import text
            count_result = db.execute(text("SELECT COUNT(*) as count FROM document_vectors"))
            total_docs = count_result.fetchone().count
            
            if total_docs == 0:
                return "📚 No documents found in the vector store. Please upload documents first, or I can search the web for this information instead."
        
    except Exception as e:
        print(f"⚠️  Error checking document availability: {e}")
        # Continue to try retrieval anyway
    
    try:
        # Preprocess query: Extract core question for better semantic matching
        # "What is AI based on my deep learning notes?" -> "what is artificial intelligence definition"
        import re
        query_lower = query.lower()
        
        # Detect chapter/section references for targeted retrieval
        chapter_match = re.search(r'\b(?:chapter|ch\.?)\s*(\d+)', query_lower)
        section_match = re.search(r'\b(?:section|sec\.?)\s*(\d+(?:\.\d+)?)', query_lower)
        page_match = re.search(r'\b(?:page|p\.?)\s*(\d+)', query_lower)
        
        # CRITICAL FIX: If user asks for a specific chapter, use HYBRID search
        # Semantic search alone fails to retrieve the right chapter
        if chapter_match:
            chapter_num = chapter_match.group(1)
            print(f"🔍 [HYBRID SEARCH] User requested Chapter {chapter_num} - using keyword + semantic hybrid search")
        
        # Remove filler phrases using word boundaries to avoid breaking words
        query_clean = query_lower
        filler_phrases = [
            r'\bbased on\b',
            r'\baccording to\b', 
            r'\bfrom my\b',
            r'\bin my\b',
            r'\bmy notes\b',
            r'\bmy documents\b',
            r'\bthe document\b',
            r'\bthe file\b',
            r'\battached\b',
            r'\buploaded\b'
        ]
        
        for pattern in filler_phrases:
            query_clean = re.sub(pattern, ' ', query_clean)
        
        # Add context boosters for better matching
        if any(word in query_clean for word in ['what is', 'define', 'explain']):
            query_clean += ' definition explanation meaning'
        
        # Boost chapter/section references in the query
        if chapter_match:
            query_clean += f' chapter {chapter_match.group(1)}'
        if section_match:
            query_clean += f' section {section_match.group(1)}'
        
        # Clean up extra spaces
        query_clean = re.sub(r'\s+', ' ', query_clean).strip()
        
        # Generate 768D query embedding using Google Gemini
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        
        query_result = genai.embed_content(
            model="models/embedding-001",
            content=query_clean,  # Use cleaned query for better matching
            task_type="retrieval_query"  # Query task type for search
        )
        query_embedding = query_result['embedding']
        
        with get_db() as db:
            # Perform pgvector similarity search with 768D embeddings
            from sqlalchemy import text
            
            # Convert embedding to PostgreSQL array format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Build SQL query with user/course filters
            filters = []
            filter_sql = ""
            
            if user_id:
                filters.append(f"user_id = '{user_id}'")
            if course_id:
                filters.append(f"course_id = '{course_id}'")
            
            # HYBRID SEARCH: Add chapter filter for chapter-specific queries
            if chapter_match:
                chapter_num = chapter_match.group(1)
                # Filter for chunks that contain the chapter number
                filters.append(f"(LOWER(content) LIKE '%chapter {chapter_num}%' OR LOWER(content) LIKE '%chapter{chapter_num}%')")
                print(f"🔍 [HYBRID SEARCH] Added keyword filter for Chapter {chapter_num}")
            
            if filters:
                filter_sql = " AND " + " AND ".join(filters)
            
            # Use pgvector's <=> operator for cosine distance (lower = more similar)
            # Retrieve more chunks initially for re-ranking
            # For chapter-specific requests, retrieve even more to ensure comprehensive coverage
            if chapter_match or section_match:
                initial_limit = limit * 5  # 5x for chapter/section requests (e.g., 75 chunks)
            else:
                initial_limit = limit * 3  # 3x for general requests (e.g., 45 chunks)
            
            sql = f"""
                SELECT 
                    id, document_name, content, relevance_score, retrieval_count,
                    (embedding <=> '{embedding_str}'::vector) as distance
                FROM document_vectors
                WHERE 1=1 {filter_sql}
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT {initial_limit}
            """
            
            result = db.execute(text(sql))
            results = result.fetchall()
            
            print(f"📊 [RETRIEVAL DEBUG] Retrieved {len(results)} chunks from vector search")
            if results and len(results) > 0:
                print(f"📊 [RETRIEVAL DEBUG] Sample of first 5 chunks:")
                for i, row in enumerate(results[:5]):
                    try:
                        content_preview = str(row[2])[:150] if len(row) > 2 and row[2] else "No content"
                        distance = row[5] if len(row) > 5 else "N/A"
                        print(f"   {i+1}. Dist={distance}: {content_preview}...")
                    except Exception as e:
                        print(f"   {i+1}. Error: {e}")
                
                # Check if Chapter 12 is in ANY of the retrieved chunks
                if chapter_match:
                    chapter_num = chapter_match.group(1)
                    found_chapter = False
                    for i, row in enumerate(results):
                        if len(row) > 2 and row[2] and f"chapter {chapter_num}" in str(row[2]).lower():
                            found_chapter = True
                            print(f"✅ [RETRIEVAL DEBUG] Chapter {chapter_num} found at position {i+1}/{len(results)}")
                            break
                    if not found_chapter:
                        print(f"❌ [RETRIEVAL DEBUG] Chapter {chapter_num} NOT in top {len(results)} chunks!")
                        print(f"   This means semantic search completely missed the target chapter.")
            
            if not results:
                return f"📚 No relevant documents found for query: '{query}'\n\nTip: Make sure documents are uploaded and indexed in the vector store."
            
            # Re-rank results: boost chunks with definition keywords
            # This solves the problem where concise definitions rank lower than verbose content
            definition_keywords = ['definition', 'defined as', 'can be described as', 'refers to', 
                                   'is the', 'means', 'is a', 'describes', 'characterized by']
            
            def calculate_relevance_boost(content: str) -> float:
                """Calculate relevance boost based on content quality indicators."""
                content_lower = content.lower()
                boost = 0.0
                
                # PRIORITY: Boost chunks from requested chapter/section (CRITICAL signal)
                if chapter_match:
                    chapter_num = chapter_match.group(1)
                    # Check if this chunk is from the requested chapter
                    if re.search(rf'\b(?:chapter|ch\.?)\s*{chapter_num}\b', content_lower):
                        boost += 5.0  # MASSIVE boost for matching chapter (overrides semantic similarity)
                    # Also check for page markers that indicate chapter start
                    # e.g., "Chapter 9: Advanced architectures"
                    if re.search(rf'chapter\s*{chapter_num}:', content_lower):
                        boost += 6.0  # Even stronger for chapter titles
                    
                    # Boost chunks with [Page X] markers when chapter is specified
                    # These are likely substantive content from the chapter
                    # (not all chunks say "Chapter 9", but chapter pages are continuous)
                    if re.search(r'\[page\s+\d+\]', content_lower):
                        # Additional boost if the chunk has substantive content indicators
                        # (works for technical, humanities, and general academic content)
                        substantive_indicators = [
                            'figure', 'table', 'example', 'definition', 'theorem', 'proof',
                            'equation', 'formula', 'algorithm', 'listing', 'diagram',
                            'important', 'key point', 'note that', 'observe that',
                            'consider', 'recall', 'remember', 'analysis', 'argument',
                            'evidence', 'conclusion', 'however', 'therefore', 'thus',
                            'event', 'period', 'century', 'era', 'movement'
                        ]
                        if any(indicator in content_lower for indicator in substantive_indicators):
                            boost += 0.25  # Boost for substantive content with page marker
                
                if section_match:
                    section_num = section_match.group(1)
                    if re.search(rf'\b(?:section|sec\.?)\s*{section_num}\b', content_lower):
                        boost += 0.40
                
                if page_match:
                    page_num = page_match.group(1)
                    if re.search(rf'\[page\s*{page_num}\]', content_lower):
                        boost += 0.30
                
                # Boost for definition phrases (strong signal)
                for keyword in definition_keywords:
                    if keyword in content_lower:
                        boost += 0.15
                
                # Penalize table of contents / meta content (unless it's the requested chapter)
                meta_indicators = ['table of contents', 'page numbers', 'index']
                for indicator in meta_indicators:
                    if indicator in content_lower and not chapter_match:
                        boost -= 0.10
                
                return boost
            
            # Apply re-ranking
            results_with_boost = []
            for doc in results:
                boost = calculate_relevance_boost(doc.content)
                adjusted_similarity = (1 - doc.distance) + boost
                results_with_boost.append((doc, adjusted_similarity))
            
            # Sort by adjusted similarity
            results_with_boost.sort(key=lambda x: x[1], reverse=True)
            
            # Take top results after re-ranking
            results = [doc for doc, _ in results_with_boost[:limit]]
            
            # Format results for LLM synthesis (clean, minimal format)
            # Group by document for cleaner citations
            from collections import defaultdict
            docs_by_name = defaultdict(list)
            for doc in results:
                docs_by_name[doc.document_name].append(doc.content)
            
            formatted_results = "Retrieved information from your documents:\n\n"
            
            for doc_name, contents in docs_by_name.items():
                formatted_results += f"From: {doc_name}\n"
                formatted_results += f"{'─' * 80}\n"
                for content in contents:
                    # Extract page numbers from content if present
                    import re
                    page_match = re.search(r'\[Page (\d+)\]', content)
                    
                    # Clean content (remove page markers for cleaner display)
                    clean_content = re.sub(r'\[Page \d+\]', '', content).strip()
                    
                    if page_match:
                        formatted_results += f"{clean_content} [Page {page_match.group(1)}]\n\n"
                    else:
                        formatted_results += f"{clean_content}\n\n"
                
                formatted_results += f"{'─' * 80}\n\n"
            
            # Update retrieval stats
            for doc in results:
                db.execute(
                    text("UPDATE document_vectors SET retrieval_count = retrieval_count + 1 WHERE id = :id"),
                    {'id': doc.id}
                )
            db.commit()
            
            return formatted_results
            
    except Exception as e:
        import traceback
        return f"❌ Error retrieving from vector store: {str(e)}\n{traceback.format_exc()}"


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
    
    This tool wraps web search (Google Custom Search with Tavily fallback) with additional intelligence:
    - Contextual query expansion
    - Result synthesis
    - Source credibility scoring
    - Automatic fallback if primary fails
    
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
        return "❌ Web search not available. Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID, or TAVILY_API_KEY in .env"
    
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
        formatted += f"\n\n_Search completed (Google Custom Search with Tavily fallback)_"
        
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

