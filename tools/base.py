"""
Base module for tool definitions and interfaces.
"""

from typing import List
from langchain.tools import Tool


def get_all_tools() -> List[Tool]:
    """
    Get all available tools for the agent.
    
    Returns:
        List of Tool objects
    """
    from .python_repl import get_python_repl_tool
    from .web_search import get_web_search_tool
    
    tools = []
    
    # Add Python REPL tool (always available)
    tools.append(get_python_repl_tool())
    
    # Add Web Search tool (if available)
    web_search_tool = get_web_search_tool()
    if web_search_tool:
        tools.append(web_search_tool)
    
    return tools

