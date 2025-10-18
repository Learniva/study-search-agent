"""
Agent Package

Contains all agent implementations:
- SupervisorAgent: Main routing agent with RBAC (Role-Based Access Control)
- StudySearchAgent: Study & search agent with RAG features
- GradingAgent: Grading agent with adaptive rubrics

All agents include their respective Phase 2/3 enhancements:
- StudySearchAgent includes: query_with_rag() for adaptive retrieval & self-correction
- GradingAgent includes: grade_with_adaptation() for ML-powered grading
"""

from .study import StudySearchAgent
from .grading import GradingAgent
from .supervisor import SupervisorAgent

__all__ = [
    "StudySearchAgent",
    "GradingAgent",
    "SupervisorAgent",
]

