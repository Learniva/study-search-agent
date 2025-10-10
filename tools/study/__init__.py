"""
Study Agent Tools

Tools used by the StudySearchAgent:
- web_search: Web search with Tavily
- python_repl: Python code execution
- manim_animation: Mathematical animation generation
- rag_tools: RAG tools (adaptive retrieval, self-correction, vector store)
"""

from .web_search import get_web_search_tool
from .python_repl import get_python_repl_tool
from .manim_animation import get_manim_tool

# Phase 2: RAG tools
try:
    from .rag_tools import (
        retrieve_from_vector_store,
        query_learning_store,
        enhanced_web_search,
        should_retrieve_context,
        get_all_rag_tools
    )
    RAG_TOOLS_AVAILABLE = True
except ImportError:
    RAG_TOOLS_AVAILABLE = False

__all__ = [
    # Core study tools
    'get_web_search_tool',
    'get_python_repl_tool',
    'get_manim_tool',
    
    # RAG tools (includes vector store retrieval)
    'retrieve_from_vector_store',
    'query_learning_store',
    'enhanced_web_search',
    'should_retrieve_context',
    'get_all_rag_tools',
    'RAG_TOOLS_AVAILABLE',
]

