"""
Web Search Tool using LangChain with fallback architecture.

Search Strategy:
1. Google Custom Search (Primary) - Comprehensive and reliable search results
2. Tavily Search (Fallback) - AI-optimized search as backup

Built on LangChain's RunnableWithFallbacks for clean, maintainable fallback logic.
"""

import os
from typing import Optional, List, Dict, Any
from langchain.tools import Tool
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser


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


def tavily_search(query: str, api_key: str, num_results: int = 5) -> Optional[List[Dict]]:
    """
    Perform Tavily search using LangChain integration.
    
    Tavily is an AI-optimized search engine designed for LLMs and RAG applications.
    Provides high-quality, relevant results with content extraction.
    
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
            api_key=api_key,
            search_depth="advanced"  # Use advanced search for better quality
        )
        
        # Use invoke() method for modern LangChain compatibility
        results = tavily.invoke({"query": query})
        
        if isinstance(results, list) and results:
            # Normalize result format to match our standard
            normalized = []
            for r in results:
                normalized.append({
                    'title': r.get('title', r.get('name', 'No title')),
                    'snippet': r.get('content', r.get('snippet', 'No description')),
                    'link': r.get('url', r.get('link', 'No URL'))
                })
            return normalized
        return None
    except Exception as e:
        print(f"❌ Tavily search error: {e}")
        return None


def get_web_search_tool() -> Optional[Tool]:
    """
    Create web search tool using LangChain with fallback architecture.
    
    Architecture:
    1. Primary: Google Custom Search (comprehensive, reliable results)
    2. Fallback: Tavily Search (AI-optimized backup)
    
    Uses LangChain's RunnableWithFallbacks for clean fallback logic.
    
    Note: Context-aware reformulation is handled at the node level before
    invoking this tool.
    
    Returns:
        Tool object configured for web search
    """
    # Check which search providers are available
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    has_google = bool(google_api_key and google_search_engine_id)
    has_tavily = bool(tavily_api_key)
    
    if not has_google and not has_tavily:
        print("⚠️  No search providers configured. Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID, or TAVILY_API_KEY")
        return None
    
    def search_with_langchain(query: str) -> str:
        """
        LangChain-based search with fallback.
        
        Uses LCEL (LangChain Expression Language) with RunnableWithFallbacks
        for clean, maintainable fallback logic.
        
        Note: Context-aware reformulation is handled at the node level before
        calling this function.
        """
        # Create LangChain runnables for each search provider
        search_chain = None
        
        if has_google:
            # Primary: Google Custom Search
            def google_runnable(q: str) -> str:
                print("🔍 Searching with Google Custom Search (Primary)...")
                results = google_custom_search(q, google_api_key, google_search_engine_id, num_results=5)
                if not results:
                    raise ValueError("Google search returned no results")
                print("✅ Google search successful")
                return format_search_results(results)
            
            search_chain = RunnableLambda(google_runnable)
            
            # Add Tavily as fallback if available
            if has_tavily:
                def tavily_runnable(q: str) -> str:
                    print("🔍 Falling back to Tavily Search...")
                    results = tavily_search(q, tavily_api_key, num_results=5)
                    if not results:
                        raise ValueError("Tavily search returned no results")
                    print("✅ Tavily search successful (fallback)")
                    return format_search_results(results)
                
                # Add fallback using LangChain's with_fallbacks
                search_chain = search_chain.with_fallbacks([RunnableLambda(tavily_runnable)])
        
        elif has_tavily:
            # Only Tavily available (no fallback needed)
            def tavily_runnable(q: str) -> str:
                print("🔍 Searching with Tavily Search...")
                results = tavily_search(q, tavily_api_key, num_results=5)
                if not results:
                    raise ValueError("Tavily search returned no results")
                print("✅ Tavily search successful")
                return format_search_results(results)
            
            search_chain = RunnableLambda(tavily_runnable)
        
        # Execute the search chain
        try:
            return search_chain.invoke(query)
        except Exception as e:
            error_msg = str(e)
            print(f"❌ All search providers failed: {error_msg}")
            return "No search results found. Please try a different query or check your API keys."
    
    # Show which providers are configured
    if has_google and has_tavily:
        config_msg = "Google Custom Search (Primary) with Tavily fallback"
    elif has_google:
        config_msg = "Google Custom Search only"
    else:
        config_msg = "Tavily only"
    
    print(f"🌐 Web search configured: {config_msg}")
    print(f"🔗 Built on LangChain's RunnableWithFallbacks for clean fallback logic")
    
    return Tool(
        name="Web_Search",
        func=search_with_langchain,
        description="""Use this tool for real-time web searches using LangChain.

Search Strategy:
- Primary: Google Custom Search (comprehensive, reliable results)
- Fallback: Tavily (AI-optimized backup)

Built on LangChain's RunnableWithFallbacks for automatic failover.

Good for:
- Current events, news, or recent happenings
- Company information and organizations
- Latest statistics, data, or facts
- General knowledge and research
- Academic topics and explanations
- Any question requiring up-to-date information

Input: A clear, specific search query
Output: Formatted search results with titles, snippets, and URLs"""
    )
