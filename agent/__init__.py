"""
Agent Package

Contains all agent implementations:
- SupervisorAgent: Main routing agent with RBAC (Role-Based Access Control)
- StudySearchAgent: Study & search agent with Phase 2 RAG features
- GradingAgent: Grading agent with Phase 3 adaptive rubrics

All agents include their respective Phase 2/3 enhancements:
- StudySearchAgent includes: query_with_rag() for adaptive retrieval & self-correction
- GradingAgent includes: grade_with_adaptation() for ML-powered grading
"""

from .supervisor_agent import SupervisorAgent
from .study_agent import StudySearchAgent
from .grading_agent import GradingAgent

__all__ = [
    'SupervisorAgent',
    'StudySearchAgent',
    'GradingAgent',
]

