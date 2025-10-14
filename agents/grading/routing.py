"""Routing logic for Grading Agent."""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage

from .state import GradingAgentState
from utils import fast_grading_route, get_smart_context, MAX_CONTEXT_TOKENS


GRADING_SYSTEM_PROMPT = """You are a professional academic grading assistant helping teachers streamline their work.

CRITICAL - ALWAYS PROVIDE:
- **NUMERICAL GRADES FIRST** - Score, percentage, grade letter at the top
- Clear breakdown by criterion with specific scores
- Brief, honest feedback (100-250 words max)
- Specific examples of strengths and issues
- Actionable improvements

Remember: Help teachers grade efficiently with realistic, honest assessments."""


class GradingAgentRouter:
    """Tool routing for Grading Agent."""
    
    def __init__(self, llm):
        self.llm = llm
    
    def route_task(self, state: GradingAgentState) -> GradingAgentState:
        """Route grading task to appropriate tool."""
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        # Try pattern-based routing first
        quick_route = fast_grading_route(question)
        if quick_route:
            updated_messages = previous_messages + [HumanMessage(content=question)]
            return {**state, "tool_used": quick_route, "messages": updated_messages}
        
        # Fall back to LLM for ambiguous cases
        routing_prompt = """Determine the appropriate tool:

**Grading Tools:**
1. grade_essay - Text submissions (DEFAULT for ANY grading with scores)
2. review_code - Code/programming (with scores)
3. grade_mcq - Multiple choice only
4. evaluate_with_rubric - JSON format with rubric
5. generate_feedback - ONLY for feedback without grading/scoring

**Lesson Planning Tools (for teachers/professors):**
6. generate_lesson_plan - Create lesson plans
7. design_curriculum - Create course curriculum/syllabus
8. create_learning_objectives - Write learning objectives
9. design_assessment - Create quizzes/tests/exams
10. generate_study_materials - Create handouts/worksheets

**Google Classroom Tools (if enabled):**
11. fetch_classroom_courses - List Google Classroom courses
12. fetch_classroom_assignments - Get assignments from a course
13. fetch_classroom_submissions - Get student submissions for an assignment
14. get_classroom_submission_details - Get detailed submission info
15. post_grade_to_classroom - Post grade to Google Classroom
16. fetch_classroom_rubrics - Get rubrics for an assignment

IMPORTANT RULES:
- If user asks to "grade" or "evaluate" → use grade_essay (not generate_feedback)
- If user wants scores/grades → use grade_essay or review_code
- If user only wants feedback (no scoring) → use generate_feedback
- For plain text submissions → use grade_essay
- For code submissions → use review_code
- For educational planning → use lesson planning tools
- For Google Classroom interactions → use classroom tools

Respond with tool name only."""
        
        messages = [
            SystemMessage(content=GRADING_SYSTEM_PROMPT),
            SystemMessage(content=routing_prompt)
        ]
        
        smart_context = get_smart_context(previous_messages, max_tokens=MAX_CONTEXT_TOKENS)
        if smart_context:
            messages.extend(smart_context)
        
        messages.append(HumanMessage(content=question))
        
        response = self.llm.invoke(messages)
        tool_choice = response.content.strip().lower()
        
        # Grading tools
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
        # Lesson planning tools
        elif "lesson" in tool_choice or "plan" in tool_choice:
            tool_choice = "generate_lesson_plan"
        elif "curriculum" in tool_choice or "syllabus" in tool_choice:
            tool_choice = "design_curriculum"
        elif "objective" in tool_choice or "outcome" in tool_choice:
            tool_choice = "create_learning_objectives"
        elif "assessment" in tool_choice or "quiz" in tool_choice or "test" in tool_choice:
            tool_choice = "design_assessment"
        elif "material" in tool_choice or "handout" in tool_choice or "worksheet" in tool_choice:
            tool_choice = "generate_study_materials"
        # Google Classroom tools
        elif "fetch_classroom_courses" in tool_choice or "list courses" in tool_choice:
            tool_choice = "fetch_classroom_courses"
        elif "fetch_classroom_assignments" in tool_choice or "get assignments" in tool_choice:
            tool_choice = "fetch_classroom_assignments"
        elif "fetch_classroom_submissions" in tool_choice or "get submissions" in tool_choice:
            tool_choice = "fetch_classroom_submissions"
        elif "get_classroom_submission_details" in tool_choice or "submission details" in tool_choice:
            tool_choice = "get_classroom_submission_details"
        elif "fetch_submission_content" in tool_choice or "submission content" in tool_choice:
            tool_choice = "fetch_submission_content"
        elif "post_grade_to_classroom" in tool_choice or "post grade" in tool_choice:
            tool_choice = "post_grade_to_classroom"
        elif "fetch_classroom_rubrics" in tool_choice or "get rubrics" in tool_choice:
            tool_choice = "fetch_classroom_rubrics"
        elif "fetch_and_grade" in tool_choice:
            tool_choice = "fetch_and_grade"
        else:
            tool_choice = "generate_feedback"
        
        updated_messages = previous_messages + [HumanMessage(content=question)]
        return {**state, "tool_used": tool_choice, "messages": updated_messages}
    
    def route_to_tool(self, state: GradingAgentState) -> Literal[
        "essay", "code", "mcq", "rubric", "feedback",
        "lesson_plan", "curriculum", "objectives", "assessment", "materials",
        "classroom_courses", "classroom_assignments", "classroom_submissions",
        "classroom_submission_details", "submission_content", "fetch_and_grade", "classroom_post_grade", "classroom_rubrics"
    ]:
        """Conditional edge for tool routing."""
        tool = state["tool_used"]
        
        # Grading tools
        if tool == "grade_essay":
            return "essay"
        elif tool == "review_code":
            return "code"
        elif tool == "grade_mcq":
            return "mcq"
        elif tool == "evaluate_with_rubric":
            return "rubric"
        elif tool == "generate_feedback":
            return "feedback"
        # Lesson planning tools
        elif tool == "generate_lesson_plan":
            return "lesson_plan"
        elif tool == "design_curriculum":
            return "curriculum"
        elif tool == "create_learning_objectives":
            return "objectives"
        elif tool == "design_assessment":
            return "assessment"
        elif tool == "generate_study_materials":
            return "materials"
        # Google Classroom tools
        elif tool == "fetch_classroom_courses":
            return "classroom_courses"
        elif tool == "fetch_classroom_assignments":
            return "classroom_assignments"
        elif tool == "fetch_classroom_submissions":
            return "classroom_submissions"
        elif tool == "get_classroom_submission_details":
            return "classroom_submission_details"
        elif tool == "fetch_submission_content":
            return "submission_content"
        elif tool == "post_grade_to_classroom":
            return "classroom_post_grade"
        elif tool == "fetch_classroom_rubrics":
            return "classroom_rubrics"
        elif tool == "fetch_and_grade":
            return "fetch_and_grade"
        else:
            return "feedback"
    
    def complexity_router(self, state: GradingAgentState) -> Literal["plan", "route"]:
        """Route based on grading complexity."""
        if state.get("is_complex_grading", False):
            return "plan"
        return "route"
    
    def plan_execution_router(self, state: GradingAgentState) -> Literal["continue", "done"]:
        """Check plan execution progress."""
        grading_plan = state.get("grading_plan", [])
        current_step = state.get("current_grading_step", 0)
        
        if current_step < len(grading_plan):
            return "continue"
        return "done"
    
    def grading_reflection_router(self, state: GradingAgentState) -> Literal[
        "review", "improve", "finalize"
    ]:
        """Route based on self-reflection."""
        needs_review = state.get("needs_human_review", False)
        grading_confidence = state.get("grading_confidence", 1.0)
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 3)
        
        if needs_review and grading_confidence < 0.6:
            return "review"
        
        if grading_confidence < 0.7 and iteration < max_iterations:
            return "improve"
        
        return "finalize"

