"""
Supervisor Agent - Multi-Agent Router
Uses the Supervisor Pattern to route between Study Agent and Grading Agent.

The supervisor:
1. Reads user request and role (student/teacher)
2. Classifies intent (study vs grading task)
3. Routes to appropriate specialized agent with LangGraph
4. Enforces role-based access control at the router node level
"""

import os
import time
from typing import Optional, TypedDict, Literal, Dict, Any, List
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from utils.llm import initialize_llm
from utils.routing import fast_intent_classification, calculate_text_similarity

# Load environment variables
load_dotenv()


class SupervisorState(TypedDict):
    """
    Enhanced LangGraph State Schema for Supervisor Agent.
    
    Includes user_role for role-based routing logic, performance tracking,
    and learning from routing decisions.
    """
    question: str
    user_role: str  # "STUDENT", "TEACHER", "PROFESSOR", "ADMIN"
    user_id: Optional[str]
    student_id: Optional[str]
    student_name: Optional[str]
    course_id: Optional[str]
    assignment_id: Optional[str]
    assignment_name: Optional[str]
    
    # Routing state
    intent: Optional[str]  # "STUDY" or "GRADE"
    agent_choice: Optional[str]  # "study_agent" or "grading_agent"
    access_denied: bool
    routing_confidence: Optional[float]  # Confidence in routing decision
    
    # Results
    agent_result: Optional[str]
    agent_used: Optional[str]
    final_answer: Optional[str]
    
    # NEW: Performance tracking
    routing_time: Optional[float]  # Time spent on routing
    agent_execution_time: Optional[float]  # Time spent in agent
    total_time: Optional[float]  # Total processing time
    
    # NEW: Learning and adaptation
    routing_success: Optional[bool]  # Whether routing was successful
    routing_alternatives: List[str]  # Alternative routing options considered
    learned_from_history: bool  # Whether historical data was used
    
    # NEW: Quality metrics
    result_quality: Optional[float]  # Quality score of result (0-1)
    user_satisfaction_predicted: Optional[float]  # Predicted user satisfaction
    
    # NEW: Context enrichment
    context_used: Optional[Dict[str, Any]]  # Additional context used for routing
    similar_past_queries: List[Dict[str, Any]]  # Similar queries from history


class SupervisorAgent:
    """
    Supervisor Agent using LangGraph for intelligent routing with role-based access control.
    
    Routes requests between:
    - Study & Search Agent: For all users (research, Q&A, animations, flashcards)
    - AI Grading Agent: For teachers only (grading, feedback, evaluation)
    
    Access Control (enforced in LangGraph router node):
    - Students: Can ONLY access Study Agent
    - Teachers: Can access BOTH agents
    - Admin: Can access BOTH agents
    
    LangGraph Flow:
    START → classify_intent → check_access → [study_agent | grading_agent | deny_access] → END
    """
    
    def __init__(self, llm_provider: str = "gemini", model_name: Optional[str] = None):
        """
        Initialize the Supervisor Agent with LangGraph and learning capabilities.
        
        OPTIMIZATION: Agents are lazy loaded (only when needed).
        
        Args:
            llm_provider: LLM provider for routing (default: gemini)
            model_name: Optional model name override
        """
        self.llm_provider = llm_provider.lower()
        self.model_name = model_name
        # Use routing-optimized LLM (temperature=0.0 for deterministic classification)
        self.llm = initialize_llm(model_name=model_name, use_case="routing")
        
        # OPTIMIZATION: Don't initialize agents - use lazy loading
        # OLD: self.study_agent = StudySearchAgent(...)  # Always loaded!
        self._study_agent = None
        self._grading_agent = None
        
        # NEW: Learning and adaptation
        self._routing_history = []  # Store recent routing decisions
        self._routing_patterns = {}  # Learn patterns from successful routings
        self._max_history = 100  # Keep last 100 routing decisions
        
        # Build LangGraph
        self.graph = self._build_graph()
    
    @property
    def study_agent(self):
        """
        Lazy load study agent (only when needed).
        
        OPTIMIZATION: Loads on first access, saving 1-2s startup time.
        """
        if self._study_agent is None:
            print("📚 Lazy loading Study Agent...")
            from agent.study_agent import StudySearchAgent
            self._study_agent = StudySearchAgent(
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
        return self._study_agent
    
    @property
    def grading_agent(self):
        """
        Lazy load grading agent (only when needed).
        
        OPTIMIZATION: Loads on first access, saving 1-2s startup time.
        """
        if self._grading_agent is None:
            print("📝 Lazy loading Grading Agent...")
            from agent.grading_agent import GradingAgent
            self._grading_agent = GradingAgent(
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
        return self._grading_agent
    
    def _build_graph(self) -> StateGraph:
        """
        Build Enhanced LangGraph for supervisor routing with learning and performance tracking.
        
        Graph structure:
        START → enrich_context → classify_intent → check_access → route_to_agent → evaluate_result → END
                                                         ↓
                                                   [study_agent | grading_agent | deny_access]
        """
        workflow = StateGraph(SupervisorState)
        
        # Add nodes
        workflow.add_node("enrich_context", self._enrich_context_node)
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("check_access", self._check_access_node)
        workflow.add_node("study_agent", self._study_agent_node)
        workflow.add_node("grading_agent", self._grading_agent_node)
        workflow.add_node("deny_access", self._access_denied_node)
        workflow.add_node("evaluate_result", self._evaluate_result_node)
        
        # Set entry point
        workflow.set_entry_point("enrich_context")
        
        # enrich_context → classify_intent
        workflow.add_edge("enrich_context", "classify_intent")
        
        # classify_intent → check_access
        workflow.add_edge("classify_intent", "check_access")
        
        # check_access → conditional routing
        workflow.add_conditional_edges(
            "check_access",
            self._route_based_on_access,
            {
                "study": "study_agent",
                "grading": "grading_agent",
                "denied": "deny_access"
            }
        )
        
        # Agent nodes → evaluate_result
        workflow.add_edge("study_agent", "evaluate_result")
        workflow.add_edge("grading_agent", "evaluate_result")
        
        # Terminal nodes
        workflow.add_edge("evaluate_result", END)
        workflow.add_edge("deny_access", END)
        
        return workflow.compile()
    
    
    def _enrich_context_node(self, state: SupervisorState) -> SupervisorState:
        """
        LangGraph Node: Enrich context with historical data and similar queries.
        
        NEW AGENTIC CAPABILITY: Learn from past routing decisions to improve accuracy.
        """
        start_time = time.time()
        
        question_lower = state["question"].lower()
        
        # Check for similar past queries
        similar_queries = []
        for history_entry in self._routing_history[-20:]:  # Check last 20 entries
            if calculate_text_similarity(question_lower, history_entry["question"].lower()) > 0.6:
                similar_queries.append({
                    "question": history_entry["question"],
                    "intent": history_entry["intent"],
                    "success": history_entry.get("success", True)
                })
        
        # Build context dictionary
        context_used = {
            "similar_queries_found": len(similar_queries),
            "routing_history_size": len(self._routing_history),
            "learned_patterns": list(self._routing_patterns.keys())
        }
        
        learned_from_history = len(similar_queries) > 0
        
        return {
            **state,
            "similar_past_queries": similar_queries,
            "context_used": context_used,
            "learned_from_history": learned_from_history,
            "routing_alternatives": []
        }
    
    
    def _classify_intent_node(self, state: SupervisorState) -> SupervisorState:
        """
        LangGraph Node: Classify the user's intent (STUDY or GRADE) with confidence scoring.
        
        OPTIMIZATION: Try pattern-based classification first (instant, no API call).
        Uses historical data for improved accuracy.
        Falls back to LLM for ambiguous cases.
        """
        question = state["question"]
        routing_start_time = time.time()
        
        # Check if similar queries suggest an intent
        similar_queries = state.get("similar_past_queries", [])
        if similar_queries:
            # Use majority vote from similar queries
            intent_votes = {}
            for sq in similar_queries:
                intent_votes[sq["intent"]] = intent_votes.get(sq["intent"], 0) + 1
            
            if intent_votes:
                predicted_intent = max(intent_votes, key=intent_votes.get)
                confidence = intent_votes[predicted_intent] / len(similar_queries)
                
                if confidence > 0.7:
                    print(f"🎯 Historical data suggests: {predicted_intent} (confidence: {confidence:.2f})")
                    routing_time = time.time() - routing_start_time
                    return {
                        **state,
                        "intent": predicted_intent,
                        "routing_confidence": confidence,
                        "routing_time": routing_time
                    }
        
        # OPTIMIZATION: Try pattern-based classification first (80-90% success rate)
        quick_intent = fast_intent_classification(question)
        if quick_intent:
            routing_time = time.time() - routing_start_time
            return {
                **state,
                "intent": quick_intent,
                "routing_confidence": 0.9,  # High confidence for pattern matches
                "routing_time": routing_time
            }
        
        # Pattern classification failed - use LLM for complex/ambiguous cases
        print("🤔 Using LLM for intent classification (ambiguous request)")
        
        routing_prompt = """Analyze this request and determine the intent:

Available intents:
1. STUDY - For research, learning, Q&A, animations, study materials
   Examples: "explain X", "what is Y", "generate MCQs", "create study guide", "animate Z"

2. GRADE - For grading student work, providing feedback, evaluation
   Examples: "grade this essay", "review this code", "evaluate this answer", "provide feedback on"

Respond with ONLY: STUDY or GRADE"""
        
        messages = [
            SystemMessage(content=routing_prompt),
            HumanMessage(content=f"Request: {question}")
        ]
        
        response = self.llm.invoke(messages)
        intent = response.content.strip().upper()
        
        # Normalize intent
        if "GRADE" in intent or "GRADING" in intent:
            intent = "GRADE"
        else:
            intent = "STUDY"
        
        print(f"🔍 Intent Classification: {intent}")
        
        routing_time = time.time() - routing_start_time
        
        return {
            **state,
            "intent": intent,
            "routing_confidence": 0.8,  # Medium-high confidence for LLM classification
            "routing_time": routing_time
        }
    
    def _check_access_node(self, state: SupervisorState) -> SupervisorState:
        """
        LangGraph Node: Check access control based on user_role and intent.
        
        Router Logic (as per specification):
        - If user_role == "STUDENT" and intent == "GRADE" → access_denied = True
        - If user_role == "PROFESSOR" and intent == "GRADE" → access_denied = False
        - If intent == "STUDY" → access_denied = False (all users can access)
        """
        user_role = state["user_role"].upper()
        intent = state["intent"]
        
        print(f"🔐 Access Check: Role={user_role}, Intent={intent}")
        
        # Router Logic: Check user_role BEFORE routing
        if intent == "GRADE":
            # Check if user has permission to grade
            if user_role == "STUDENT":
                # Access Denied: Students cannot grade
                access_denied = True
                agent_choice = None
                print("❌ Access Check: DENIED (Student cannot access grading tools)")
            elif user_role in ["TEACHER", "PROFESSOR", "INSTRUCTOR", "ADMIN"]:
                # Access Granted: Teachers/Professors can grade
                access_denied = False
                agent_choice = "grading_agent"
                print("✅ Access Check: GRANTED (Teacher can access grading tools)")
            else:
                # Unknown role, deny by default
                access_denied = True
                agent_choice = None
                print("❌ Access Check: DENIED (Unknown role)")
        else:
            # STUDY intent: All users can access
            access_denied = False
            agent_choice = "study_agent"
            print("✅ Access Check: GRANTED (Study tools available to all)")
        
        return {
            **state,
            "access_denied": access_denied,
            "agent_choice": agent_choice
        }
    
    def _route_based_on_access(self, state: SupervisorState) -> Literal["study", "grading", "denied"]:
        """
        Conditional edge function: Route based on access control result.
        """
        if state["access_denied"]:
            return "denied"
        elif state["agent_choice"] == "study_agent":
            return "study"
        elif state["agent_choice"] == "grading_agent":
            return "grading"
        else:
            return "denied"
    
    def _study_agent_node(self, state: SupervisorState) -> SupervisorState:
        """LangGraph Node: Execute Study Agent with ML tracking and performance measurement."""
        print("📚 Routing to Study Agent...")
        
        agent_start_time = time.time()
        
        # Pass user_id to enable ML tracking and learning features
        answer = self.study_agent.query(
            question=state["question"],
            user_id=state.get("user_id")  # Enable ML tracking if user_id provided
        )
        
        agent_execution_time = time.time() - agent_start_time
        
        return {
            **state,
            "agent_result": answer,
            "agent_used": "Study & Search Agent",
            "final_answer": answer,
            "agent_execution_time": agent_execution_time
        }
    
    def _grading_agent_node(self, state: SupervisorState) -> SupervisorState:
        """LangGraph Node: Execute Grading Agent with performance measurement."""
        print("📝 Routing to Grading Agent...")
        
        agent_start_time = time.time()
        
        answer = self.grading_agent.query(
            question=state["question"],
            professor_id=state.get("user_id"),
            student_id=state.get("student_id"),
            student_name=state.get("student_name"),
            course_id=state.get("course_id"),
            assignment_id=state.get("assignment_id"),
            assignment_name=state.get("assignment_name")
        )
        
        agent_execution_time = time.time() - agent_start_time
        
        return {
            **state,
            "agent_result": answer,
            "agent_used": "AI Grading Agent",
            "final_answer": answer,
            "agent_execution_time": agent_execution_time
        }
    
    def _access_denied_node(self, state: SupervisorState) -> SupervisorState:
        """
        LangGraph Node: Access Denied.
        
        Returns error message when student tries to access grading tools.
        """
        print("🚫 Access Denied Node: Returning error message")
        
        error_message = """🚫 Access Denied

[Access Denied Node]: Error: Grading tool restricted to Professors.

You are currently logged in as: {role}

The grading features are only available to:
- Teachers
- Professors
- Instructors
- Administrators

Students have access to:
📚 Study & Search features
🔍 Web Search
🧮 Python REPL
🎬 Animations
📝 Study Guides
🎴 Flashcards

If you believe you should have access to grading tools, please contact your administrator or use the correct role when starting the application:

    python main.py --role professor
""".format(role=state["user_role"].upper())
        
        return {
            **state,
            "agent_result": error_message,
            "agent_used": None,
            "final_answer": error_message
        }
    
    def _evaluate_result_node(self, state: SupervisorState) -> SupervisorState:
        """
        LangGraph Node: Evaluate the result quality and learn from the routing decision.
        
        NEW AGENTIC CAPABILITY: Self-assessment and continuous learning.
        """
        # Calculate total time
        routing_time = state.get("routing_time", 0.0)
        agent_execution_time = state.get("agent_execution_time", 0.0)
        total_time = routing_time + agent_execution_time
        
        # Estimate result quality based on response length and structure
        answer = state.get("final_answer", "")
        result_quality = self._estimate_result_quality(answer)
        
        # Predict user satisfaction based on quality and time
        # Fast responses with high quality = high satisfaction
        time_penalty = min(total_time / 10.0, 0.3)  # Max 30% penalty for slow responses
        user_satisfaction_predicted = max(0.0, result_quality - time_penalty)
        
        # Determine routing success
        routing_success = result_quality > 0.6 and not state.get("access_denied", False)
        
        # Add to routing history for learning
        history_entry = {
            "question": state["question"],
            "intent": state.get("intent"),
            "agent_used": state.get("agent_used"),
            "success": routing_success,
            "quality": result_quality,
            "total_time": total_time,
            "timestamp": time.time()
        }
        
        self._routing_history.append(history_entry)
        
        # Keep only recent history
        if len(self._routing_history) > self._max_history:
            self._routing_history = self._routing_history[-self._max_history:]
        
        # Update routing patterns
        intent = state.get("intent")
        if intent and routing_success:
            if intent not in self._routing_patterns:
                self._routing_patterns[intent] = {"successes": 0, "total": 0}
            self._routing_patterns[intent]["successes"] += 1
            self._routing_patterns[intent]["total"] += 1
        
        print(f"\n📊 Performance Metrics:")
        print(f"   Routing Time: {routing_time:.3f}s")
        print(f"   Agent Execution: {agent_execution_time:.3f}s")
        print(f"   Total Time: {total_time:.3f}s")
        print(f"   Result Quality: {result_quality:.2f}")
        print(f"   Predicted Satisfaction: {user_satisfaction_predicted:.2f}")
        
        return {
            **state,
            "total_time": total_time,
            "result_quality": result_quality,
            "user_satisfaction_predicted": user_satisfaction_predicted,
            "routing_success": routing_success
        }
    
    def _estimate_result_quality(self, answer: str) -> float:
        """
        Estimate the quality of the answer based on simple heuristics.
        
        Returns a score from 0 to 1.
        """
        if not answer:
            return 0.0
        
        score = 0.5  # Base score
        
        # Length check (not too short, not excessively long)
        length = len(answer)
        if 100 < length < 5000:
            score += 0.2
        elif length >= 5000:
            score += 0.1
        
        # Structure indicators
        if any(marker in answer for marker in ["###", "##", "**", "---", "```"]):
            score += 0.1  # Has formatting
        
        if any(word in answer.lower() for word in ["however", "therefore", "additionally", "specifically"]):
            score += 0.1  # Has connecting words
        
        # Error indicators (reduce score)
        if "error" in answer.lower() or "failed" in answer.lower():
            score -= 0.2
        
        if "access denied" in answer.lower():
            score = 0.3  # Low score for access denied
        
        return max(0.0, min(1.0, score))
    
    
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
        Main entry point for supervisor agent using LangGraph.
        
        The LangGraph will:
        1. Classify intent (STUDY or GRADE)
        2. Check access based on user_role
        3. Route to appropriate agent or access denied node
        
        Args:
            question: User's question
            user_role: User's role (student/teacher/admin)
            thread_id: Conversation thread ID
            user_id: User ID for database tracking
            student_id: Student ID being graded
            student_name: Student name
            course_id: Course ID
            assignment_id: Assignment ID
            assignment_name: Assignment name
            
        Returns:
            Dictionary with answer and metadata
        """
        print(f"\n{'='*70}")
        print(f"🎯 SUPERVISOR AGENT (LangGraph)")
        print(f"   Role: {user_role.upper()}")
        print(f"   Question: {question[:60]}{'...' if len(question) > 60 else ''}")
        print(f"{'='*70}\n")
        
        try:
            # Normalize role to uppercase for state
            normalized_role = user_role.upper()
            if normalized_role in ["PROFESSOR", "INSTRUCTOR"]:
                normalized_role = "TEACHER"
            
            # Initial state for LangGraph (with new agentic fields)
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
                # NEW: Performance tracking
                "routing_time": None,
                "agent_execution_time": None,
                "total_time": None,
                # NEW: Learning and adaptation
                "routing_success": None,
                "routing_alternatives": [],
                "learned_from_history": False,
                # NEW: Quality metrics
                "result_quality": None,
                "user_satisfaction_predicted": None,
                # NEW: Context enrichment
                "context_used": None,
                "similar_past_queries": []
            }
            
            # Run the LangGraph
            result = self.graph.invoke(initial_state)
            
            print(f"\n{'='*70}")
            if result.get("agent_used"):
                print(f"✅ Completed by: {result['agent_used']}")
            else:
                print(f"❌ Access Denied")
            print(f"{'='*70}\n")
            
            # Return standardized response with performance metrics
            return {
                "answer": result["final_answer"],
                "agent_used": result.get("agent_used"),
                "user_role": user_role,
                "success": not result["access_denied"],
                # NEW: Performance and quality metrics
                "routing_confidence": result.get("routing_confidence"),
                "total_time": result.get("total_time"),
                "result_quality": result.get("result_quality"),
                "user_satisfaction_predicted": result.get("user_satisfaction_predicted"),
                "learned_from_history": result.get("learned_from_history", False)
            }
            
        except Exception as e:
            error_msg = f"❌ Supervisor Error: {str(e)}"
            print(error_msg)
            
            return {
                "answer": f"I encountered an error processing your request: {str(e)}",
                "agent_used": None,
                "user_role": user_role,
                "success": False,
                "error": str(e)
            }
    
    def get_conversation_history(self, thread_id: str = "default", agent: str = "study") -> list:
        """
        Get conversation history from a specific agent.
        
        Args:
            thread_id: Conversation thread ID
            agent: Which agent's history ("study" or "grading")
            
        Returns:
            List of conversation messages
        """
        if agent == "study":
            return self.study_agent.get_conversation_history(thread_id=thread_id)
        elif agent == "grading":
            return self.grading_agent.get_conversation_history(thread_id=thread_id)
        else:
            return []
    
    def visualize_architecture(self) -> str:
        """Return a reference to the system architecture documentation."""
        return """
System Architecture Documentation
==================================

For a comprehensive view of the Multi-Agent System architecture, please see:
    docs/SYSTEM_ARCHITECTURE.md

This includes:
  • Complete system diagrams
  • Component details and flows
  • LangGraph workflows
  • Role-based access control
  • Technology stack
  • Performance optimizations
  • Data flow examples

Quick Summary:
  ✓ Supervisor Agent routes between Study and Grading agents
  ✓ Role-based access control (Students → Study only, Teachers → Both)
  ✓ LangGraph workflows for multi-step processing
  ✓ Lazy loading and performance optimizations
  ✓ Centralized error handling
"""
    
    def get_capabilities(self, user_role: str) -> Dict[str, list]:
        """
        Get list of capabilities available to user based on role.
        
        Args:
            user_role: User's role
            
        Returns:
            Dictionary of available capabilities
        """
        capabilities = {
            "study_features": [
                "📚 Document Q&A - Ask questions about uploaded study materials",
                "🔍 Web Search - Real-time research on any topic",
                "🧮 Python REPL - Execute code and solve math problems",
                "🎬 Manim Animation - Create educational animations",
                "📝 Study Guides - Generate comprehensive study materials",
                "🎴 Flashcards - Create flashcard sets for memorization",
                "❓ MCQ Generation - Generate practice questions"
            ],
            "grading_features": []
        }
        
        # Add grading features for teachers
        if user_role.lower() in ["teacher", "admin", "instructor", "professor"]:
            capabilities["grading_features"] = [
                "✍️ Essay Grading - AI-powered essay evaluation with rubrics",
                "💻 Code Review - Automated code review and feedback",
                "📊 Rubric Evaluation - Grade submissions against custom rubrics",
                "💬 Feedback Generation - Generate constructive student feedback",
                "✅ MCQ Autograding - Automatically grade multiple choice questions",
                "🔍 Answer Comparison - Compare student answers to model answers"
            ]
        
        return capabilities
    
    def chat(self, user_role: str = "student"):
        """
        Interactive chat mode with supervisor routing.
        
        Args:
            user_role: User's role (student/teacher)
        """
        print("=" * 70)
        print("🎓 MULTI-AGENT STUDY & GRADING ASSISTANT")
        print("=" * 70)
        print(f"\n👤 Role: {user_role.upper()}")
        print("\n✨ Powered by Supervisor Pattern + LangGraph")
        
        # Show available capabilities
        capabilities = self.get_capabilities(user_role)
        
        print("\n📚 STUDY FEATURES (Available to all users):")
        for feature in capabilities["study_features"]:
            print(f"   {feature}")
        
        if capabilities["grading_features"]:
            print("\n📝 GRADING FEATURES (Teachers only):")
            for feature in capabilities["grading_features"]:
                print(f"   {feature}")
        
        print("\n💡 Special commands:")
        print("   'arch' - Show architecture diagram")
        print("   'caps' - Show your capabilities")
        print("   'role: <role>' - Change role (for testing)")
        print("   'quit', 'exit', 'q' - End session\n")
        
        current_role = user_role
        
        while True:
            try:
                question = input("\n🤔 Your request: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Happy teaching and learning!")
                    break
                
                if question.lower() == 'arch':
                    print(self.visualize_architecture())
                    continue
                
                if question.lower() == 'caps':
                    caps = self.get_capabilities(current_role)
                    print(f"\n📋 Capabilities for {current_role.upper()}:")
                    print("\nStudy Features:")
                    for f in caps["study_features"]:
                        print(f"  {f}")
                    if caps["grading_features"]:
                        print("\nGrading Features:")
                        for f in caps["grading_features"]:
                            print(f"  {f}")
                    continue
                
                if question.lower().startswith('role:'):
                    new_role = question.split(':', 1)[1].strip()
                    current_role = new_role
                    print(f"✅ Role changed to: {current_role.upper()}")
                    caps = self.get_capabilities(current_role)
                    print(f"   Available features: {len(caps['study_features']) + len(caps['grading_features'])}")
                    continue
                
                if not question:
                    continue
                
                # Process request through supervisor
                result = self.query(question, user_role=current_role)
                
                if result["success"]:
                    print(f"\n✅ {result['agent_used']}:")
                    print(f"{result['answer']}\n")
                else:
                    print(f"\n{result['answer']}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Happy teaching and learning!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")


def main():
    """Test the supervisor agent in interactive mode."""
    import sys
    
    # Get role from command line or default to student
    role = sys.argv[1] if len(sys.argv) > 1 else "student"
    
    supervisor = SupervisorAgent(llm_provider="gemini")
    supervisor.chat(user_role=role)


if __name__ == "__main__":
    main()

