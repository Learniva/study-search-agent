"""
Shared routing utilities for the Multi-Agent System.

Provides pattern-based routing optimization to reduce LLM calls by 80-90%.
Used by both Study Agent and Grading Agent for fast tool selection.
"""

import re
from typing import Optional, Dict, List


def pattern_based_route(question: str, patterns: Dict[str, List[str]]) -> Optional[str]:
    """
    Route query based on regex patterns (no LLM call).
    
    OPTIMIZATION: Eliminates 80-90% of routing LLM calls by using regex patterns.
    Falls back to LLM for ambiguous cases.
    
    Args:
        question: User's question
        patterns: Dictionary mapping tool names to list of regex patterns
        
    Returns:
        Tool name if pattern matches, None to fall back to LLM
    """
    q = question.lower()
    
    # Check each tool's patterns
    for tool, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, q):
                print(f"⚡ Pattern-based routing: {tool} (no LLM call)")
                return tool
    
    # No pattern matched - fall back to LLM
    return None


# =============================================================================
# STUDY AGENT PATTERNS
# =============================================================================

STUDY_AGENT_PATTERNS = {
    'Document_QA': [
        # PRIORITY: Most flexible patterns first (allows ANY words in between)
        # "my <anything> notes/document" - e.g., "my deep learning notes", "my AI document"
        r'\bmy\b.*\b(notes|documents|files|pdf|material|book)\b',
        # "according to/based on/from/in + the/my + <anything> + notes/document"
        # e.g., "according to the deep learning notes", "from my AI pdf"
        r'\b(according to|based on|from|in)\b.*\b(the|my|this|these)\b.*\b(notes|document|pdf|file|material|book|text|content)\b',
        # Chapter references (e.g., "chapter 1", "chapter 5 of deep learning")
        # These likely refer to uploaded documents
        r'\b(chapter|section|page)\s+\d+\b',
        r'\b(generate|create|make)\b.*(study guide|summary|flashcards|mcq|questions)\b.*(chapter|section)\s+\d+',
        # Study material generation (likely from uploaded docs if specific topic mentioned)
        r'\b(generate|create|make)\b.*(study guide|summary|flashcards|mcq|questions)\b.*(for|about|on)\b.*(deep learning|machine learning|code savanna)',
        # Direct references to documents
        r'\b(my notes|my documents|my files|uploaded files?)\b',
        r'\b(the|my|this) (attached|uploaded)\b.*\b(document|file|pdf|docx)\b',
        # Questions about what documents say/contain
        r'\b(what does|what do)\b.*\b(the|my|this)\b.*\b(notes|document|pdf|file|material|text|content)\b',
        r'\b(notes|document|file|material|text|content)\b.*\b(say|says|mention|mentions|state|states|explain|explains)\b',
        # Specific document names (customize based on your documents)
        r'\b(deep learning|code savanna|machine learning)\b.*\b(notes|document|material|pdf|book)\b',
        # "from/in/based on/according to" + "attached/uploaded"
        r'\b(from|in|based on|according to)\b.*\b(attached|uploaded)\b',
    ],
    'Python_REPL': [
        r'\b(calculate|compute|solve)\b.*\d',
        r'\d+\s*[\+\-\*/\^]\s*\d+',
        r'\b(python|execute|run|eval)\b.*\bcode\b',
        r'\b(fibonacci|factorial|prime)\b',
    ],
    'render_manim_video': [
        r'\b(animate|animation|visualize|create\s+(a\s+)?video)\b',
        r'\b(show\s+(me\s+)?(an?\s+)?animation)\b',
        r'\b(manim|visual\s+explanation)\b',
    ],
    'Web_Search': [
        r'^\s*(what|who|when|where|why|how|explain|tell\s+me)\b',
        r'\b(latest|current|recent|news|today|this\s+(week|month|year))\b',
        r'\b(what\s+is|who\s+is|when\s+is|where\s+is)\b',
        r'\b(define|definition|meaning\s+of)\b',
    ],
}


def fast_study_route(question: str) -> Optional[str]:
    """
    Fast pattern-based routing for study agent.
    
    Args:
        question: User's question
        
    Returns:
        Tool name if pattern matches, None for LLM routing
    """
    return pattern_based_route(question, STUDY_AGENT_PATTERNS)


# =============================================================================
# GRADING AGENT PATTERNS
# =============================================================================

GRADING_AGENT_PATTERNS = {
    'grade_essay': [
        r'\b(grade|evaluate)\b.*\b(essay|paper|report|assignment|writing)\b',
        r'\b(essay|paper|report)\b.*\b(grade|grading|evaluation)\b',
        r'\bgrade\s+(this|an?|the)\s+(essay|paper|report)\b',
    ],
    'review_code': [
        r'\b(review|grade|evaluate)\b.*\b(code|program|script)\b',
        r'\b(code|program)\b.*\b(review|grade|grading)\b',
        r'\b(python|java|c\+\+|javascript)\b.*\b(code|program)\b',
        r'\bdef\s+\w+\(|\bclass\s+\w+|\bfunction\s+\w+',
    ],
    'grade_mcq': [
        r'\b(mcq|multiple\s*choice|quiz)\b.*\b(grade|grading|score)\b',
        r'\b(student|correct)\s*(answers?|responses?)\b',
        r'\b(grade|score)\b.*\b(mcq|quiz|test)\b',
    ],
    'generate_feedback': [
        r'\b(feedback|comments?)\b.*\b(only|without\s+grade)\b',
        r'\bprovide\s+feedback\b',
        r'\bgive\s+feedback\b',
    ],
}


def fast_grading_route(question: str) -> Optional[str]:
    """
    Fast pattern-based routing for grading agent.
    
    Args:
        question: User's grading request
        
    Returns:
        Tool name if pattern matches, None for LLM routing
    """
    return pattern_based_route(question, GRADING_AGENT_PATTERNS)


# =============================================================================
# SUPERVISOR AGENT PATTERNS
# =============================================================================

SUPERVISOR_INTENT_PATTERNS = {
    'GRADE': [
        r'\b(grade|grading|evaluate|review)\b.*(essay|paper|code|assignment|submission)\b',
        r'\b(essay|paper|code|assignment)\b.*(grade|grading|evaluate)\b',
        r'\bgive\s+(a\s+)?grade\b',
        r'\bprovide\s+feedback\s+on\b',
        r'\b(score|mark)\b.*(essay|paper|assignment)\b',
    ],
    'STUDY': [
        r'^\s*(what|who|when|where|why|how|explain|tell\s+me)\b',
        r'\b(learn|study|understand|research)\b',
        r'\b(animate|visualize|create\s+animation)\b',
        r'\b(calculate|compute|solve)\b.*\d',
        r'\b(summarize|summary|study\s+guide|flashcards?|mcq)\b',
    ],
}


def fast_intent_classification(question: str) -> Optional[str]:
    """
    Fast pattern-based intent classification for supervisor.
    
    Args:
        question: User's request
        
    Returns:
        Intent ("STUDY" or "GRADE") if pattern matches, None for LLM classification
    """
    result = pattern_based_route(question, SUPERVISOR_INTENT_PATTERNS)
    
    if result:
        print(f"⚡ Pattern-based intent: {result} (no LLM call)")
    
    return result


# =============================================================================
# SIMILARITY UTILITIES
# =============================================================================

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple word-based similarity between two texts.
    
    Uses Jaccard similarity: intersection / union of word sets
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score from 0 to 1
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


def find_similar_queries(
    query: str,
    history: List[Dict],
    threshold: float = 0.6,
    max_results: int = 5
) -> List[Dict]:
    """
    Find similar queries in history.
    
    Args:
        query: Current query
        history: List of historical queries with metadata
        threshold: Minimum similarity threshold (0-1)
        max_results: Maximum similar queries to return
        
    Returns:
        List of similar queries with similarity scores
    """
    query_lower = query.lower()
    similar = []
    
    for entry in history:
        similarity = calculate_text_similarity(query_lower, entry.get("question", "").lower())
        
        if similarity >= threshold:
            similar.append({
                **entry,
                'similarity': similarity
            })
    
    # Sort by similarity (highest first)
    similar.sort(key=lambda x: x['similarity'], reverse=True)
    
    return similar[:max_results]

