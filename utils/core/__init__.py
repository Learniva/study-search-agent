"""
Core Utilities Package

Essential system utilities used throughout the application:
- llm: LLM initialization and configuration
- constants: System-wide constants and configuration
- cache: Result caching with TTL
"""

# Commenting out LLM imports to avoid langchain dependencies for auth-only operations
# from .llm import initialize_llm, initialize_grading_llm, DEFAULT_MODEL, TEMPERATURE_SETTINGS
from .constants import (
    DEFAULT_CACHE_TTL,
    MAX_CONTEXT_TOKENS,
    MAX_AGENT_ITERATIONS,
    MAX_GRADING_ITERATIONS,
    VAGUE_QUESTION_PATTERNS,
    FOLLOW_UP_PRONOUNS,
    GENERIC_SUBJECTS,
    REALTIME_QUERY_PATTERNS,
    GRADING_ERROR_INDICATORS,
    GRADING_UNCERTAINTY_INDICATORS
)
from .cache import ResultCache

__all__ = [
    # LLM (commented out to avoid langchain dependencies)
    # "initialize_llm",
    # "initialize_grading_llm",
    # "DEFAULT_MODEL", 
    # "TEMPERATURE_SETTINGS",
    
    # Cache
    "ResultCache",
    
    # Constants (explicitly exported)
    "DEFAULT_CACHE_TTL",
    "MAX_CONTEXT_TOKENS",
    "MAX_AGENT_ITERATIONS",
    "MAX_GRADING_ITERATIONS",
    "VAGUE_QUESTION_PATTERNS",
    "FOLLOW_UP_PRONOUNS",
    "GENERIC_SUBJECTS",
    "REALTIME_QUERY_PATTERNS",
    "GRADING_ERROR_INDICATORS",
    "GRADING_UNCERTAINTY_INDICATORS",
]

