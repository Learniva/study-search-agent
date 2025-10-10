"""
Tools Package

Organized by agent:
- tools.study: Tools for StudySearchAgent
- tools.grading: Tools for GradingAgent  
- tools.base: Base tool utilities (shared)

Import from subdirectories:
    from tools.study import get_document_qa_tool, get_web_search_tool
    from tools.grading import get_all_grading_tools
"""

# Re-export for backward compatibility
from .base import get_all_tools

# Study tools
try:
    from .study import (
        get_document_qa_tool,
        get_web_search_tool,
        get_python_repl_tool,
        get_manim_tool,
        initialize_document_qa,
    )
    STUDY_TOOLS_AVAILABLE = True
except ImportError:
    STUDY_TOOLS_AVAILABLE = False

# Grading tools
try:
    from .grading import (
        get_all_grading_tools,
        get_rubric_retrieval_tools,
        get_submission_processing_tools,
        initialize_rubric_store,
    )
    GRADING_TOOLS_AVAILABLE = True
except ImportError:
    GRADING_TOOLS_AVAILABLE = False

__all__ = [
    # Base
    'get_all_tools',
    
    # Study tools
    'get_document_qa_tool',
    'get_web_search_tool',
    'get_python_repl_tool',
    'get_manim_tool',
    'initialize_document_qa',
    
    # Grading tools
    'get_all_grading_tools',
    'get_rubric_retrieval_tools',
    'get_submission_processing_tools',
    'initialize_rubric_store',
    
    # Flags
    'STUDY_TOOLS_AVAILABLE',
    'GRADING_TOOLS_AVAILABLE',
]

