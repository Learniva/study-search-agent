"""
Prompts Package

Centralized prompt templates for all agents:
- Study Agent prompts (ReAct-style)
- Grading Agent prompts
- Supervisor Agent prompts
- Tool-specific prompts
"""

from .prompts import (
    get_agent_prompt,
    get_grading_prompt_for_rubric,
    get_essay_grading_prompt,
    get_code_review_prompt,
    get_rubric_evaluation_prompt,
    get_feedback_prompt,
    get_citation_check_prompt,
    format_rubric_for_prompt,
    GRADING_AGENT_SYSTEM_PROMPT,
    SUPERVISOR_INTENT_CLASSIFICATION_PROMPT,
    SUPERVISOR_ACCESS_CONTROL_EXPLANATION,
    MANIM_ANIMATION_SYSTEM_PROMPT,
)

# Backward compatibility aliases
get_grading_prompt = get_grading_prompt_for_rubric
get_feedback_generation_prompt = get_feedback_prompt
get_mcq_grading_prompt = get_grading_prompt_for_rubric  # Same as general grading
get_supervisor_prompt = lambda: SUPERVISOR_INTENT_CLASSIFICATION_PROMPT
get_intent_classification_prompt = lambda: SUPERVISOR_INTENT_CLASSIFICATION_PROMPT

__all__ = [
    'get_agent_prompt',
    'get_grading_prompt',
    'get_grading_prompt_for_rubric',
    'get_essay_grading_prompt',
    'get_code_review_prompt',
    'get_rubric_evaluation_prompt',
    'get_feedback_prompt',
    'get_feedback_generation_prompt',
    'get_citation_check_prompt',
    'format_rubric_for_prompt',
    'get_mcq_grading_prompt',
    'get_supervisor_prompt',
    'get_intent_classification_prompt',
    'GRADING_AGENT_SYSTEM_PROMPT',
    'SUPERVISOR_INTENT_CLASSIFICATION_PROMPT',
    'SUPERVISOR_ACCESS_CONTROL_EXPLANATION',
    'MANIM_ANIMATION_SYSTEM_PROMPT',
]

