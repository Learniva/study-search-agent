"""
Query enrichment utilities for improving search quality.

Handles context-aware query expansion for follow-up questions
and vague queries that need enrichment from conversation history.
"""

import re
from typing import List, Tuple
from langchain_core.messages import HumanMessage

from utils.core.constants import (
    VAGUE_QUESTION_PATTERNS,
    FOLLOW_UP_PRONOUNS,
    GENERIC_SUBJECTS,
    MAX_SHORT_QUESTION_WORDS,
    REALTIME_QUERY_PATTERNS,
    QUERY_ENRICHMENT_SYSTEM_PROMPT
)


def detect_realtime_query(question: str) -> bool:
    """
    Detect if query is asking for real-time information.
    
    Real-time queries may get stale cached data from web search.
    
    Args:
        question: User's question
        
    Returns:
        True if query is asking for real-time data
    """
    question_lower = question.lower()
    return any(re.search(pattern, question_lower) for pattern in REALTIME_QUERY_PATTERNS)


def needs_query_enrichment(
    question: str,
    context_messages: List
) -> Tuple[bool, List[str]]:
    """
    Determine if query needs enrichment from conversation context.
    
    Enrichment is needed for:
    - Vague questions ("how does it work?")
    - Questions with pronouns without context
    - Generic subjects without specification
    - Short follow-up questions
    
    Args:
        question: User's question
        context_messages: Previous conversation messages
        
    Returns:
        Tuple of (needs_enrichment, reasons)
    """
    if not context_messages:
        return False, []
    
    question_lower = question.lower()
    reasons = []
    
    # Check for vague patterns
    is_vague = any(question_lower.startswith(pattern) for pattern in VAGUE_QUESTION_PATTERNS)
    if is_vague:
        reasons.append("vague pattern")
    
    # Check for pronouns
    has_pronoun = any(word in question_lower for word in FOLLOW_UP_PRONOUNS)
    if has_pronoun:
        reasons.append("has pronoun")
    
    # Check for generic subjects
    has_generic_subject = any(subject in question_lower for subject in GENERIC_SUBJECTS)
    if has_generic_subject:
        reasons.append("generic subject")
    
    # Check if question is short
    is_short = len(question.split()) <= MAX_SHORT_QUESTION_WORDS
    
    # Need enrichment if vague/pronoun/generic AND short AND have context
    needs_enrichment = (is_vague or has_pronoun or has_generic_subject) and is_short
    
    return needs_enrichment, reasons


def enrich_query_with_context(
    question: str,
    context_messages: List,
    llm
) -> str:
    """
    Enrich a vague follow-up question with conversation context.
    
    Uses LLM to expand the question into a complete, standalone query
    by incorporating relevant information from conversation history.
    
    Args:
        question: Original vague question
        context_messages: Previous conversation messages
        llm: Language model to use for enrichment
        
    Returns:
        Enriched query string
    """
    from langchain_core.messages import SystemMessage, HumanMessage as HM
    
    # Build context text from messages
    context_text = "\n".join([
        f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content[:200]}"
        for msg in context_messages
    ])
    
    # Build enrichment prompt
    enrichment_user = f"""Conversation History:
{context_text}

Follow-up Question: {question}

Expanded search query:"""
    
    # Get enriched query from LLM
    messages = [
        SystemMessage(content=QUERY_ENRICHMENT_SYSTEM_PROMPT),
        HM(content=enrichment_user)
    ]
    
    response = llm.invoke(messages)
    enriched_query = response.content.strip()
    
    return enriched_query


def format_realtime_warning(actual_time_str: str) -> str:
    """
    Format warning message for real-time queries.
    
    Args:
        actual_time_str: Current system time as string
        
    Returns:
        Formatted warning message
    """
    warning = "\n\n⚠️ **IMPORTANT DATA QUALITY WARNING:**\n"
    warning += "Web search may return STALE/CACHED data for real-time queries!\n\n"
    warning += f"**Your actual system time:** {actual_time_str}\n\n"
    warning += "❗ The information above from web search may be OUTDATED.\n"
    warning += "💡 For accurate real-time data (time, weather, stocks), use:\n"
    warning += "   - Dedicated time/weather APIs\n"
    warning += "   - Python datetime commands\n"
    warning += "   - System commands (`date`, `curl wttr.in`, etc.)"
    
    return warning

