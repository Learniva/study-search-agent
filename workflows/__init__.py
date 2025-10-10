"""
Workflows Package

Contains LangGraph workflows for agent orchestration:
- RAG Workflow: Self-correcting RAG with adaptive retrieval (Phase 2)
- Grading Workflow: Adaptive grading with ML learning (Phase 3)
"""

# Phase 2: RAG Workflow
try:
    from .rag_workflow import RAGWorkflow
    RAG_WORKFLOW_AVAILABLE = True
except ImportError:
    RAG_WORKFLOW_AVAILABLE = False

# Phase 3: Grading Workflow
try:
    from .grading_workflow import AdaptiveGradingWorkflow
    GRADING_WORKFLOW_AVAILABLE = True
except ImportError:
    GRADING_WORKFLOW_AVAILABLE = False

__all__ = [
    'RAGWorkflow',
    'AdaptiveGradingWorkflow',
    'RAG_WORKFLOW_AVAILABLE',
    'GRADING_WORKFLOW_AVAILABLE',
]

