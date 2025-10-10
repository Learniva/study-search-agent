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

from tools.grading import get_all_grading_tools
from utils import (
    initialize_llm,
    ResultCache,
    get_smart_context,
    fast_grading_route,
    DEFAULT_CACHE_TTL,
    MAX_GRADING_ITERATIONS,
    MAX_CONTEXT_TOKENS,
    GRADING_ERROR_INDICATORS,
    GRADING_UNCERTAINTY_INDICATORS,
    MIN_RESPONSE_LENGTH,
    MIN_TERM_OVERLAP_RATIO,
    GRADING_HIGH_CONFIDENCE,
    GRADING_MEDIUM_CONFIDENCE,
    GRADING_LOW_CONFIDENCE,
)

# Database imports (optional - gracefully handle if not available)
try:
    from database import get_db, check_db_connection, save_grading_session, log_audit, get_or_create_user
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("⚠️  Database module not available. Grading history will not be persisted.")

# Adaptive Rubric imports (optional - gracefully handle if not available)
try:
    from utils.ml import get_adaptive_rubric_manager
    ADAPTIVE_RUBRICS_AVAILABLE = True
    print("✅ Adaptive Rubrics feature loaded successfully")
except ImportError as e:
    ADAPTIVE_RUBRICS_AVAILABLE = False
    print(f"⚠️  Adaptive Rubrics not available: {e}")

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
    """
    Enhanced State for the grading agent with agentic capabilities and database persistence.
    Includes self-reflection, consistency checking, adaptive behavior, and multi-step planning.
    """
    messages: Annotated[List[Any], add_messages]
    question: str
    original_question: Optional[str]
    
    # Tool execution tracking
    tool_used: Optional[str]
    tool_result: Optional[str]
    tools_used_history: List[str]
    
    # Answer and grading tracking
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
    
    # NEW: Self-reflection & quality control for grading
    grading_confidence: Optional[float]  # Confidence in the assigned grade
    consistency_score: Optional[float]  # How consistent with past grading
    detected_issues: List[str]  # Potential issues in submission or grading
    needs_human_review: bool  # Whether professor should review this
    review_reasons: List[str]  # Why human review is recommended
    
    # NEW: Adaptive rubric and criteria
    rubric_used: Optional[Dict[str, Any]]  # Rubric applied
    adapted_rubric: bool  # Whether rubric was adapted from professor patterns
    criterion_scores: Optional[Dict[str, float]]  # Individual criterion scores
    
    # NEW: Intelligent feedback generation
    feedback_quality: Optional[float]  # Quality of generated feedback
    suggested_improvements: List[str]  # Suggestions for student improvement
    positive_highlights: List[str]  # Student's strengths
    
    # NEW: Error detection and correction
    potential_errors: List[Dict[str, Any]]  # Detected potential errors in submission
    auto_corrections: List[Dict[str, Any]]  # Automatic corrections made
    
    # NEW: Comparative analysis
    compared_to_average: Optional[bool]  # Whether compared to class average
    percentile_rank: Optional[float]  # Student's percentile in class
    
    # NEW: Multi-step planning for complex grading
    is_complex_grading: bool  # Flag for tasks requiring multiple tools
    grading_plan: Optional[List[Dict[str, Any]]]  # Step-by-step execution plan
    current_grading_step: int  # Track progress in plan
    completed_grading_steps: List[str]  # Steps already completed
    intermediate_grading_results: List[Dict[str, Any]]  # Results from each step
    
    # Iteration tracking
    iteration: int
    max_iterations: int


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
        
        # OPTIMIZATION: Initialize result cache using shared utility
        self.cache = ResultCache(ttl_seconds=DEFAULT_CACHE_TTL)
        
        # Check database availability
        self.db_available = DATABASE_AVAILABLE
        if self.db_available:
            self.db_available = check_db_connection()
            if self.db_available:
                print("✅ Grading Agent: PostgreSQL connected - grading history will be persisted")
            else:
                print("⚠️  Grading Agent: PostgreSQL unavailable - grading history will not be persisted")
        
        # Initialize adaptive rubric manager
        if ADAPTIVE_RUBRICS_AVAILABLE:
            self.rubric_manager = get_adaptive_rubric_manager()
            print("✅ Grading Agent: Adaptive Rubrics enabled - learning from professor feedback")
        else:
            self.rubric_manager = None
        
        # Build graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.memory)
    
    def _build_graph(self) -> StateGraph:
        """
        Build the enhanced LangGraph for grading workflows with agentic capabilities and multi-step planning.
        
        Enhanced Graph structure with multi-step planning, self-reflection and quality control:
        START → analyze_submission → detect_complexity → [simple | complex]
                        ↓                                     ↓         ↓
                 detect_issues                          route_task  plan_complex
                                                            ↓           ↓
                                                      [tools]    execute_plan (loop)
                                                            ↓           ↓
                                                        check_consistency
                                                                ↓
                                                        self_reflect_grade
                                                                ↓
                                        [needs_review | adjust_grade | finalize]
                                              ↓              ↓            ↓
                                     flag_for_review   improve_grade   format_result → END
        """
        workflow = StateGraph(GradingAgentState)
        
        # NEW: Add multi-step planning nodes
        workflow.add_node("detect_complexity", self._detect_grading_complexity)
        workflow.add_node("plan_complex", self._plan_complex_grading)
        workflow.add_node("execute_plan", self._execute_grading_plan)
        
        # NEW: Add agentic nodes for grading
        workflow.add_node("analyze_submission", self._analyze_submission)
        workflow.add_node("check_consistency", self._check_consistency)
        workflow.add_node("self_reflect_grade", self._self_reflect_grade)
        workflow.add_node("flag_for_review", self._flag_for_review)
        workflow.add_node("improve_grade", self._improve_grade)
        
        # Existing nodes
        workflow.add_node("route_task", self._route_task)
        workflow.add_node("grade_essay", self._grade_essay)
        workflow.add_node("review_code", self._review_code)
        workflow.add_node("grade_mcq", self._grade_mcq)
        workflow.add_node("evaluate_rubric", self._evaluate_rubric)
        workflow.add_node("generate_feedback", self._generate_feedback)
        workflow.add_node("format_result", self._format_result)
        
        # Set entry point to submission analysis
        workflow.set_entry_point("analyze_submission")
        
        # NEW: Analyze submission first, then detect complexity
        workflow.add_edge("analyze_submission", "detect_complexity")
        
        # NEW: Route based on complexity
        workflow.add_conditional_edges(
            "detect_complexity",
            self._complexity_router,
            {
                "plan": "plan_complex",  # Complex grading needs planning
                "route": "route_task"     # Simple grading goes to routing
            }
        )
        
        # NEW: After planning, execute the plan
        workflow.add_edge("plan_complex", "execute_plan")
        
        # NEW: Loop execute_plan until all steps done
        workflow.add_conditional_edges(
            "execute_plan",
            self._plan_execution_router,
            {
                "continue": "execute_plan",  # More steps to execute
                "done": "check_consistency"   # All steps complete
            }
        )
        
        # Add conditional edges from router (for simple grading)
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
        
        # NEW: All tool nodes go to consistency checker
        workflow.add_edge("grade_essay", "check_consistency")
        workflow.add_edge("review_code", "check_consistency")
        workflow.add_edge("grade_mcq", "check_consistency")
        workflow.add_edge("evaluate_rubric", "check_consistency")
        workflow.add_edge("generate_feedback", "check_consistency")
        
        # NEW: After consistency check, do self-reflection
        workflow.add_edge("check_consistency", "self_reflect_grade")
        
        # NEW: Route based on self-reflection
        workflow.add_conditional_edges(
            "self_reflect_grade",
            self._grading_reflection_router,
            {
                "review": "flag_for_review",  # Needs human review
                "improve": "improve_grade",  # Can be improved automatically
                "finalize": "format_result"  # Good to go
            }
        )
        
        # Flag for review and improve grade both go to formatter
        workflow.add_edge("flag_for_review", "format_result")
        workflow.add_edge("improve_grade", "format_result")
        
        # Format result goes to END
        workflow.add_edge("format_result", END)
        
        return workflow
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics from shared cache utility."""
        return self.cache.get_stats()
    
    
    
    def _route_task(self, state: GradingAgentState) -> GradingAgentState:
        """
        Route the grading task to the appropriate tool.
        
        OPTIMIZATION: Try pattern-based routing first (instant, no API call).
        Falls back to LLM for ambiguous cases.
        """
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        # OPTIMIZATION: Try pattern-based routing first (80-90% success rate)
        quick_route = fast_grading_route(question)
        if quick_route:
            updated_messages = previous_messages + [HumanMessage(content=question)]
            return {
                **state,
                "tool_used": quick_route,
                "messages": updated_messages
            }
        
        # Pattern routing failed - use LLM for complex/ambiguous cases
        print("🤔 Using LLM for grading routing (ambiguous request)")
        
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
        
        # OPTIMIZATION: Use smart context (2 messages max, configurable tokens)
        # OLD: messages.extend(previous_messages[-4:])  # Too much context!
        smart_context = get_smart_context(previous_messages, max_tokens=MAX_CONTEXT_TOKENS)
        if smart_context:
            messages.extend(smart_context)
        
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
    
    def _analyze_submission(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Analyze submission for potential issues before grading.
        
        Detects:
        - Plagiarism indicators
        - Formatting issues
        - Missing components
        - Incomplete submissions
        """
        question = state["question"]
        
        print("\n🔍 Analyzing Submission...")
        
        detected_issues = []
        potential_errors = []
        
        # Check for very short submissions
        if len(question) < 100:
            detected_issues.append("Submission is very short (< 100 characters)")
        
        # Check for common plagiarism indicators (simplified)
        plagiarism_indicators = [
            "http://", "https://", "www.",  # URLs might indicate copy-paste
            "© ", "copyright",  # Copyright symbols
        ]
        if any(indicator in question.lower() for indicator in plagiarism_indicators):
            detected_issues.append("Contains potential plagiarism indicators (URLs/copyright)")
        
        # Check for code/math without proper formatting
        if any(char in question for char in ["{", "}", "[", "]", "def ", "class "]):
            if "```" not in question and "code" not in question.lower():
                potential_errors.append({
                    "type": "formatting",
                    "description": "Code detected but not in code blocks",
                    "severity": "low"
                })
        
        print(f"   Detected {len(detected_issues)} issues, {len(potential_errors)} potential errors")
        
        return {
            **state,
            "original_question": question,
            "detected_issues": detected_issues,
            "potential_errors": potential_errors,
            "tools_used_history": [],
            "iteration": 0,
            "max_iterations": 3,
            "needs_human_review": False,
            "review_reasons": [],
            "suggested_improvements": [],
            "positive_highlights": [],
            "auto_corrections": [],
            "adapted_rubric": False
        }
    
    def _detect_grading_complexity(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Detect if grading task requires multi-step planning.
        
        Complex grading tasks include:
        - Multiple evaluation aspects (grade + rubric + feedback)
        - Comparative analysis (grade + compare to class average)
        - Multi-tool workflows (essay grader + feedback generator)
        """
        question = state["question"].lower()
        
        print("\n🔍 Detecting Grading Complexity...")
        
        # Multi-tool indicators
        multi_tool_indicators = [
            ("rubric" in question or "criteria" in question) and ("grade" in question or "evaluate" in question),
            ("feedback" in question or "comments" in question) and ("grade" in question),
            ("compare" in question or "average" in question) and ("grade" in question),
            question.count(" and ") >= 2,  # Multiple requirements
            "also" in question and ("grade" in question or "evaluate" in question),
        ]
        
        is_complex = any(multi_tool_indicators)
        
        if is_complex:
            print("   ✅ Complex grading task detected - multi-step planning required")
        else:
            print("   📝 Standard grading task - single tool workflow")
        
        return {
            **state,
            "is_complex_grading": is_complex,
            "current_grading_step": 0,
            "completed_grading_steps": [],
            "intermediate_grading_results": []
        }
    
    def _complexity_router(self, state: GradingAgentState) -> str:
        """Route based on grading complexity detection."""
        if state.get("is_complex_grading", False):
            return "plan"
        else:
            return "route"
    
    def _plan_complex_grading(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Create multi-step grading plan for complex tasks.
        
        Uses LLM to decompose complex grading into sequential steps.
        
        Example:
        Input: "Grade this essay, check it against the rubric, and provide detailed feedback"
        Plan:
        [
          {"step": 1, "description": "Grade essay", "tool": "grade_essay"},
          {"step": 2, "description": "Check rubric compliance", "tool": "evaluate_rubric"},
          {"step": 3, "description": "Generate detailed feedback", "tool": "generate_feedback"}
        ]
        """
        question = state["question"]
        
        print("\n📋 Planning Complex Grading Task...")
        
        planning_prompt = f"""You are a grading workflow planner. Break down this complex grading request into sequential steps.

Available grading tools:
- grade_essay: Grade text-based submissions (essays, reports, assignments)
- review_code: Review and grade code submissions
- grade_mcq: Auto-grade multiple choice questions
- evaluate_rubric: Evaluate submission against specific rubric
- generate_feedback: Generate detailed feedback and improvement suggestions

Request: {question}

Create a step-by-step plan in JSON format:
{{
  "steps": [
    {{"step": 1, "description": "Brief description", "tool": "tool_name"}},
    {{"step": 2, "description": "Brief description", "tool": "tool_name"}}
  ]
}}

Guidelines:
- Maximum 4 steps
- Each step should use ONE tool
- Steps should build on each other logically
- Focus on the grading workflow, not administrative tasks

Return ONLY the JSON plan, nothing else."""

        try:
            response = self.llm.invoke([HumanMessage(content=planning_prompt)])
            plan_text = response.content.strip()
            
            # Extract JSON from response
            import json
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
            plan_data = json.loads(plan_text)
            grading_plan = plan_data.get("steps", [])
            
            print(f"   ✅ Created {len(grading_plan)}-step grading plan:")
            for step in grading_plan:
                print(f"      Step {step['step']}: {step['description']} ({step['tool']})")
            
            return {
                **state,
                "grading_plan": grading_plan
            }
            
        except Exception as e:
            print(f"   ⚠️  Planning failed: {e}. Falling back to standard routing.")
            # Fallback: create simple single-step plan
            return {
                **state,
                "grading_plan": [{"step": 1, "description": "Grade submission", "tool": "grade_essay"}],
                "is_complex_grading": False  # Disable complex mode
            }
    
    def _execute_grading_plan(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Execute multi-step grading plan.
        
        Executes each step in the grading plan sequentially, passing
        context between steps.
        """
        grading_plan = state.get("grading_plan", [])
        current_step = state.get("current_grading_step", 0)
        intermediate_results = state.get("intermediate_grading_results", [])
        
        print(f"\n⚙️  Executing Grading Plan (Step {current_step + 1}/{len(grading_plan)})...")
        
        if current_step >= len(grading_plan):
            # All steps completed - synthesize final result
            print("   ✅ All grading steps completed. Synthesizing final result...")
            
            # Combine all intermediate results
            final_result = "\n\n---\n\n".join([
                f"**{r['step_description']}**\n{r['result']}"
                for r in intermediate_results
            ])
            
            return {
                **state,
                "tool_result": final_result,
                "final_answer": final_result
            }
        
        # Execute current step
        step = grading_plan[current_step]
        tool_name = step["tool"]
        step_description = step["description"]
        
        print(f"   Executing: {step_description}")
        print(f"   Tool: {tool_name}")
        
        # Build context from previous steps
        context_parts = [state["question"]]
        if intermediate_results:
            context_parts.append("\n\nPrevious results:")
            for prev_result in intermediate_results:
                context_parts.append(f"- {prev_result['step_description']}: {prev_result['result'][:200]}...")
        
        context = "\n".join(context_parts)
        
        # Execute tool
        try:
            tool = self.tool_map.get(tool_name)
            if not tool:
                result = f"Error: Tool '{tool_name}' not found"
            else:
                result = tool.invoke(context)
            
            # Store intermediate result
            intermediate_results.append({
                "step": current_step + 1,
                "step_description": step_description,
                "tool": tool_name,
                "result": result
            })
            
            completed_steps = state.get("completed_grading_steps", [])
            completed_steps.append(step_description)
            
            print(f"   ✅ Step {current_step + 1} completed")
            
            # Move to next step
            return {
                **state,
                "current_grading_step": current_step + 1,
                "completed_grading_steps": completed_steps,
                "intermediate_grading_results": intermediate_results,
                "tool_used": tool_name,
                "tool_result": result
            }
            
        except Exception as e:
            print(f"   ❌ Step {current_step + 1} failed: {e}")
            return {
                **state,
                "tool_result": f"Error executing {step_description}: {str(e)}",
                "current_grading_step": len(grading_plan)  # Skip remaining steps
            }
    
    def _plan_execution_router(self, state: GradingAgentState) -> str:
        """Route based on plan execution progress."""
        grading_plan = state.get("grading_plan", [])
        current_step = state.get("current_grading_step", 0)
        
        if current_step < len(grading_plan):
            return "continue"  # More steps to execute
        else:
            return "done"  # All steps completed
    
    def _check_consistency(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Check grading consistency with past grades.
        
        Compares this grade with historical grades from the same professor
        to ensure consistency.
        """
        tool_result = state.get("tool_result", "")
        professor_id = state.get("professor_id")
        grading_type = state.get("grading_type")
        
        print("\n📊 Checking Grading Consistency...")
        
        consistency_score = 1.0  # Default: fully consistent
        
        # Try to extract score from result
        import re
        score_match = re.search(r'Score:\s*(\d+)', tool_result)
        current_score = int(score_match.group(1)) if score_match else None
        
        # TODO: Compare with historical grades from database
        # For now, use simplified heuristic check
        
        if current_score:
            # Check if score seems reasonable
            if current_score > 100:
                consistency_score = 0.3
                print(f"   ⚠️  Score ({current_score}) exceeds maximum")
            elif current_score < 0:
                consistency_score = 0.3
                print(f"   ⚠️  Score ({current_score}) is negative")
            else:
                print(f"   ✅ Score ({current_score}) is within valid range")
        
        # Track tools used
        tools_used = state.get("tools_used_history", [])
        if state.get("tool_used"):
            tools_used.append(state["tool_used"])
        
        return {
            **state,
            "consistency_score": consistency_score,
            "tools_used_history": tools_used
        }
    
    def _self_reflect_grade(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Self-reflect on grading quality.
        
        Evaluates:
        - Confidence in the assigned grade
        - Completeness of feedback
        - Appropriateness of tone
        - Need for human review
        """
        tool_result = state.get("tool_result", "")
        detected_issues = state.get("detected_issues", [])
        consistency_score = state.get("consistency_score", 1.0)
        
        print("\n🤔 Self-Reflecting on Grading Quality...")
        
        grading_confidence = 1.0
        needs_review = False
        review_reasons = []
        
        # Check for detected issues in submission
        if detected_issues:
            grading_confidence -= 0.2 * min(len(detected_issues), 3)
            needs_review = True
            review_reasons.append(f"Submission has {len(detected_issues)} detected issues")
        
        # Check consistency
        if consistency_score < 0.7:
            grading_confidence -= 0.3
            needs_review = True
            review_reasons.append(f"Low consistency score ({consistency_score:.2f})")
        
        # Check feedback completeness
        required_sections = ["score", "feedback", "strengths", "improvement"]
        missing_sections = [s for s in required_sections if s.lower() not in tool_result.lower()]
        if missing_sections:
            grading_confidence -= 0.1 * len(missing_sections)
            review_reasons.append(f"Missing sections: {', '.join(missing_sections)}")
        
        # Check feedback length (should be substantive)
        if len(tool_result) < 200:
            grading_confidence -= 0.2
            needs_review = True
            review_reasons.append("Feedback is too brief")
        
        # Ensure confidence is in valid range
        grading_confidence = max(0.0, min(1.0, grading_confidence))
        
        # Extract score and create criterion scores (simplified)
        import re
        score_match = re.search(r'Score:\s*(\d+)(?:/(\d+))?', tool_result)
        if score_match:
            score = int(score_match.group(1))
            max_score = int(score_match.group(2)) if score_match.group(2) else 100
            
            # Create simplified criterion scores
            criterion_scores = {
                "overall": float(score) / max_score if max_score > 0 else 0.0
            }
        else:
            criterion_scores = {}
        
        # Generate suggested improvements and highlights
        suggested_improvements = []
        positive_highlights = []
        
        if grading_confidence < 0.8:
            suggested_improvements.append("Review and expand feedback sections")
        if detected_issues:
            suggested_improvements.append("Address detected issues in submission")
        
        print(f"   Grading Confidence: {grading_confidence:.2f}")
        print(f"   Needs Human Review: {needs_review}")
        if review_reasons:
            print(f"   Review Reasons: {', '.join(review_reasons)}")
        
        return {
            **state,
            "grading_confidence": grading_confidence,
            "needs_human_review": needs_review,
            "review_reasons": review_reasons,
            "criterion_scores": criterion_scores,
            "suggested_improvements": suggested_improvements,
            "positive_highlights": positive_highlights
        }
    
    def _grading_reflection_router(self, state: GradingAgentState) -> str:
        """Router for grading reflection results."""
        needs_review = state.get("needs_human_review", False)
        grading_confidence = state.get("grading_confidence", 1.0)
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 3)
        
        # Flag for human review if significant issues
        if needs_review and grading_confidence < 0.6:
            print(f"   ⚠️  Low confidence ({grading_confidence:.2f}), flagging for professor review")
            return "review"
        
        # Try to improve if low confidence but not critical
        if grading_confidence < 0.7 and iteration < max_iterations:
            print(f"   🔄 Moderate confidence ({grading_confidence:.2f}), attempting improvement")
            return "improve"
        
        # Otherwise finalize
        print(f"   ✅ Acceptable confidence ({grading_confidence:.2f}), finalizing grade")
        return "finalize"
    
    def _flag_for_review(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Flag grading for human review.
        
        Adds clear notices that professor should review this grading.
        """
        review_reasons = state.get("review_reasons", [])
        
        print("\n⚠️  Flagging for Human Review...")
        
        review_notice = "\n\n" + "="*60 + "\n"
        review_notice += "⚠️  **REQUIRES PROFESSOR REVIEW**\n"
        review_notice += "="*60 + "\n\n"
        review_notice += "This grading has been flagged for human review due to:\n"
        for i, reason in enumerate(review_reasons, 1):
            review_notice += f"  {i}. {reason}\n"
        review_notice += "\nPlease carefully review the AI's assessment and make necessary adjustments.\n"
        
        tool_result = state.get("tool_result", "")
        return {
            **state,
            "tool_result": tool_result + review_notice
        }
    
    def _improve_grade(self, state: GradingAgentState) -> GradingAgentState:
        """
        NEW AGENTIC NODE: Attempt to improve grading quality.
        
        Enriches feedback with additional details and suggestions.
        """
        tool_result = state.get("tool_result", "")
        suggested_improvements = state.get("suggested_improvements", [])
        iteration = state.get("iteration", 0)
        
        print(f"\n🔄 Improving Grading Quality (Iteration {iteration + 1})...")
        
        # Add suggested improvements if they're missing
        if suggested_improvements:
            improvement_section = "\n\n**Additional Improvement Suggestions:**\n"
            for i, suggestion in enumerate(suggested_improvements, 1):
                improvement_section += f"  {i}. {suggestion}\n"
            tool_result += improvement_section
        
        # Increment iteration
        return {
            **state,
            "tool_result": tool_result,
            "iteration": iteration + 1,
            "grading_confidence": min(1.0, state.get("grading_confidence", 0.7) + 0.1)
        }
    
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
        
        # Add agentic enhancements to footer
        footer = "\n\n" + "─" * 60
        
        # Add confidence score
        grading_confidence = state.get("grading_confidence")
        if grading_confidence is not None:
            confidence_emoji = "✅" if grading_confidence > 0.8 else "⚠️" if grading_confidence > 0.6 else "❌"
            footer += f"\n{confidence_emoji} AI Grading Confidence: {grading_confidence:.0%}"
        
        # Add consistency score
        consistency_score = state.get("consistency_score")
        if consistency_score and consistency_score < 1.0:
            footer += f"\n📊 Consistency Score: {consistency_score:.0%}"
        
        # Add detected issues if any
        detected_issues = state.get("detected_issues", [])
        if detected_issues:
            footer += "\n\n⚠️ Detected Issues in Submission:"
            for issue in detected_issues:
                footer += f"\n   • {issue}"
        
        # NEW: Add multi-step planning information
        is_complex = state.get("is_complex_grading", False)
        if is_complex:
            grading_plan = state.get("grading_plan", [])
            completed_steps = state.get("completed_grading_steps", [])
            if grading_plan:
                footer += "\n\n🔄 Multi-Step Grading Workflow Executed:"
                footer += f"\n   • Total Steps: {len(grading_plan)}"
                footer += f"\n   • Completed: {len(completed_steps)}"
                footer += "\n   • Steps:"
                for step in grading_plan:
                    status = "✅" if any(step["description"] in cs for cs in completed_steps) else "❌"
                    footer += f"\n      {status} Step {step['step']}: {step['description']} ({step['tool']})"
        
        footer += "\n\n⚠️  IMPORTANT REMINDER FOR TEACHERS:"
        footer += "\n   • This is an AI-generated evaluation"
        footer += "\n   • Please review and adjust the grade/feedback as needed"
        footer += "\n   • AI should assist, not replace, your professional judgment"
        footer += "\n   • Consider the context and individual student circumstances"
        
        # Add review flag if needed
        if state.get("needs_human_review"):
            footer += "\n   • ⚠️  This grading has been flagged for EXTRA CAREFUL REVIEW"
        
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
        
        OPTIMIZATION: Checks cache first for instant responses on repeated grading.
        
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
            # OPTIMIZATION: Check cache first (0ms vs 2-5s for cache hits)
            cache_key = self.cache.get_cache_key(question, thread_id)
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return cached_result
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get existing conversation history
            existing_messages = []
            try:
                state = self.app.get_state(config)
                if state and state.values:
                    existing_messages = state.values.get("messages", [])
            except Exception:
                pass
            
            # Initial state with database context and enhanced agentic fields
            initial_state = {
                # Messages and question
                "messages": existing_messages,
                "question": question,
                "original_question": question,
                
                # Tool execution
                "tool_used": None,
                "tool_result": None,
                "tools_used_history": [],
                
                # Answer
                "final_answer": None,
                
                # Database context
                "professor_id": professor_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "assignment_name": assignment_name,
                
                # Grading metadata
                "grading_type": None,
                "processing_start_time": time.time(),
                "submission_data": {"question": question},
                "ai_feedback_data": {},
                
                # Self-reflection & quality control
                "grading_confidence": None,
                "consistency_score": None,
                "detected_issues": [],
                "needs_human_review": False,
                "review_reasons": [],
                
                # Adaptive rubric and criteria
                "rubric_used": None,
                "adapted_rubric": False,
                "criterion_scores": None,
                
                # Intelligent feedback
                "feedback_quality": None,
                "suggested_improvements": [],
                "positive_highlights": [],
                
                # Error detection
                "potential_errors": [],
                "auto_corrections": [],
                
                # Comparative analysis
                "compared_to_average": None,
                "percentile_rank": None,
                
                # NEW: Multi-step planning
                "is_complex_grading": False,
                "grading_plan": None,
                "current_grading_step": 0,
                "completed_grading_steps": [],
                "intermediate_grading_results": [],
                
                # Iteration tracking
                "iteration": 0,
                "max_iterations": MAX_GRADING_ITERATIONS
            }
            
            # Run the graph
            result = self.app.invoke(initial_state, config)
            
            final_answer = result.get("final_answer", "No result generated")
            
            # OPTIMIZATION: Store in cache for future requests
            self.cache.set(cache_key, final_answer)
            
            return final_answer
            
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
    
    def record_professor_feedback(
        self,
        professor_id: str,
        rubric_type: str,
        ai_scores: Dict[str, float],
        professor_scores: Dict[str, float],
        overall_ai_score: Optional[float] = None,
        overall_professor_score: Optional[float] = None
    ):
        """
        Record professor feedback for adaptive rubric learning.
        
        Args:
            professor_id: Professor identifier
            rubric_type: Type of rubric (essay, code, etc.)
            ai_scores: AI's criterion scores
            professor_scores: Professor's corrected scores
            overall_ai_score: Overall AI score
            overall_professor_score: Overall professor score
        """
        if not ADAPTIVE_RUBRICS_AVAILABLE or self.rubric_manager is None:
            print("⚠️  Adaptive rubrics not available")
            return
        
        try:
            self.rubric_manager.record_grading(
                professor_id=professor_id,
                rubric_type=rubric_type,
                ai_scores=ai_scores,
                professor_scores=professor_scores,
                overall_ai_score=overall_ai_score,
                overall_professor_score=overall_professor_score
            )
            print(f"📊 Adaptive learning: Recorded professor feedback for {rubric_type}")
        except Exception as e:
            print(f"⚠️  Error recording feedback: {e}")
    
    def get_consistency_report(self, professor_id: str, grading_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get grading consistency report for a professor.
        
        Args:
            professor_id: Professor identifier
            grading_type: Optional filter by grading type
            
        Returns:
            Consistency report with metrics and recommendations
        """
        if not ADAPTIVE_RUBRICS_AVAILABLE or self.rubric_manager is None:
            return {"error": "Adaptive rubrics not available"}
        
        try:
            return self.rubric_manager.get_consistency_report(professor_id, grading_type)
        except Exception as e:
            return {"error": str(e)}
    
    def get_adapted_rubric(
        self,
        professor_id: str,
        rubric_type: str,
        base_rubric: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get rubric adapted to professor's grading patterns.
        
        Args:
            professor_id: Professor identifier
            rubric_type: Type of rubric
            base_rubric: Base rubric structure
            
        Returns:
            Adapted rubric with learned adjustments
        """
        if not ADAPTIVE_RUBRICS_AVAILABLE or self.rubric_manager is None:
            return base_rubric  # Return base rubric if adaptive not available
        
        try:
            adaptive_rubric = self.rubric_manager.get_or_create_rubric(
                professor_id=professor_id,
                rubric_type=rubric_type,
                base_rubric=base_rubric
            )
            return adaptive_rubric.get_adapted_rubric()
        except Exception as e:
            print(f"⚠️  Error getting adapted rubric: {e}")
            return base_rubric
    
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


    def grade_with_adaptation(
        self,
        submission: str,
        rubric: Optional[Dict[str, Any]] = None,
        assignment_type: str = "essay",
        professor_id: Optional[str] = None,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
        assignment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grade with Phase 3 adaptive features (if available).
        
        Uses adaptive grading workflow when professor_id is provided.
        Falls back to standard grading otherwise.
        
        Args:
            submission: Student submission text
            rubric: Grading rubric (optional)
            assignment_type: Type of assignment
            professor_id: Professor's ID for adaptive features
            student_id: Student's ID for personalization
            course_id: Optional course context
            assignment_id: Optional assignment identifier
        
        Returns:
            Dictionary with grade, feedback, and metadata
        """
        # Try to use adaptive grading workflow (Phase 3)
        if professor_id:
            try:
                from workflows.grading_workflow import AdaptiveGradingWorkflow
                
                if not hasattr(self, '_adaptive_workflow'):
                    self._adaptive_workflow = AdaptiveGradingWorkflow(self.llm)
                
                return self._adaptive_workflow.execute(
                    submission=submission,
                    rubric=rubric or {},
                    professor_id=professor_id,
                    assignment_type=assignment_type,
                    student_id=student_id
                )
            except ImportError:
                print("⚠️  Adaptive workflow not available, using standard grading")
        
        # Fallback to standard grading
        import json
        grading_request = json.dumps({
            "essay": submission,
            "assignment_type": assignment_type,
            "rubric": rubric
        })
        
        result = self.query(grading_request)
        
        return {
            "success": True,
            "grade": {"feedback": result},
            "adaptive_features": {"used_adaptive_rubric": False},
            "metadata": {"phase": "0"}
        }


def main():
    """Test the grading agent in interactive mode."""
    print("\n🚀 Initializing AI Grading Agent...")
    agent = GradingAgent(llm_provider="gemini")
    agent.chat()


if __name__ == "__main__":
    main()

