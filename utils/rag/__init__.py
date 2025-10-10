"""
RAG Utilities Package

RAG-specific utilities for context management and query enrichment:
- context: Conversation context management (token-aware)
- query_enrichment: Query expansion for vague/follow-up questions
"""

from .context import (
    get_smart_context,
    estimate_tokens,
    truncate_to_tokens,
    format_conversation_history,
    get_context_summary,
)

from .query_enrichment import (
    detect_realtime_query,
    needs_query_enrichment,
    enrich_query_with_context,
    format_realtime_warning,
)

__all__ = [
    # Context management
    'get_smart_context',
    'estimate_tokens',
    'truncate_to_tokens',
    'format_conversation_history',
    'get_context_summary',
    
    # Query enrichment
    'detect_realtime_query',
    'needs_query_enrichment',
    'enrich_query_with_context',
    'format_realtime_warning',
]

