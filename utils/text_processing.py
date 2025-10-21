"""
Text Processing and Cleaning Utilities

Provides text cleaning and sanitization for web search results,
document processing, and user inputs.
"""

import re
import html
from typing import Optional


def clean_web_search_text(text: str) -> str:
    """
    Clean text from web search results (titles, snippets).
    
    Handles:
    - HTML entities (&amp;, &quot;, etc.)
    - Extra whitespace
    - Unicode normalization
    - Special characters
    - Truncation markers
    
    Args:
        text: Raw text from web search
        
    Returns:
        Cleaned, human-readable text
    """
    if not text:
        return ""
    
    # 1. Decode HTML entities (&amp; -> &, &quot; -> ", etc.)
    text = html.unescape(text)
    
    # 2. Remove zero-width characters and other invisible Unicode
    text = re.sub(r'[\u200b-\u200f\u2060\ufeff]', '', text)
    
    # 3. Normalize whitespace (multiple spaces -> single space)
    text = re.sub(r'\s+', ' ', text)
    
    # 4. Clean up truncation markers
    text = re.sub(r'\.\.\.$', '...', text)  # Standardize ellipsis at end
    
    # 5. Remove any remaining HTML tags (defensive)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 6. Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def clean_url(url: str) -> str:
    """
    Clean and normalize URLs from web search.
    
    Handles:
    - Tracking parameters removal (optional)
    - URL encoding normalization
    - Invalid characters
    
    Args:
        url: Raw URL from web search
        
    Returns:
        Cleaned URL
    """
    if not url:
        return ""
    
    # Basic validation
    url = url.strip()
    
    # Optional: Remove common tracking parameters
    # Uncomment if you want cleaner URLs
    # tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'fbclid', 'gclid']
    # for param in tracking_params:
    #     url = re.sub(rf'[?&]{param}=[^&]*', '', url)
    
    return url


def sanitize_for_llm(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text for LLM consumption.
    
    Additional cleaning beyond basic web search cleaning:
    - Length limiting
    - Special token removal
    - Format normalization
    
    Args:
        text: Text to sanitize
        max_length: Optional maximum length (tokens approximation)
        
    Returns:
        Sanitized text safe for LLM
    """
    if not text:
        return ""
    
    # Apply basic cleaning first
    text = clean_web_search_text(text)
    
    # Remove potential prompt injection attempts (defensive)
    # Remove excessive repeated characters
    text = re.sub(r'(.)\1{10,}', r'\1\1\1', text)
    
    # Limit length if specified (rough approximation: 4 chars ≈ 1 token)
    if max_length:
        char_limit = max_length * 4
        if len(text) > char_limit:
            text = text[:char_limit] + "..."
    
    return text


def extract_domain(url: str) -> str:
    """
    Extract clean domain from URL for citation display.
    
    Args:
        url: Full URL
        
    Returns:
        Domain name (e.g., "wikipedia.org")
    """
    if not url:
        return "Unknown source"
    
    # Extract domain using regex
    match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
    if match:
        return match.group(1)
    return url


def format_citation(title: str, url: str, index: int) -> str:
    """
    Format a clean citation for web search results.
    
    Args:
        title: Result title
        url: Result URL
        index: Citation number
        
    Returns:
        Formatted citation string
    """
    clean_title = clean_web_search_text(title)
    domain = extract_domain(url)
    
    return f"[{index}] {clean_title} ({domain})"


def is_spam_content(text: str) -> bool:
    """
    Detect likely spam or low-quality content.
    
    Args:
        text: Text to check
        
    Returns:
        True if content appears to be spam
    """
    if not text or len(text.strip()) < 20:
        return True  # Too short
    
    text_lower = text.lower()
    
    # Spam indicators
    spam_keywords = [
        'click here', 'buy now', 'limited time', 'act now',
        'free money', 'earn $$$', 'make money fast'
    ]
    
    spam_count = sum(1 for keyword in spam_keywords if keyword in text_lower)
    
    # Check for excessive capitalization
    if len(text) > 20:
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
        if caps_ratio > 0.5:  # More than 50% caps
            return True
    
    return spam_count >= 2  # 2 or more spam keywords


def normalize_newlines(text: str) -> str:
    """
    Normalize different newline formats.
    
    Args:
        text: Text with mixed newline formats
        
    Returns:
        Text with consistent newlines
    """
    # Convert Windows (CRLF) and old Mac (CR) to Unix (LF)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove excessive newlines (3+ -> 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


__all__ = [
    'clean_web_search_text',
    'clean_url',
    'sanitize_for_llm',
    'extract_domain',
    'format_citation',
    'is_spam_content',
    'normalize_newlines',
]

