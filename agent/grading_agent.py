"""
AI Grading Agent - For Teachers and Instructors

A specialized agent for grading and evaluating student work using:
- LangGraph: Multi-step grading workflow
- LangChain: RAG for rubric retrieval, document parsing
- Deep Learning/LLM Reasoning: Detailed evaluation and critique
- RAG/ML: Rubric retrieval for consistent, verifiable grading
- Generative AI: Structured output (scores, feedback text)

Capabilities:
- Essay grading with RAG-retrieved rubrics
- Code review and feedback
- MCQ auto-grading
- Rubric-based evaluation with ChromaDB
- Personalized feedback generation
- File processing for various submission types

AI Fundamentals Applied (per specification):
1. System Prompt: Defines role as detailed academic grader
2. Tool: Rubric Retrieval - RAG tool with ChromaDB for consistent grading
3. Tool: File Processor - Parse submissions (text, code, documents)
4. LLM Execution: Compare submission against rubric, generate scores/feedback

This agent is ONLY accessible to users with teacher/instructor roles.

Features PostgreSQL integration for:
- Long-term storage of grading history
- Professor configurations
- Rubric templates
- Audit logging
"""

import os
import time
from typing import Optional, TypedDict, Annotated, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from tools.grading_tools import get_all_grading_tools
from utils.llm import initialize_llm

# Database imports (optional - gracefully handle if not available)
try:
    from database.database import get_db, check_db_connection
    from database.operations import save_grading_session, log_audit, get_or_create_user
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("⚠️  Database module not available. Grading history will not be persisted.")

# Load environment variables
load_dotenv()


# SYSTEM PROMPT: Defines the AI Grading Agent's role
# AI Fundamental Applied: Strictly defines role as detailed academic grader
GRADING_AGENT_SYSTEM_PROMPT = """You are a detailed academic grader with expertise in evaluating student work across multiple disciplines.

YOUR ROLE:
- You are a professional, experienced educator
- You provide fair, consistent, and constructive grading
- You always use rubrics and clear criteria for evaluation
- You give specific, actionable feedback to help students improve
- You maintain high standards while being supportive

YOUR APPROACH:
1. Always provide a rubric or clear scoring criteria
2. Assign numerical scores (out of 100 or specified maximum)
3. Give constructive feedback with specific examples
4. Highlight both strengths and areas for improvement
5. Offer concrete suggestions for how to improve
6. Be objective, fair, and evidence-based in your assessments

YOUR OUTPUT MUST INCLUDE:
- A clear numerical score
- Detailed breakdown by criterion
- Specific feedback referencing the submission
- Both positive reinforcement and constructive criticism
- Suggestions for improvement

IMPORTANT GUIDELINES:
- Base all evaluations on the provided rubric and submission
- Be specific - cite examples from the student's work
- Be constructive - frame criticism as opportunities for growth
- Be fair - apply the same standards consistently
- Be thorough - address all criteria in the rubric
- Be professional - maintain an encouraging, educational tone

Remember: Your goal is to help students learn and improve, not just to assign grades."""


class GradingAgentState(TypedDict):
    """State for the grading agent with database persistence."""
    messages: Annotated[List[Any], add_messages]
    question: str
    tool_used: Optional[str]
    tool_result: Optional[str]
    final_answer: Optional[str]
    
    # Additional context for database storage
    professor_id: Optional[str]
    student_id: Optional[str]
    student_name: Optional[str]
    course_id: Optional[str]
    assignment_id: Optional[str]
    assignment_name: Optional[str]
    
    # Grading metadata
    grading_type: Optional[str]
    submission_data: Optional[Dict[str, Any]]
    ai_feedback_data: Optional[Dict[str, Any]]
    processing_start_time: Optional[float]


class GradingAgent:
    """
    AI Grading Agent powered by LangGraph.
    
    Capabilities:
    - Essay grading with customizable rubrics
    - Code review with style and correctness checking
    - MCQ auto-grading
    - Rubric-based evaluation
    - Constructive feedback generation
    
    Access: Teachers and instructors only
    """
    
    def __init__(self, llm_provider: str = "gemini", model_name: Optional[str] = None):
        """
        Initialize the AI Grading Agent.
        
        Args:
            llm_provider: LLM provider (default: gemini)
            model_name: Optional model name override
        """
        self.llm_provider = llm_provider.lower()
        # Use grading-optimized LLM (temperature=0.3 for precise, consistent evaluation)
        self.llm = initialize_llm(model_name=model_name, use_case="grading")
        self.tools = get_all_grading_tools()
        
        # Create tool lookup
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Initialize memory
        self.memory = MemorySaver()
        
        # Check database availability
        self.db_available = DATABASE_AVAILABLE
        if self.db_available:
            self.db_available = check_db_connection()
            if self.db_available:
                print("✅ Grading Agent: PostgreSQL connected - grading history will be persisted")
            else:
                print("⚠️  Grading Agent: PostgreSQL unavailable - grading history will not be persisted")
        
        # Build graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.memory)
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph for grading workflows.
        
        Graph structure:
        START → route_task → [essay | code | mcq | rubric | feedback] → format_result → END
        """
        workflow = StateGraph(GradingAgentState)
        
        # Add nodes
        workflow.add_node("route_task", self._route_task)
        workflow.add_node("grade_essay", self._grade_essay)
        workflow.add_node("review_code", self._review_code)
        workflow.add_node("grade_mcq", self._grade_mcq)
        workflow.add_node("evaluate_rubric", self._evaluate_rubric)
        workflow.add_node("generate_feedback", self._generate_feedback)
        workflow.add_node("format_result", self._format_result)
        
        # Set entry point
        workflow.set_entry_point("route_task")
        
        # Add conditional edges from router
        workflow.add_conditional_edges(
            "route_task",
            self._route_to_tool,
            {
                "essay": "grade_essay",
                "code": "review_code",
                "mcq": "grade_mcq",
                "rubric": "evaluate_rubric",
                "feedback": "generate_feedback"
            }
        )
        
        # All tool nodes go to formatter
        workflow.add_edge("grade_essay", "format_result")
        workflow.add_edge("review_code", "format_result")
        workflow.add_edge("grade_mcq", "format_result")
        workflow.add_edge("evaluate_rubric", "format_result")
        workflow.add_edge("generate_feedback", "format_result")
        
        # Format result goes to END
        workflow.add_edge("format_result", END)
        
        return workflow
    
    def _route_task(self, state: GradingAgentState) -> GradingAgentState:
        """
        Route the grading task to the appropriate tool.
        
        Uses the system prompt to maintain consistent academic grader role.
        """
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        routing_prompt = """Analyze this grading request and determine which tool to use:

Available grading tools:
1. grade_essay - For grading ANY text-based submissions (essays, reports, assignments, math problems)
   Use when: Request contains plain text submission, written work, math assignment, lab report
   Features: RAG rubric retrieval, handles all text formats automatically
   DEFAULT CHOICE for most grading requests

2. review_code - For code/programming submissions ONLY
   Use when: Submission contains Python, Java, C++, or other programming code
   Features: Code analysis, bug detection, style review

3. grade_mcq - For multiple choice questions ONLY
   Use when: Request explicitly mentions MCQ, quiz, or multiple choice answers

4. evaluate_with_rubric - ONLY when submission is in JSON format with explicit rubric
   Use when: Request provides BOTH submission AND rubric in JSON format
   NEVER use for plain text submissions

5. generate_feedback - For feedback-only requests (no grading)
   Use when: Explicit request for "feedback only", "comments only", no score needed

IMPORTANT: For plain text submissions (essays, math, reports), ALWAYS use grade_essay, NOT evaluate_with_rubric.

Respond with ONLY the tool name: grade_essay, review_code, grade_mcq, evaluate_with_rubric, or generate_feedback"""
        
        # Use the system prompt to define role
        messages = [
            SystemMessage(content=GRADING_AGENT_SYSTEM_PROMPT),
            SystemMessage(content=routing_prompt)
        ]
        
        # Add conversation context
        if previous_messages:
            messages.extend(previous_messages[-4:])
        
        messages.append(HumanMessage(content=question))
        
        response = self.llm.invoke(messages)
        tool_choice = response.content.strip().lower()
        
        # Normalize tool choice
        if "essay" in tool_choice:
            tool_choice = "grade_essay"
        elif "code" in tool_choice:
            tool_choice = "review_code"
        elif "mcq" in tool_choice:
            tool_choice = "grade_mcq"
        elif "rubric" in tool_choice:
            tool_choice = "evaluate_with_rubric"
        elif "feedback" in tool_choice:
            tool_choice = "generate_feedback"
        else:
            # Default to feedback generation
            tool_choice = "generate_feedback"
        
        print(f"\n📝 Grading task routed to: {tool_choice.replace('_', ' ').title()}")
        
        updated_messages = previous_messages + [HumanMessage(content=question)]
        
        return {
            **state,
            "tool_used": tool_choice,
            "messages": updated_messages
        }
    
    def _route_to_tool(self, state: GradingAgentState):
        """Conditional edge function for routing."""
        tool = state["tool_used"]
        
        if tool == "grade_essay":
            return "essay"
        elif tool == "review_code":
            return "code"
        elif tool == "grade_mcq":
            return "mcq"
        elif tool == "evaluate_with_rubric":
            return "rubric"
        else:
            return "feedback"
    
    def _grade_essay(self, state: GradingAgentState) -> GradingAgentState:
        """Execute essay grading tool."""
        print("✍️ Grading essay...")
        
        tool = self.tool_map.get("grade_essay")
        if not tool:
            return {
                **state,
                "tool_result": "Essay grading tool not available."
            }
        
        try:
            result = tool.func(state["question"])
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "tool_result": f"Error grading essay: {str(e)}"}
    
    def _review_code(self, state: GradingAgentState) -> GradingAgentState:
        """Execute code review tool."""
        print("💻 Reviewing code...")
        
        tool = self.tool_map.get("review_code")
        if not tool:
            return {
                **state,
                "tool_result": "Code review tool not available."
            }
        
        try:
            result = tool.func(state["question"])
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "tool_result": f"Error reviewing code: {str(e)}"}
    
    def _grade_mcq(self, state: GradingAgentState) -> GradingAgentState:
        """Execute MCQ grading tool."""
        print("✅ Grading MCQ answers...")
        
        tool = self.tool_map.get("grade_mcq")
        if not tool:
            return {
                **state,
                "tool_result": "MCQ grading tool not available."
            }
        
        try:
            result = tool.func(state["question"])
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "tool_result": f"Error grading MCQ: {str(e)}"}
    
    def _evaluate_rubric(self, state: GradingAgentState) -> GradingAgentState:
        """Execute rubric evaluation tool."""
        print("📋 Evaluating with rubric...")
        
        tool = self.tool_map.get("evaluate_with_rubric")
        if not tool:
            return {
                **state,
                "tool_result": "Rubric evaluation tool not available."
            }
        
        try:
            result = tool.func(state["question"])
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "tool_result": f"Error evaluating with rubric: {str(e)}"}
    
    def _generate_feedback(self, state: GradingAgentState) -> GradingAgentState:
        """Execute feedback generation tool."""
        print("💬 Generating feedback...")
        
        tool = self.tool_map.get("generate_feedback")
        if not tool:
            return {
                **state,
                "tool_result": "Feedback generation tool not available."
            }
        
        try:
            result = tool.func(state["question"])
            return {**state, "tool_result": result}
        except Exception as e:
            return {**state, "tool_result": f"Error generating feedback: {str(e)}"}
    
    def _format_result(self, state: GradingAgentState) -> GradingAgentState:
        """Format the grading result and save to database."""
        tool_result = state.get("tool_result", "No result generated")
        tool_used = state.get("tool_used", "Unknown")
        
        # Calculate processing time
        processing_time = None
        if state.get("processing_start_time"):
            processing_time = time.time() - state["processing_start_time"]
        
        # Save to database if available
        if self.db_available and state.get("professor_id"):
            try:
                with get_db() as db:
                    # Extract grading data from AI feedback
                    ai_feedback = state.get("ai_feedback_data", {})
                    score = ai_feedback.get("score") or ai_feedback.get("overall_score")
                    max_score = ai_feedback.get("max_score") or ai_feedback.get("total_possible") or 100
                    
                    # Ensure professor exists in database
                    get_or_create_user(
                        db=db,
                        user_id=state["professor_id"],
                        role="teacher"
                    )
                    
                    # Save grading session
                    save_grading_session(
                        db=db,
                        professor_id=state["professor_id"],
                        grading_type=state.get("grading_type", tool_used),
                        submission=state.get("submission_data", {"question": state.get("question")}),
                        ai_feedback=ai_feedback,
                        student_id=state.get("student_id"),
                        student_name=state.get("student_name"),
                        course_id=state.get("course_id"),
                        assignment_id=state.get("assignment_id"),
                        assignment_name=state.get("assignment_name"),
                        score=score,
                        max_score=max_score,
                        agent_used=tool_used,
                        processing_time=processing_time
                    )
                    
                    # Log audit entry
                    log_audit(
                        db=db,
                        user_id=state["professor_id"],
                        action_type=f"grade_{state.get('grading_type', 'unknown')}",
                        user_role="teacher",
                        resource_type="grading_session",
                        action_details={
                            "tool_used": tool_used,
                            "processing_time": processing_time
                        },
                        course_id=state.get("course_id"),
                        student_id=state.get("student_id"),
                        success=True
                    )
                    
                    print(f"✅ Grading session saved to database (processing time: {processing_time:.2f}s)")
            except Exception as e:
                print(f"⚠️  Failed to save grading session to database: {e}")
        
        # Add helpful footer
        footer = "\n\n" + "─" * 60
        footer += "\n⚠️  IMPORTANT REMINDER FOR TEACHERS:"
        footer += "\n   • This is an AI-generated evaluation"
        footer += "\n   • Please review and adjust the grade/feedback as needed"
        footer += "\n   • AI should assist, not replace, your professional judgment"
        footer += "\n   • Consider the context and individual student circumstances"
        if self.db_available:
            footer += "\n   • This grading session has been saved to your history"
        footer += "\n" + "─" * 60
        
        final_answer = tool_result + footer
        
        return {
            **state,
            "final_answer": final_answer,
            "messages": state["messages"] + [AIMessage(content=final_answer)]
        }
    
    def query(
        self, 
        question: str, 
        thread_id: str = "default",
        professor_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        assignment_name: Optional[str] = None
    ) -> str:
        """
        Process a grading request.
        
        Args:
            question: The grading request
            thread_id: Thread ID for conversation memory
            professor_id: Professor's user ID (for database storage)
            student_id: Student ID being graded
            student_name: Student name
            course_id: Course ID
            assignment_id: Assignment ID
            assignment_name: Assignment name
            
        Returns:
            The grading result
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get existing conversation history
            existing_messages = []
            try:
                state = self.app.get_state(config)
                if state and state.values:
                    existing_messages = state.values.get("messages", [])
            except Exception:
                pass
            
            # Initial state with database context
            initial_state = {
                "messages": existing_messages,
                "question": question,
                "tool_used": None,
                "tool_result": None,
                "final_answer": None,
                # Database context
                "professor_id": professor_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "assignment_name": assignment_name,
                # Metadata
                "processing_start_time": time.time(),
                "submission_data": {"question": question},
                "ai_feedback_data": {}
            }
            
            # Run the graph
            result = self.app.invoke(initial_state, config)
            
            return result.get("final_answer", "No result generated")
            
        except Exception as e:
            # Log error to database if available
            if self.db_available and professor_id:
                try:
                    with get_db() as db:
                        log_audit(
                            db=db,
                            user_id=professor_id,
                            action_type="grade_error",
                            user_role="teacher",
                            success=False,
                            error_message=str(e)
                        )
                except:
                    pass
            
            return f"Error processing grading request: {str(e)}"
    
    def get_conversation_history(self, thread_id: str = "default") -> List[Any]:
        """Get conversation history for a thread."""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.app.get_state(config)
            return state.values.get("messages", []) if state else []
        except Exception as e:
            print(f"Error retrieving history: {e}")
            return []
    
    def get_tool_info(self) -> Dict[str, str]:
        """Get information about available grading tools."""
        return {
            "grade_essay": "Grade essays and written assignments with detailed rubric-based feedback",
            "review_code": "Review code submissions for correctness, style, and best practices",
            "grade_mcq": "Automatically grade multiple choice questions",
            "evaluate_with_rubric": "Evaluate submissions against custom rubrics",
            "generate_feedback": "Generate personalized, constructive feedback for students"
        }
    
    def chat(self):
        """Interactive chat mode for grading agent."""
        print("=" * 70)
        print("📝 AI GRADING AGENT - Teacher Mode")
        print("=" * 70)
        print("\n✨ Grading Tools Available:")
        
        for tool_name, description in self.get_tool_info().items():
            print(f"  • {tool_name.replace('_', ' ').title()}: {description}")
        
        print("\n💡 Usage Examples:")
        print("  • 'Grade this essay: [paste essay]'")
        print("  • 'Review this Python code: [paste code]'")
        print("  • 'Grade MCQ - Student: A,B,C,A,D / Correct: A,C,C,A,D'")
        print("  • 'Provide feedback on this submission: [text]'")
        
        print("\n⚠️  Remember: AI grades are suggestions. Always review and adjust!")
        print("\nType 'quit' to exit\n")
        
        while True:
            try:
                question = input("\n📝 Grading request: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Happy grading!")
                    break
                
                if not question:
                    continue
                
                print("\n" + "=" * 70)
                answer = self.query(question)
                print("=" * 70)
                print(f"\n{answer}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Happy grading!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")


def main():
    """Test the grading agent in interactive mode."""
    print("\n🚀 Initializing AI Grading Agent...")
    agent = GradingAgent(llm_provider="gemini")
    agent.chat()


if __name__ == "__main__":
    main()

