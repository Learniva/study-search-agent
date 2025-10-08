"""
LLM Initialization Utilities for Multi-Agent System.

Optimized for Google Gemini with support for different use cases:
- Study Agent: Creative, conversational (higher temperature)
- Grading Agent: Precise, consistent (lower temperature)
- Supervisor Agent: Fast routing decisions (lower temperature)

Primary Provider: Google Gemini (fast, cost-effective, excellent for education)
Optional Support: OpenAI, Anthropic, HuggingFace (for advanced use cases)
"""

import os
from typing import Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI


# Gemini model recommendations
GEMINI_MODELS = {
    "default": "models/gemini-2.0-flash-exp",
    "flash": "models/gemini-2.0-flash-exp",
    "flash_thinking": "models/gemini-2.0-flash-thinking-exp-1219",
    "pro": "models/gemini-1.5-pro",
    "flash_8b": "models/gemini-1.5-flash-8b"
}

# Temperature settings for different use cases
TEMPERATURE_SETTINGS = {
    "study": 0.7,      # Creative, conversational
    "grading": 0.3,    # Precise, consistent evaluation
    "routing": 0.0,    # Deterministic decision-making
    "creative": 0.9,   # Max creativity (animations, content generation)
    "precise": 0.0     # Exact answers (math, code)
}


def initialize_llm(
    provider: str = "gemini",
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    use_case: Optional[Literal["study", "grading", "routing", "creative", "precise"]] = None,
    max_tokens: Optional[int] = None,
    **kwargs
):
    """
    Initialize and return Google Gemini LLM with optimized configuration.
    
    Args:
        provider: LLM provider - defaults to "gemini" (primary provider)
        model_name: Optional Gemini model override (e.g., "models/gemini-1.5-pro")
        temperature: Optional temperature override (0.0-1.0)
        use_case: Automatically set temperature based on use case
        max_tokens: Maximum tokens to generate
        **kwargs: Additional Gemini-specific arguments
        
    Returns:
        Initialized Gemini LLM instance configured for the specified use case
        
    Raises:
        ValueError: If GOOGLE_API_KEY is missing
        
    Examples:
        >>> # For grading with consistent evaluation (temp=0.3)
        >>> llm = initialize_llm(use_case="grading")
        
        >>> # For creative content generation (temp=0.9)
        >>> llm = initialize_llm(use_case="creative")
        
        >>> # Custom configuration
        >>> llm = initialize_llm(temperature=0.5, max_tokens=2048)
        
        >>> # Use specific Gemini model
        >>> llm = initialize_llm(model_name="models/gemini-1.5-pro")
    """
    provider = provider.lower()
    
    # Determine temperature based on use case
    if temperature is None and use_case:
        temperature = TEMPERATURE_SETTINGS.get(use_case, 0.7)
    elif temperature is None:
        temperature = 0.7  # Default conversational temperature
    
    # Gemini is the primary and default provider
    if provider == "gemini" or provider == "google":
        return _initialize_gemini(model_name, temperature, max_tokens, **kwargs)
    
    # Optional fallback providers (require additional packages)
    elif provider == "openai":
        return _initialize_openai(model_name, temperature, max_tokens, **kwargs)
    
    elif provider == "anthropic" or provider == "claude":
        return _initialize_anthropic(model_name, temperature, max_tokens, **kwargs)
    
    elif provider == "huggingface" or provider == "hf":
        return _initialize_huggingface(model_name, temperature, max_tokens, **kwargs)
    
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Primary provider is 'gemini'. Optional: 'openai', 'anthropic', 'huggingface'."
        )


def _initialize_gemini(
    model_name: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    **kwargs
) -> ChatGoogleGenerativeAI:
    """
    Initialize Google Gemini LLM with optimized settings.
    
    Args:
        model_name: Gemini model name (e.g., "models/gemini-2.0-flash-exp")
        temperature: Temperature setting (0.0-1.0)
        max_tokens: Maximum output tokens
        **kwargs: Additional Gemini-specific parameters
        
    Returns:
        Configured ChatGoogleGenerativeAI instance
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment variables. "
            "Get your free API key at: https://makersuite.google.com/app/apikey"
        )
    
    # Use specified model or default to latest Gemini Flash
    model = model_name or GEMINI_MODELS["default"]
    
    # Gemini-specific configuration
    config = {
        "model": model,
        "temperature": temperature,
        "google_api_key": api_key,
        "convert_system_message_to_human": True,  # Important for Gemini compatibility
    }
    
    if max_tokens:
        config["max_output_tokens"] = max_tokens
    
    # Merge with user-provided kwargs (allows advanced customization)
    config.update(kwargs)
    
    return ChatGoogleGenerativeAI(**config)


# =============================================================================
# OPTIONAL PROVIDERS (Require additional packages)
# =============================================================================

def _initialize_openai(
    model_name: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    **kwargs
):
    """
    Initialize OpenAI LLM (optional provider).
    
    Note: Requires langchain-openai package.
    Install with: pip install langchain-openai
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ValueError(
            "OpenAI provider requires langchain-openai package. "
            "Install with: pip install langchain-openai"
        )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not found in environment variables. "
            "Get your API key at: https://platform.openai.com/api-keys"
        )
    
    model = model_name or "gpt-4-turbo"
    
    config = {
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
    }
    
    if max_tokens:
        config["max_tokens"] = max_tokens
    
    config.update(kwargs)
    
    return ChatOpenAI(**config)


def _initialize_anthropic(
    model_name: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    **kwargs
):
    """
    Initialize Anthropic Claude LLM (optional provider).
    
    Note: Requires langchain-anthropic package.
    Install with: pip install langchain-anthropic
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ValueError(
            "Anthropic provider requires langchain-anthropic package. "
            "Install with: pip install langchain-anthropic"
        )
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables. "
            "Get your API key at: https://console.anthropic.com/"
        )
    
    model = model_name or "claude-3-5-sonnet-20241022"
    
    config = {
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
    }
    
    if max_tokens:
        config["max_tokens"] = max_tokens
    
    config.update(kwargs)
    
    return ChatAnthropic(**config)


def _initialize_huggingface(
    model_name: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    **kwargs
):
    """
    Initialize HuggingFace LLM (optional provider).
    
    Note: Requires langchain-huggingface package.
    Install with: pip install langchain-huggingface
    """
    try:
        from langchain_huggingface import HuggingFaceEndpoint
    except ImportError:
        raise ValueError(
            "HuggingFace provider requires langchain-huggingface package. "
            "Install with: pip install langchain-huggingface"
        )
    
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise ValueError(
            "HUGGINGFACE_API_KEY not found in environment variables. "
            "Get your API key at: https://huggingface.co/settings/tokens"
        )
    
    model = model_name or "mistralai/Mistral-7B-Instruct-v0.2"
    
    config = {
        "repo_id": model,
        "temperature": temperature,
        "huggingfacehub_api_token": api_key,
        "max_new_tokens": max_tokens or 1024,
    }
    
    config.update(kwargs)
    
    return HuggingFaceEndpoint(**config)


# =============================================================================
# HELPER FUNCTIONS FOR GEMINI CONFIGURATION
# =============================================================================

def get_recommended_gemini_model(use_case: str = "general") -> str:
    """
    Get recommended Gemini model for a specific use case.
    
    Args:
        use_case: Use case - "general", "fast", "quality", "thinking", "cost_effective"
        
    Returns:
        Recommended Gemini model name
    """
    recommendations = {
        "general": GEMINI_MODELS["default"],
        "fast": GEMINI_MODELS["flash_8b"],
        "quality": GEMINI_MODELS["pro"],
        "thinking": GEMINI_MODELS["flash_thinking"],
        "cost_effective": GEMINI_MODELS["flash_8b"]
    }
    
    return recommendations.get(use_case, GEMINI_MODELS["default"])


# =============================================================================
# CONVENIENCE FUNCTIONS FOR SPECIFIC USE CASES
# =============================================================================

def initialize_study_llm(**kwargs):
    """
    Initialize Gemini LLM optimized for study/research tasks.
    
    Settings: Creative, conversational (temp=0.7)
    Best for: Q&A, explanations, study guides, content generation
    """
    return initialize_llm(use_case="study", **kwargs)


def initialize_grading_llm(**kwargs):
    """
    Initialize Gemini LLM optimized for grading tasks.
    
    Settings: Precise, consistent (temp=0.3)
    Best for: Essay grading, code review, rubric evaluation
    """
    return initialize_llm(use_case="grading", **kwargs)


def initialize_routing_llm(**kwargs):
    """
    Initialize Gemini LLM optimized for routing decisions.
    
    Settings: Fast, deterministic (temp=0.0)
    Best for: Intent classification, task routing, decision-making
    """
    return initialize_llm(use_case="routing", **kwargs)

