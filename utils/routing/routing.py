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
    # Animation patterns first (higher priority)
    'render_manim_video': [
        r'\b(animate|animation|visualize|create\s+(a\s+)?video|generate\s+(a\s+)?video)\b',
        r'\b(show\s+(me\s+)?(an?\s+)?animation)\b',
        r'\b(manim|visual\s+explanation)\b',
    ],
    'Python_REPL': [
        # Only match when user wants to EXECUTE code, not when asking HOW to code
        r'\b(calculate|compute|solve)\b.*\d',  # "Calculate 5+3"
        r'\d+\s*[\+\-\*/\^]\s*\d+',            # "2+2" or "5*3"
        r'\b(execute|run|eval)\b.*\b(this|the|following)\b.*\bcode\b',  # "Execute this code"
        r'```python.*```',                     # Code blocks to execute
        r'\b(fibonacci|factorial|prime)\b.*\b(for|of)\b.*\d+',  # "Fibonacci of 10"
    ],
    'Document_QA': [
        # ONLY route to Document_QA when user EXPLICITLY mentions their documents
        # This prevents unwanted document lookups for general questions
        # NOTE: Placed after animation patterns to avoid conflicts
        
        # Explicit document references (but not if asking for animation)
        r'\b(attached|uploaded)\b',
        r'\bmy\b.*\b(notes|documents|files|pdf|material|book)\b',
        r'\b(according to|based on|from|in)\b.*\b(notes|document|pdf|file|material|book|text|content)\b',
        r'\b(my notes|my documents|my files|uploaded files?)\b',
        r'\b(the|my|this|an?) (attached|uploaded)\b.*\b(document|file|pdf|docx)\b',
        r'\b(what does|what do)\b.*\b(the|my|this)\b.*\b(notes|document|pdf|file|material|text|content)\b',
        r'\b(notes|document|file|material|text|content)\b.*\b(say|says|mention|mentions|state|states|explain|explains)\b',
        
        # Chapter/section references (clearly document-related)
        r'\b(chapter|section|page)\b.*\d+',
        r'\b(chapter|section)\b',
        
        # Study material generation from documents
        r'\b(generate|create|make)\b.*(study guide|summar|flashcard|mcq|question|quiz|test).*\b(from|based on|using)\b',
        r'\b(summariz|summar)\b.*\b(chapter|section|my|the)\b',
        
        # Follow-ups explicitly about documents
        r'\b(in|from)\s+(my|the|this)\s+(document|notes|book|material)\b',
    ],
    'Web_Search': [
        # General knowledge questions (when documents are NOT explicitly mentioned)
        r'^\s*(?:what|how|why|explain|describe|define|who|when|where)\b',
        
        # Current/time-sensitive queries
        r'\b(latest|current|recent|news|today|yesterday|this\s+(week|month|year))\b',
        r'\b(2024|2025|2026)\b',
        r'\b(who\s+is|when\s+is|where\s+is)\b.*\b(now|today|currently)\b',
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
    # Combined fetch and grade patterns (highest priority)
    'fetch_and_grade': [
        r'\b(?:grade|evaluate|review|assess|mark|score)\s+(?:this\s+)?(?:submission|assignment|work|student\s+work)\b',
        r'\b(?:grade|evaluate|review|assess|mark|score)\s+(?:the\s+)?(?:submission|assignment|work|student\s+work)\b',
        r'\b(?:submission|assignment|work|student\s+work)\s+(?:grade|evaluation|review|assessment|marking|scoring)\b',
        r'\bgrade\s+this\s+submission\b',
        r'\bevaluate\s+this\s+assignment\b',
        r'\breview\s+this\s+work\b',
        r'\bgrade\s+this\s+submission\s+using\s+the\s+computer\s+science\s+intro\s+rubric\b',
        r'\breview\s+the\s+code\s+quality\s+and\s+provide\s+feedback\b',
    ],
    'review_code': [
        r'\b(review|grade|evaluate)\b.*\b(code|program|script)\b',
        r'\b(code|program)\b.*\b(review|grade|grading)\b',
        r'\b(python|java|c\+\+|javascript)\b.*\b(code|program)\b',
        r'\bdef\s+\w+\(|\bclass\s+\w+|\bfunction\s+\w+',
        r'```(python|java|javascript|c\+\+)',  # Code blocks
    ],
    'grade_essay': [
        r'\b(grade|evaluate)\b.*\b(essay|paper|report|writing)\b',  # Removed "assignment" to avoid false matches
        r'\b(essay|paper|report)\b.*\b(grade|grading|evaluation)\b',
        r'\bgrade\s+(this|an?|the)\s+(essay|paper|report)\b',
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
    # Google Classroom Tools
    'fetch_classroom_courses': [
        r'\b(show|list|get|fetch|display)\b.*(my\s+)?(google\s+)?classroom\s+courses?\b',
        r'\bgoogle\s+classroom\s+courses?\b',
        r'\bclassroom\s+courses?\b.*\b(show|list|get)\b',
    ],
    'fetch_submission_content': [
        r'\b(get|fetch|extract|read)\b.*\b(submission\s+content|file\s+content|document\s+content)\b',
        r'\bsubmission\s+content\b.*\b(for|from)\b',
        r'\bfetch_submission_content\b',
        r'\bget\s+content\s+from\s+submission\b',
        r'\bread\s+submission\s+files\b',
        r'\bextract\s+submission\s+content\b',
        r'\bget\s+content\s+from\b.*\bsubmission\b',
        r'\bcontent\s+from\s+submission\b',
    ],
    'fetch_classroom_submissions': [
        r'\bget\s+submissions?\b.*\bcourse\b',
        r'\bshow\s+me\s+submissions?\b',
        r'\bfetch_classroom_submissions\b',
        r'\bsubmissions?\s+for\s+(assignment|coursework)\b',
        r'\b(show|list|get|fetch)\b.*\b(student\s+)?submissions?\b.*\b(course|assignment)\b',
        r'\bstudent\s+submissions?\b',
    ],
    'fetch_classroom_assignments': [
        r'\b(show|list|get|fetch)\b.*classroom\s+assignments?\b',
        r'\bclassroom\s+assignments?\b.*\b(show|list|get)\b',
        r'\bassignments?\s+from\s+course\b',
        r'\b(show|list|get|fetch)\b.*\bassignments?\s+from\s+course\b',
        r'\bcourse\s+\d+.*\bassignments?\b',
    ],
    # Lesson Planning Tools (for teachers/professors)
    'generate_lesson_plan': [
        r'\b(create|generate|make|design|write)\b.*\b(lesson\s+plan)\b',
        r'\blesson\s+plan\b.*\b(for|about|on)\b',
        r'\bplan\s+(a|the)\s+lesson\b',
    ],
    'design_curriculum': [
        r'\b(create|design|develop)\b.*\b(curriculum|syllabus|course\s+plan)\b',
        r'\b(curriculum|syllabus)\b.*\b(for|design)\b',
        r'\b(semester|course)\s+(plan|outline)\b',
    ],
    'create_learning_objectives': [
        r'\b(create|write|develop)\b.*\b(learning\s+objectives?|learning\s+outcomes?)\b',
        r'\blearning\s+objectives?\b.*\b(for|about)\b',
        r'\bbloom.?s\s+taxonomy\b',
    ],
    'design_assessment': [
        r'\b(create|design|make|generate)\b.*\b(quiz|test|exam|assessment)\b',
        r'\b(quiz|test|exam)\b.*\b(for|about|on)\b',
        r'\bdesign\s+(an?\s+)?(quiz|test|exam|assessment)\b',
    ],
    'generate_study_materials': [
        r'\b(create|generate|make)\b.*\b(handout|worksheet|study\s+guide|material)\b',
        r'\b(handout|worksheet|study\s+guide)\b.*\b(for|about|on)\b',
        r'\bmake\s+(a|an)\s+(handout|worksheet)\b',
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
        # Google Classroom patterns
        r'\b(google\s+)?classroom\b.*(courses?|assignments?|submissions?|rubrics?)\b',
        r'\b(show|list|get|fetch)\b.*(my\s+)?(google\s+)?classroom\b',
        r'\bpost\s+grade\s+to\s+classroom\b',
        r'\bassignments?\s+from\s+course\b',
        r'\bcourse\s+\d+',
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

