"""
Web search tool for real-time information retrieval.
"""

import os
from typing import Optional
from langchain.tools import Tool
from langchain_community.tools.tavily_search import TavilySearchResults


def get_web_search_tool() -> Optional[Tool]:
    """
    Create and return the web search tool using Tavily API.
    
    This tool performs web searches and is useful for:
    - Current events and news
    - Real-time data
    - Recent developments
    - Up-to-date facts
    
    Returns:
        Tool object configured for web search, or None if API key is not available
    """
    try:
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            print("Warning: TAVILY_API_KEY not found. Web search tool will be unavailable.")
            return None
        
        web_search = TavilySearchResults(
            max_results=3,
            api_key=tavily_api_key
        )
        
        return Tool(
            name="Web_Search",
            func=web_search.run,
            description="""Use this tool when you need real-time, up-to-date information about:
- Current events, news, or recent happenings
- Latest statistics, data, or facts
- Information that may have changed recently
- Weather, stock prices, or other time-sensitive data
- Recent developments in any field

Input should be a clear search query."""
        )
    except Exception as e:
        print(f"Warning: Web search tool unavailable: {e}")
        return None

