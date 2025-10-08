"""
Utility modules for the Study and Search Agent.

Provides:
- LLM initialization (Google Gemini 2.5 Flash)
- Centralized prompt templates for all agents and tools
- Authentication and authorization utilities
"""

# LLM initialization (Gemini 2.5 Flash)
from .llm import (
    initialize_llm,
    initialize_study_llm,
    initialize_grading_llm,
    initialize_routing_llm,
    initialize_creative_llm,
    initialize_precise_llm,
    DEFAULT_MODEL,
    TEMPERATURE_SETTINGS
)

# Study Agent prompts
from .prompts import get_agent_prompt

# Grading Agent prompts
from .prompts import (
    GRADING_AGENT_SYSTEM_PROMPT,
    get_grading_prompt_for_rubric,
    get_essay_grading_prompt,
    get_code_review_prompt,
    get_rubric_evaluation_prompt,
    get_feedback_prompt
)

# Supervisor Agent prompts
from .prompts import (
    SUPERVISOR_INTENT_CLASSIFICATION_PROMPT,
    SUPERVISOR_ACCESS_CONTROL_EXPLANATION
)

# Animation prompts
from .prompts import MANIM_ANIMATION_SYSTEM_PROMPT

# Citation and rubric helpers
from .prompts import (
    get_citation_check_prompt,
    format_rubric_for_prompt,
    CITATION_STYLE_GUIDELINES
)

__all__ = [
    # LLM (Gemini 2.5 Flash)
    'initialize_llm',
    'initialize_study_llm',
    'initialize_grading_llm',
    'initialize_routing_llm',
    'initialize_creative_llm',
    'initialize_precise_llm',
    'DEFAULT_MODEL',
    'TEMPERATURE_SETTINGS',
    
    # Study Agent
    'get_agent_prompt',
    
    # Grading Agent
    'GRADING_AGENT_SYSTEM_PROMPT',
    'get_grading_prompt_for_rubric',
    'get_essay_grading_prompt',
    'get_code_review_prompt',
    'get_rubric_evaluation_prompt',
    'get_feedback_prompt',
    
    # Supervisor Agent
    'SUPERVISOR_INTENT_CLASSIFICATION_PROMPT',
    'SUPERVISOR_ACCESS_CONTROL_EXPLANATION',
    
    # Animation
    'MANIM_ANIMATION_SYSTEM_PROMPT',
    
    # Helpers
    'get_citation_check_prompt',
    'format_rubric_for_prompt',
    'CITATION_STYLE_GUIDELINES'
]

