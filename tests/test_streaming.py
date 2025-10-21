"""Test streaming functionality."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from agents.study.core import StudySearchAgent
from agents.supervisor.core import SupervisorAgent


@pytest.fixture
def mock_llm():
    """Create a mock LLM that supports streaming."""
    mock = MagicMock()
    
    # Mock agenerate to simulate streaming
    async def mock_agenerate(*args, **kwargs):
        callbacks = kwargs.get("callbacks", [])
        # Simulate streaming tokens
        for token in ["This ", "is ", "a ", "test ", "streaming ", "response."]:
            for callback in callbacks:
                if hasattr(callback, "on_llm_new_token"):
                    callback.on_llm_new_token(token)
            await asyncio.sleep(0.01)
        
        # Return mock generation
        generation = MagicMock()
        generation.generations = [[MagicMock(text="This is a test streaming response.")]]
        return generation
    
    mock.agenerate = mock_agenerate
    return mock


@pytest.mark.asyncio
async def test_base_agent_streaming():
    """Test streaming functionality in BaseAgent."""
    with patch("utils.initialize_llm") as mock_init_llm:
        # Set up the mock LLM
        mock_llm = MagicMock()
        
        # Mock agenerate to simulate streaming
        async def mock_agenerate(*args, **kwargs):
            callbacks = kwargs.get("callbacks", [])
            # Simulate streaming tokens
            for token in ["This ", "is ", "a ", "test ", "streaming ", "response."]:
                for callback in callbacks:
                    if hasattr(callback, "on_llm_new_token"):
                        callback.on_llm_new_token(token)
                await asyncio.sleep(0.01)
            
            # Return mock generation
            generation = MagicMock()
            generation.generations = [[MagicMock(text="This is a test streaming response.")]]
            return generation
        
        mock_llm.agenerate = mock_agenerate
        mock_init_llm.return_value = mock_llm
        
        # Create a study agent with mocked components
        agent = StudySearchAgent()
        
        # Mock the app.invoke to return a simple result
        agent.app = MagicMock()
        agent.app.invoke.return_value = {
            "question": "test question",
            "is_complex_task": False,
            "tool_result": "This is a test result",
            "document_qa_failed": False
        }
        
        # Test streaming
        chunks = []
        async for chunk in agent.aquery_stream("test question"):
            chunks.append(chunk)
        
        # Verify we got streaming chunks
        assert len(chunks) > 1
        assert "".join(chunks) != ""


@pytest.mark.asyncio
async def test_supervisor_streaming():
    """Test streaming functionality in SupervisorAgent."""
    with patch("agents.supervisor.core.initialize_llm") as mock_init_llm:
        mock_init_llm.return_value = MagicMock()
        
        # Create a supervisor agent with mocked components
        supervisor = SupervisorAgent()
        
        # Mock the study agent's streaming method
        mock_study_agent = MagicMock()
        supervisor._study_agent = mock_study_agent
        
        # Set up the mock streaming generator
        async def mock_stream():
            for chunk in ["This ", "is ", "a ", "test ", "streaming ", "response."]:
                yield chunk
        
        mock_study_agent.aquery_stream.return_value = mock_stream()
        
        # Mock the nodes to route to study agent
        supervisor.nodes.enrich_context = MagicMock(return_value={
            "intent": "STUDY",
            "agent_choice": "study_agent",
            "access_denied": False
        })
        supervisor.nodes.classify_intent = MagicMock(return_value={
            "intent": "STUDY",
            "agent_choice": "study_agent",
            "access_denied": False
        })
        supervisor.nodes.check_access = MagicMock(return_value={
            "intent": "STUDY",
            "agent_choice": "study_agent",
            "access_denied": False
        })
        
        # Test streaming
        chunks = []
        async for chunk in supervisor.aquery_stream("test question", user_role="student"):
            chunks.append(chunk)
        
        # Verify we got streaming chunks
        assert len(chunks) > 1
        assert "".join(chunks) == "This is a test streaming response."
        
        # Verify the study agent's streaming method was called
        mock_study_agent.aquery_stream.assert_called_once()

