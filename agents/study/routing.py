"""Routing logic for Study Agent."""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage

from .state import StudyAgentState
from utils import fast_study_route


class StudyAgentRouter:
    """Tool routing for Study Agent."""
    
    def __init__(self, llm):
        self.llm = llm
    
    def route_question(self, state: StudyAgentState) -> StudyAgentState:
        """Analyze question and determine tool to use."""
        question = state["question"]
        previous_messages = state.get("messages", [])
        
        # Try pattern-based routing first (fast, no LLM call)
        quick_route = fast_study_route(question)
        if quick_route:
            updated_messages = previous_messages + [HumanMessage(content=question)]
            return {**state, "tool_used": quick_route, "messages": updated_messages}
        
        # Fall back to LLM for ambiguous cases
        routing_prompt = """Determine which tool to use:

Available tools:
1. Document_QA - Search uploaded documents
2. Python_REPL - Execute code/calculations
3. render_manim_video - Create animations
4. Web_Search - Internet search

Respond with ONLY the tool name."""
        
        messages = [
            SystemMessage(content=routing_prompt),
            *previous_messages[-4:],  # Recent context
            HumanMessage(content=question)
        ]
        
        response = self.llm.invoke(messages)
        tool_choice = response.content.strip()
        
        # Normalize tool name
        if "Document_QA" in tool_choice or "document" in tool_choice.lower():
            tool_choice = "Document_QA"
        elif "Python_REPL" in tool_choice or "python" in tool_choice.lower():
            tool_choice = "Python_REPL"
        elif "manim" in tool_choice.lower() or "animation" in tool_choice.lower():
            tool_choice = "render_manim_video"
        else:
            tool_choice = "Web_Search"
        
        updated_messages = previous_messages + [HumanMessage(content=question)]
        return {**state, "tool_used": tool_choice, "messages": updated_messages}
    
    def route_to_tool(self, state: StudyAgentState) -> Literal[
        "document_qa", "web_search", "python_repl", "manim_animation"
    ]:
        """Conditional edge function for tool routing."""
        tool = state["tool_used"]
        
        if tool == "Document_QA":
            return "document_qa"
        elif tool == "Python_REPL":
            return "python_repl"
        elif tool == "render_manim_video":
            return "manim_animation"
        else:
            return "web_search"
    
    def should_retry(self, state: StudyAgentState) -> Literal["retry", "finish"]:
        """Decide if retry with different tool is needed."""
        if state.get("document_qa_failed") and state.get("tried_document_qa"):
            if state.get("iteration", 0) < 2:
                return "retry"
        return "finish"
    
    def route_by_complexity(self, state: StudyAgentState) -> Literal["plan_complex", "route_simple"]:
        """Route based on task complexity."""
        if state.get("is_complex_task", False):
            return "plan_complex"
        return "route_simple"
    
    def check_plan_steps(self, state: StudyAgentState) -> Literal["execute_step", "synthesize", "fallback_to_simple"]:
        """Check plan execution progress."""
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if plan is None or not state.get("is_complex_task", False):
            return "fallback_to_simple"
        elif current_step < len(plan):
            return "execute_step"
        else:
            return "synthesize"
    
    def route_after_reflection(self, state: StudyAgentState) -> Literal["retry", "clarify", "finish"]:
        """Route based on self-reflection results."""
        if state.get("needs_retry", False):
            return "retry"
        elif state.get("needs_clarification", False):
            return "clarify"
        else:
            return "finish"

