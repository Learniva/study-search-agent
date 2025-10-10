"""
Base module for tool definitions and interfaces.
"""

from typing import List
from langchain.tools import Tool


def get_all_tools() -> List[Tool]:
    """
    Get all available tools for the agent.
    Includes RAG tools for document Q&A via L2 Vector Store (pgvector).
    
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
    
    # Add RAG tools (L2 Vector Store for document Q&A)
    try:
        from .study import RAG_TOOLS_AVAILABLE
        from .study.rag_tools import get_all_rag_tools
        
        if RAG_TOOLS_AVAILABLE:
            rag_tools = get_all_rag_tools()
            if rag_tools:
                tools.extend(rag_tools)
                print(f"✅ RAG tools loaded ({len(rag_tools)} tools available)")
        else:
            print("⚠️  RAG tools not available (database not configured)")
    except Exception as e:
        print(f"⚠️  RAG tools initialization failed: {e}")
    
    return tools

