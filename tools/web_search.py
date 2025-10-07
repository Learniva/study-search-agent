"""
Web search tool with hybrid approach:
1. Google Custom Search API
2. DuckDuckGo (free fallback)
3. Tavily (legacy support)
"""

import os
from typing import Optional, List, Dict, Any
from langchain.tools import Tool


def format_search_results(results: List[Dict[str, Any]]) -> str:
    """
    Format search results into human-readable text.
    
    Args:
        results: List of search result dictionaries
        
    Returns:
        Formatted string with search results
    """
    if not results:
        return "No search results found."
    
    formatted = []
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', result.get('content', 'No description'))
        url = result.get('link', result.get('url', 'No URL'))
        
        formatted.append(f"{i}. {title}\n   {snippet}\n   Source: {url}")
    
    return "\n\n".join(formatted)


def google_custom_search(query: str, api_key: str, search_engine_id: str, num_results: int = 5) -> Optional[List[Dict]]:
    """
    Perform Google Custom Search.
    
    Args:
        query: Search query
        api_key: Google API key
        search_engine_id: Custom Search Engine ID
        num_results: Number of results to return
        
    Returns:
        List of search results or None if error
    """
    try:
        from googleapiclient.discovery import build
        
        service = build("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(
            q=query,
            cx=search_engine_id,
            num=num_results
        ).execute()
        
        if 'items' in result:
            return [
                {
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', '')
                }
                for item in result['items']
            ]
        return None
    except Exception as e:
        print(f"Google Custom Search error: {e}")
        return None


def duckduckgo_search(query: str, num_results: int = 5) -> Optional[List[Dict]]:
    """
    Perform DuckDuckGo search with retry logic 
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        List of search results or None if error
    """
    import time
    
    max_retries = 2
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            from duckduckgo_search import DDGS
            
            # Add headers to avoid rate limiting
            with DDGS(headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }) as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
                
            if results:
                return [
                    {
                        'title': r.get('title', ''),
                        'snippet': r.get('body', ''),
                        'link': r.get('href', '')
                    }
                    for r in results
                ]
            return None
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # If rate limited, retry after delay
            if 'ratelimit' in error_msg and attempt < max_retries - 1:
                print(f"⚠️  DuckDuckGo rate limited. Retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                print(f"❌ DuckDuckGo search failed: {e}")
                return None
    
    return None


def tavily_search(query: str, api_key: str, num_results: int = 5) -> Optional[List[Dict]]:
    """
    Perform Tavily search (legacy support).
    
    Args:
        query: Search query
        api_key: Tavily API key
        num_results: Number of results to return
        
    Returns:
        List of search results or None if error
    """
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        
        tavily = TavilySearchResults(
            max_results=num_results,
            api_key=api_key
        )
        
        results = tavily.run(query)
        
        if isinstance(results, list):
            return results
        return None
    except Exception as e:
        print(f"Tavily search error: {e}")
        return None


def get_web_search_tool() -> Optional[Tool]:
    """
    Create web search tool with hybrid approach:
    1. Try Google Custom Search API (best quality)
    2. Fall back to DuckDuckGo (free, good quality)
    3. Fall back to Tavily (if configured)
    
    Returns:
        Tool object configured for web search
    """
    # Check which search providers are available
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    has_google = bool(google_api_key and google_search_engine_id)
    has_tavily = bool(tavily_api_key)
    
    # DuckDuckGo is always available (no API key needed)
    
    def hybrid_search(query: str) -> str:
        """
        Hybrid search with fallback strategy.
        Tries Tavily → Google → DuckDuckGo
        """
        results = None
        search_provider = None
        
        # Try Tavily first (reliable, good quality for specific queries)
        if has_tavily:
            print("🔍 Searching with Tavily...")
            results = tavily_search(query, tavily_api_key, num_results=5)
            if results:
                search_provider = "Tavily"
        
        # Fall back to Google Custom Search (best quality if configured)
        if not results and has_google:
            print("🔍 Searching with Google Custom Search API (fallback)...")
            results = google_custom_search(
                query, 
                google_api_key, 
                google_search_engine_id,
                num_results=5
            )
            if results:
                search_provider = "Google"
        
        # Fall back to DuckDuckGo (free but rate-limited)
        if not results:
            print("🔍 Searching with DuckDuckGo (free fallback)...")
            results = duckduckgo_search(query, num_results=5)
            if results:
                search_provider = "DuckDuckGo"
        
        # Format results
        if results:
            formatted = format_search_results(results)
            print(f"✅ Found results using {search_provider}")
            return formatted
        else:
            return "No search results found. Please try a different query."
    
    # Show which providers are configured
    providers = []
    if has_tavily:
        providers.append("Tavily (primary, reliable)")
    else:
        providers.append("Tavily (not configured)")
    if has_google:
        providers.append("Google Custom Search (fallback)")
    providers.append("DuckDuckGo (free fallback)")
    
    print(f"🌐 Web search configured with: {', '.join(providers)}")
    
    return Tool(
        name="Web_Search",
        func=hybrid_search,
        description="""Use this tool for real-time web searches. Hybrid search with:
1. Tavily (primary - reliable, good quality, LLM-optimized)
2. Google Custom Search API (fallback, best quality if configured)
3. DuckDuckGo (free fallback, may have rate limits)

Good for:
- Current events, news, or recent happenings
- Company information and organizations
- Latest statistics, data, or facts
- General knowledge and research
- Academic topics and explanations

Input should be a clear search query."""
    )
