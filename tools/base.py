"""
Base module for tool definitions and interfaces.
"""

from typing import List
from langchain.tools import Tool


def get_all_tools() -> List[Tool]:
    """
    Get all available tools for the agent.
    Document Q&A is now handled via RAG tools (retrieve_from_vector_store).
    
    Returns:
        List of Tool objects
    """
    from .study.python_repl import get_python_repl_tool
    from .study.web_search import get_web_search_tool
    from .study.manim_animation import get_manim_tool
    
    tools = []
    
    # Add Python REPL tool 
    tools.append(get_python_repl_tool())
    
    # Add Web Search tool 
    web_search_tool = get_web_search_tool()
    if web_search_tool:
        tools.append(web_search_tool)
    
    # Add Manim Animation tool
    manim_tool = get_manim_tool()
    if manim_tool:
        tools.append(manim_tool)
    
    # RAG tools (L2 Vector Store) are imported separately via tools.study.rag_tools
    
    return tools

