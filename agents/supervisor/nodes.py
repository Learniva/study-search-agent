"""LangGraph nodes for Supervisor Agent."""

import time
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

from .state import SupervisorState
from utils import fast_intent_classification, calculate_text_similarity


class SupervisorAgentNodes:
    """LangGraph node implementations for Supervisor Agent."""
    
    def __init__(self, llm, routing_history: list, routing_patterns: dict):
        self.llm = llm
        self.routing_history = routing_history
        self.routing_patterns = routing_patterns
    
    def enrich_context(self, state: SupervisorState) -> SupervisorState:
        """Enrich context with historical data."""
        question_lower = state["question"].lower()
        similar_queries = []
        
        for history_entry in self.routing_history[-20:]:
            similarity = calculate_text_similarity(
                question_lower,
                history_entry["question"].lower()
            )
            if similarity > 0.6:
                similar_queries.append({
                    "question": history_entry["question"],
                    "intent": history_entry["intent"],
                    "success": history_entry.get("success", True)
                })
        
        context_used = {
            "similar_queries_found": len(similar_queries),
            "routing_history_size": len(self.routing_history),
            "learned_patterns": list(self.routing_patterns.keys())
        }
        
        return {
            **state,
            "similar_past_queries": similar_queries,
            "context_used": context_used,
            "learned_from_history": len(similar_queries) > 0,
            "routing_alternatives": []
        }
    
    def classify_intent(self, state: SupervisorState) -> SupervisorState:
        """Classify user intent (STUDY or GRADE)."""
        question = state["question"]
        routing_start_time = time.time()
        
        # Check similar queries first
        similar_queries = state.get("similar_past_queries", [])
        if similar_queries:
            intent_votes = {}
            for sq in similar_queries:
                intent_votes[sq["intent"]] = intent_votes.get(sq["intent"], 0) + 1
            
            if intent_votes:
                predicted_intent = max(intent_votes, key=intent_votes.get)
                confidence = intent_votes[predicted_intent] / len(similar_queries)
                
                if confidence > 0.7:
                    routing_time = time.time() - routing_start_time
                    return {
                        **state,
                        "intent": predicted_intent,
                        "routing_confidence": confidence,
                        "routing_time": routing_time
                    }
        
        # Try pattern-based classification
        quick_intent = fast_intent_classification(question)
        if quick_intent:
            routing_time = time.time() - routing_start_time
            return {
                **state,
                "intent": quick_intent,
                "routing_confidence": 0.9,
                "routing_time": routing_time
            }
        
        # Fall back to LLM
        routing_prompt = """Analyze this request and determine intent:

Intents:
1. STUDY - Research, learning, Q&A, animations, study materials
2. GRADE - Grading student work, feedback, evaluation

Respond with: STUDY or GRADE"""
        
        messages = [
            SystemMessage(content=routing_prompt),
            HumanMessage(content=f"Request: {question}")
        ]
        
        response = self.llm.invoke(messages)
        intent = response.content.strip().upper()
        
        if "GRADE" in intent or "GRADING" in intent:
            intent = "GRADE"
        else:
            intent = "STUDY"
        
        routing_time = time.time() - routing_start_time
        
        return {
            **state,
            "intent": intent,
            "routing_confidence": 0.8,
            "routing_time": routing_time
        }
    
    def check_access(self, state: SupervisorState) -> SupervisorState:
        """Check access control based on role and intent."""
        user_role = state["user_role"].upper()
        intent = state["intent"]
        
        if intent == "GRADE":
            if user_role == "STUDENT":
                access_denied = True
                agent_choice = None
            elif user_role in ["TEACHER", "PROFESSOR", "INSTRUCTOR", "ADMIN"]:
                access_denied = False
                agent_choice = "grading_agent"
            else:
                access_denied = True
                agent_choice = None
        else:
            access_denied = False
            agent_choice = "study_agent"
        
        return {
            **state,
            "access_denied": access_denied,
            "agent_choice": agent_choice
        }
    
    def execute_study_agent(self, state: SupervisorState, study_agent) -> SupervisorState:
        """Execute Study Agent."""
        agent_start_time = time.time()
        
        answer = study_agent.query(
            question=state["question"],
            user_id=state.get("user_id")
        )
        
        agent_execution_time = time.time() - agent_start_time
        
        return {
            **state,
            "agent_result": answer,
            "agent_used": "Study Agent",
            "final_answer": answer,
            "agent_execution_time": agent_execution_time
        }
    
    def execute_grading_agent(self, state: SupervisorState, grading_agent) -> SupervisorState:
        """Execute Grading Agent."""
        agent_start_time = time.time()
        
        answer = grading_agent.query(
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
            "agent_used": "Grading Agent",
            "final_answer": answer,
            "agent_execution_time": agent_execution_time
        }
    
    def access_denied(self, state: SupervisorState) -> SupervisorState:
        """Return access denied message."""
        error_message = f"""🚫 Access Denied

You are logged in as: {state['user_role'].upper()}

Grading features are only available to:
- Teachers
- Professors
- Administrators

Students have access to:
📚 Study & Search features
🔍 Web Search
🧮 Python REPL
🎬 Animations

To access grading tools, use: python main.py --role professor"""
        
        return {
            **state,
            "agent_result": error_message,
            "agent_used": None,
            "final_answer": error_message
        }
    
    def evaluate_result(self, state: SupervisorState) -> SupervisorState:
        """Evaluate result quality and learn from routing decision."""
        routing_time = state.get("routing_time", 0.0)
        agent_execution_time = state.get("agent_execution_time", 0.0)
        total_time = routing_time + agent_execution_time
        
        answer = state.get("final_answer", "")
        result_quality = self._estimate_quality(answer)
        
        time_penalty = min(total_time / 10.0, 0.3)
        user_satisfaction_predicted = max(0.0, result_quality - time_penalty)
        
        routing_success = result_quality > 0.6 and not state.get("access_denied", False)
        
        # Add to history for learning
        self.routing_history.append({
            "question": state["question"],
            "intent": state.get("intent"),
            "agent_used": state.get("agent_used"),
            "success": routing_success,
            "quality": result_quality,
            "total_time": total_time,
            "timestamp": time.time()
        })
        
        # Keep only recent history
        if len(self.routing_history) > 100:
            self.routing_history[:] = self.routing_history[-100:]
        
        # Update patterns
        intent = state.get("intent")
        if intent and routing_success:
            if intent not in self.routing_patterns:
                self.routing_patterns[intent] = {"successes": 0, "total": 0}
            self.routing_patterns[intent]["successes"] += 1
            self.routing_patterns[intent]["total"] += 1
        
        return {
            **state,
            "total_time": total_time,
            "result_quality": result_quality,
            "user_satisfaction_predicted": user_satisfaction_predicted,
            "routing_success": routing_success
        }
    
    def _estimate_quality(self, answer: str) -> float:
        """Estimate answer quality based on heuristics."""
        if not answer:
            return 0.0
        
        score = 0.5
        length = len(answer)
        
        if 100 < length < 5000:
            score += 0.2
        elif length >= 5000:
            score += 0.1
        
        if any(m in answer for m in ["###", "##", "**", "---", "```"]):
            score += 0.1
        
        if any(w in answer.lower() for w in ["however", "therefore", "additionally"]):
            score += 0.1
        
        if "error" in answer.lower() or "failed" in answer.lower():
            score -= 0.2
        
        if "access denied" in answer.lower():
            score = 0.3
        
        return max(0.0, min(1.0, score))

