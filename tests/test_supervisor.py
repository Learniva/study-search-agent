"""Supervisor agent tests."""

import pytest
from unittest.mock import patch, MagicMock

from agents.supervisor.core import SupervisorAgent


@pytest.fixture
def supervisor_agent():
    """Create a supervisor agent for testing."""
    with patch("agents.supervisor.core.initialize_llm") as mock_llm:
        mock_llm.return_value = MagicMock()
        agent = SupervisorAgent()
        yield agent


def test_supervisor_initialization(supervisor_agent):
    """Test supervisor agent initialization."""
    assert supervisor_agent is not None
    assert supervisor_agent.llm is not None
    assert supervisor_agent.graph is not None


def test_get_capabilities(supervisor_agent):
    """Test getting capabilities for different roles."""
    # Student capabilities
    student_caps = supervisor_agent.get_capabilities("student")
    assert "study_features" in student_caps
    assert len(student_caps["study_features"]) > 0
    assert "grading_features" in student_caps
    assert len(student_caps["grading_features"]) == 0

    # Teacher capabilities
    teacher_caps = supervisor_agent.get_capabilities("teacher")
    assert "study_features" in teacher_caps
    assert len(teacher_caps["study_features"]) > 0
    assert "grading_features" in teacher_caps
    assert len(teacher_caps["grading_features"]) > 0
