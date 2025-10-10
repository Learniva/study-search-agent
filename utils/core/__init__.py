"""
Core Utilities Package

Essential system utilities used throughout the application:
- llm: LLM initialization and configuration
- constants: System-wide constants and configuration
- cache: Result caching with TTL
"""

from .llm import initialize_llm, initialize_grading_llm, DEFAULT_MODEL, TEMPERATURE_SETTINGS
from .constants import *
from .cache import ResultCache

__all__ = [
    # LLM
    'initialize_llm',
    'initialize_grading_llm',
    'DEFAULT_MODEL',
    'TEMPERATURE_SETTINGS',
    
    # Cache
    'ResultCache',
    
    # Constants (all exported from constants module)
    'DEFAULT_CACHE_TTL',
    'MAX_CONTEXT_TOKENS',
    'VAGUE_QUESTION_PATTERNS',
    'FOLLOW_UP_PRONOUNS',
    'GENERIC_SUBJECTS',
    # ... (constants will be imported via *)
]

