"""
LLM Initialization Utilities for Multi-Agent System using Google Gemini.


Optimized for speed, cost-effectiveness, and educational tasks.
- Study Agent: Creative, conversational (higher temperature)
- Grading Agent: Precise, consistent (lower temperature)
- Supervisor Agent: Fast routing decisions (lower temperature)

Temperature-based configuration for different use cases:
- Study: 0.7 (creative, conversational)
- Grading: 0.3 (precise, consistent)
- Routing: 0.0 (deterministic)
- Creative: 0.9 (animations, content generation)
- Precise: 0.0 (math, code execution)

Optimized for educational tasks with role-specific settings.
"""

import os
from typing import Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI


# Default Gemini models (2.5 generation - stable)
DEFAULT_MODEL = "gemini-2.5-flash"  # Fast, cost-effective
FALLBACK_MODEL = "gemini-2.5-pro"   # Advanced reasoning

# Temperature settings by use case
TEMPERATURE_SETTINGS = {
    "study": 0.7,      # Creative, conversational
    "grading": 0.3,    # Precise, consistent evaluation
    "routing": 0.0,    # Deterministic decision-making
    "creative": 0.9,   # Max creativity (animations, content generation)
    "precise": 0.0     # Exact answers (math, code)
}


def initialize_llm(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    use_case: Optional[Literal["study", "grading", "routing", "creative", "precise"]] = None,
    max_tokens: Optional[int] = None,
    streaming: bool = False,
    **kwargs
) -> ChatGoogleGenerativeAI:
    """
    Initialize Google Gemini LLM with optimized configuration.
    
    Args:
        model_name: Optional model override (default: gemini-2.5-flash)
        temperature: Optional temperature (0.0-1.0), overrides use_case
        use_case: Auto-set temperature: study, grading, routing, creative, precise
        max_tokens: Maximum output tokens
        streaming: Enable streaming mode for token-by-token output
        **kwargs: Additional Gemini parameters
        
    Returns:
        Configured ChatGoogleGenerativeAI instance
        
    Examples:
        >>> llm = initialize_llm(use_case="grading")  # temp=0.3
        >>> llm = initialize_llm(use_case="creative")  # temp=0.9
        >>> llm = initialize_llm(temperature=0.5, max_tokens=2048)
        >>> llm = initialize_llm(use_case="study", streaming=True)  # For streaming
    """
    # Get API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found. "
            "Get your API key at: https://makersuite.google.com/app/apikey"
        )
    
    # Set temperature based on use case or default
    if temperature is None and use_case:
        temperature = TEMPERATURE_SETTINGS.get(use_case, 0.7)
    elif temperature is None:
        temperature = 0.7
    
    # Determine model to use
    model = model_name or DEFAULT_MODEL
    
    # Configure Gemini
    config = {
        "model": model,
        "temperature": temperature,
        "google_api_key": api_key,
        "convert_system_message_to_human": True,
        "streaming": streaming,  # Enable/disable streaming mode
    }
    
    if max_tokens:
        config["max_output_tokens"] = max_tokens
    
    config.update(kwargs)
    
    try:
        return ChatGoogleGenerativeAI(**config)
    except Exception as e:
        # If default model fails, try fallback
        if model == DEFAULT_MODEL and "not found" in str(e).lower():
            print(f"⚠️  {DEFAULT_MODEL} unavailable, falling back to {FALLBACK_MODEL}")
            config["model"] = FALLBACK_MODEL
            return ChatGoogleGenerativeAI(**config)
        raise


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def initialize_study_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """
    Initialize Gemini for study/research tasks.
    Temperature: 0.7 (creative, conversational)
    """
    return initialize_llm(use_case="study", **kwargs)


def initialize_grading_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """
    Initialize Gemini for grading tasks.
    Temperature: 0.3 (precise, consistent)
    """
    return initialize_llm(use_case="grading", **kwargs)


def initialize_routing_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """
    Initialize Gemini for routing/classification.
    Temperature: 0.0 (deterministic)
    """
    return initialize_llm(use_case="routing", **kwargs)


def initialize_creative_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """
    Initialize Gemini for creative tasks.
    Temperature: 0.9 (maximum creativity)
    """
    return initialize_llm(use_case="creative", **kwargs)


def initialize_precise_llm(**kwargs) -> ChatGoogleGenerativeAI:
    """
    Initialize Gemini for precise tasks.
    Temperature: 0.0 (exact answers)
    """
    return initialize_llm(use_case="precise", **kwargs)

