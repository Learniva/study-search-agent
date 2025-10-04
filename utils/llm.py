"""
LLM initialization utilities.
Supports multiple LLM providers (HuggingFace, Gemini, OpenAI, Anthropic).
"""

import os
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEndpoint


def initialize_llm(provider: str = "gemini", model_name: Optional[str] = None):
    """
    Initialize and return an LLM based on the specified provider.
    
    Args:
        provider: One of "huggingface", "gemini", "openai", "anthropic"
        model_name: Optional model name override
        
    Returns:
        Initialized LLM instance
        
    Raises:
        ValueError: If provider is unsupported or API key is missing
    """
    provider = provider.lower()
    
    if provider == "huggingface" or provider == "hf":
        api_key = os.getenv("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError("HUGGINGFACE_API_KEY not found in environment variables")
        
        # Default to a reliable model that works with free tier
        model = model_name or "google/flan-t5-xxl"
        
        return HuggingFaceEndpoint(
            repo_id=model,
            temperature=0.1,
            huggingfacehub_api_token=api_key,
            max_new_tokens=512
        )
    
    elif provider == "gemini" or provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        return ChatGoogleGenerativeAI(
            model=model_name or "models/gemini-2.5-flash",
            temperature=0,
            google_api_key=api_key,
            convert_system_message_to_human=True
        )
    
    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ValueError("langchain-openai not installed. Install with: pip install langchain-openai")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return ChatOpenAI(
            model=model_name or "gpt-4-turbo-preview",
            temperature=0,
            api_key=api_key
        )
    
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ValueError("langchain-anthropic not installed. Install with: pip install langchain-anthropic")
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        return ChatAnthropic(
            model=model_name or "claude-3-sonnet-20240229",
            temperature=0,
            api_key=api_key
        )
    
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Use 'huggingface', 'gemini', 'openai', or 'anthropic'."
        )

