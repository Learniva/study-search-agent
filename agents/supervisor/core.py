"""Supervisor Agent - Clean, modular implementation."""

from typing import Optional, Dict, Any, List
import time

from .state import SupervisorState
from .workflow import build_supervisor_workflow
from .concurrent_supervisor import ConcurrentSupervisorMixin
from utils.patterns import StateManager
from utils.config_integration import ConfigManager
from utils import initialize_llm
from utils.monitoring import get_logger

logger = get_logger(__name__)


class SupervisorAgent(ConcurrentSupervisorMixin):
    """
    Supervisor Agent with role-based routing.
    
    Routes between Study and Grading agents based on:
    - User role (student/teacher/admin)
    - Query intent (STUDY/GRADE)
    - Access control rules
    
    Features:
    - Intelligent routing with pattern matching
    - Learning from past decisions
    - Performance tracking
    - Quality evaluation
    
    Note: Doesn't inherit from BaseAgent because it has different
    query handling pattern (routes to other agents instead of tools).
    """
    
    def __init__(
        self,
        llm_provider: str = "gemini",
        model_name: Optional[str] = None
    ):
        """Initialize Supervisor Agent with concurrent execution support."""
        self.llm_provider = llm_provider.lower()
        self.model_name = model_name
        self.llm = initialize_llm(model_name=model_name, use_case="routing")
        
        # Lazy load agents (only when needed)
        self._study_agent = None
        self._grading_agent = None
        
        # Learning and adaptation
        self._routing_history = []
        self._routing_patterns = {}
        self._max_history = 100
        
        # Initialize concurrent execution capabilities (from mixin)
        # This sets up task_manager, duration_estimator, and _concurrent_mode_enabled
        if hasattr(super(), '__init__'):
            try:
                super().__init__(llm_provider=llm_provider, model_name=model_name)
            except TypeError:
                # Mixin doesn't accept these params, initialize without them
                from utils.concurrent_execution import get_task_manager, TaskDurationEstimator
                self.task_manager = get_task_manager()
                self.duration_estimator = TaskDurationEstimator()
                self._concurrent_mode_enabled = True
        
        # Build workflow
        workflow, self.nodes = build_supervisor_workflow(
            self.llm,
            self._routing_history,
            self._routing_patterns
        )
        
        # Add agent execution nodes dynamically
        def study_agent_node(state: SupervisorState) -> SupervisorState:
            return self.nodes.execute_study_agent(state, self.study_agent)
        
        def grading_agent_node(state: SupervisorState) -> SupervisorState:
            return self.nodes.execute_grading_agent(state, self.grading_agent)
        
        workflow.add_node("study_agent", study_agent_node)
        workflow.add_node("grading_agent", grading_agent_node)
        
        # Add edges from agents to evaluator
        workflow.add_edge("study_agent", "evaluate_result")
        workflow.add_edge("grading_agent", "evaluate_result")
        
        self.graph = workflow.compile()
    
    @property
    def study_agent(self):
        """Lazy load study agent."""
        if self._study_agent is None:
            from agents.study import StudySearchAgent
            self._study_agent = StudySearchAgent(
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
        return self._study_agent
        
    @property
    def streaming_study_agent(self):
        """Lazy load streaming study agent with concurrent support."""
        if not hasattr(self, "_streaming_study_agent") or self._streaming_study_agent is None:
            # Use the optimized fast streaming agent for better performance
            from agents.study.fast_streaming_agent import FastStreamingStudyAgent
            self._streaming_study_agent = FastStreamingStudyAgent(
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
            logger.info("⚡ Fast streaming study agent initialized (<100ms first response)")
        return self._streaming_study_agent
    
    @property
    def grading_agent(self):
        """Lazy load grading agent."""
        if self._grading_agent is None:
            from agents.grading import GradingAgent
            self._grading_agent = GradingAgent(
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
        return self._grading_agent
    
    def query(
        self,
        question: str,
        user_role: str = "student",
        thread_id: str = "default",
        user_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for supervisor routing.
        
        Args:
            question: User's question
            user_role: User's role (student/teacher/admin)
            thread_id: Conversation thread ID
            user_id: User ID for tracking
            student_id: Student ID (for grading)
            student_name: Student name (for grading)
            course_id: Course ID
            assignment_id: Assignment ID
            assignment_name: Assignment name
            
        Returns:
            Dictionary with answer and metadata
        """
        try:
            # Normalize role
            normalized_role = user_role.upper()
            if normalized_role in ["PROFESSOR", "INSTRUCTOR"]:
                normalized_role = "TEACHER"
            
            # Initial state
            initial_state: SupervisorState = {
                "question": question,
                "user_role": normalized_role,
                "user_id": user_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "assignment_name": assignment_name,
                "intent": None,
                "agent_choice": None,
                "access_denied": False,
                "routing_confidence": None,
                "agent_result": None,
                "agent_used": None,
                "final_answer": None,
                "routing_time": None,
                "agent_execution_time": None,
                "total_time": None,
                "routing_success": None,
                "routing_alternatives": [],
                "learned_from_history": False,
                "result_quality": None,
                "user_satisfaction_predicted": None,
                "context_used": None,
                "similar_past_queries": []
            }
            
            # Execute graph
            result = self.graph.invoke(initial_state)
            
            # Return standardized response
            return {
                "answer": result["final_answer"],
                "agent_used": result.get("agent_used"),
                "user_role": user_role,
                "success": not result["access_denied"],
                "routing_confidence": result.get("routing_confidence"),
                "total_time": result.get("total_time"),
                "result_quality": result.get("result_quality"),
                "user_satisfaction_predicted": result.get("user_satisfaction_predicted"),
                "learned_from_history": result.get("learned_from_history", False)
            }
            
        except Exception as e:
            return {
                "answer": f"Error: {str(e)}",
                "agent_used": None,
                "user_role": user_role,
                "success": False,
                "error": str(e)
            }
    
    def get_conversation_history(
        self,
        thread_id: str = "default",
        agent: str = "study"
    ) -> list:
        """Get conversation history from specific agent."""
        if agent == "study":
            return self.study_agent.get_conversation_history(thread_id=thread_id)
        elif agent == "grading":
            return self.grading_agent.get_conversation_history(thread_id=thread_id)
        return []
    
    async def aquery_stream(
        self,
        question: str,
        user_role: str = "student",
        thread_id: str = "default",
        user_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None
    ):
        """
        Streaming version of query method that yields chunks of the response.
        
        Args:
            Same as query method
            
        Yields:
            Chunks of the response as they become available
        """
        try:
            # Normalize role
            normalized_role = user_role.upper()
            if normalized_role in ["PROFESSOR", "INSTRUCTOR"]:
                normalized_role = "TEACHER"
            
            # Initial state
            initial_state: SupervisorState = {
                "question": question,
                "user_role": normalized_role,
                "user_id": user_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "assignment_name": assignment_name,
                "intent": None,
                "agent_choice": None,
                "access_denied": False,
                "routing_confidence": None,
                "agent_result": None,
                "agent_used": None,
                "final_answer": None,
                "routing_time": None,
                "agent_execution_time": None,
                "total_time": None,
                "routing_success": None,
                "routing_alternatives": [],
                "learned_from_history": False,
                "result_quality": None,
                "user_satisfaction_predicted": None,
                "context_used": None,
                "similar_past_queries": [],
                "streaming": True  # Flag to indicate streaming mode
            }
            
            # ⚡ OPTIMIZED: Use async methods for non-blocking routing
            state = await self.nodes.aenrich_context(initial_state)
            state = await self.nodes.aclassify_intent(state)
            state = await self.nodes.acheck_access(state)
            
            # If access denied, return error
            if state["access_denied"]:
                yield "⛔ Access Denied. Your role does not have permission to use this feature."
                return
                
            # Route to appropriate agent with streaming
            if state["agent_choice"] == "study_agent":
                # Use dedicated streaming study agent
                async for chunk in self.streaming_study_agent.aquery_stream(
                    question=question,
                    thread_id=thread_id
                ):
                    yield chunk
            
            elif state["agent_choice"] == "grading_agent":
                # Get streaming response from grading agent
                if hasattr(self.grading_agent, "aquery_stream"):
                    async for chunk in self.grading_agent.aquery_stream(
                        question=question,
                        thread_id=thread_id,
                        professor_id=user_id,
                        student_id=student_id,
                        student_name=student_name,
                        course_id=course_id,
                        assignment_id=assignment_id,
                        assignment_name=assignment_name
                    ):
                        yield chunk
                else:
                    # Fallback if streaming not implemented in grading agent
                    yield "Streaming not supported by grading agent. Please use non-streaming endpoint."
            
            # End of stream marker
            yield "[DONE]"
            
        except Exception as e:
            yield f"[ERROR] {str(e)}"
    
    def get_capabilities(self, user_role: str) -> Dict[str, list]:
        """Get capabilities available to user role."""
        capabilities = {
            "study_features": [
                "📚 Document Q&A",
                "🔍 Web Search",
                "🧮 Python REPL",
                "🎬 Manim Animation",
                "📝 Study Guides",
                "🎴 Flashcards",
                "❓ MCQ Generation"
            ],
            "grading_features": []
        }
        
        if user_role.lower() in ["teacher", "admin", "instructor", "professor"]:
            capabilities["grading_features"] = [
                "✍️ Essay Grading",
                "💻 Code Review",
                "📊 Rubric Evaluation",
                "💬 Feedback Generation",
                "✅ MCQ Autograding"
            ]
        
        return capabilities

