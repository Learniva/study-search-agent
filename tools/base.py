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
    from .study.python_repl import get_python_repl_tool
    from .study.web_search import get_web_search_tool
    from .study.document_qa import get_document_qa_tool
    from .study.manim_animation import get_manim_tool
    
    tools = []
    
    # Add Python REPL tool 
    tools.append(get_python_repl_tool())
    
    # Add Web Search tool 
    web_search_tool = get_web_search_tool()
    if web_search_tool:
        tools.append(web_search_tool)
    
    # Add Document Q&A tool 
    doc_qa_tool = get_document_qa_tool()
    if doc_qa_tool:
        tools.append(doc_qa_tool)
    
    # Add Manim Animation tool
    manim_tool = get_manim_tool()
    if manim_tool:
        tools.append(manim_tool)
    
    return tools

