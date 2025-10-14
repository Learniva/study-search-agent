"""LangGraph workflow construction for Study Agent."""

from langgraph.graph import StateGraph, END

from .state import StudyAgentState
from .nodes import StudyAgentNodes
from .routing import StudyAgentRouter


def build_study_workflow(llm, tool_map: dict) -> StateGraph:
    """
    Build LangGraph workflow for Study Agent.
    
    Flow:
    START → detect_complexity → [simple | complex]
    Simple: route → tool → check → format → reflect → END
    Complex: plan → execute (loop) → synthesize → reflect → END
    """
    workflow = StateGraph(StudyAgentState)
    
    # Initialize nodes and routing
    nodes = StudyAgentNodes(llm, tool_map)
    router = StudyAgentRouter(llm)
    
    # Add nodes
    workflow.add_node("detect_complexity", nodes.detect_complexity)
    workflow.add_node("plan_complex_task", nodes.plan_complex_task)
    workflow.add_node("execute_plan", nodes.execute_plan)
    workflow.add_node("synthesize_results", nodes.synthesize_results)
    workflow.add_node("self_reflect", nodes.self_reflect)
    workflow.add_node("route_question", router.route_question)
    
    # Tool execution nodes
    workflow.add_node("document_qa", nodes._execute_document_qa)
    workflow.add_node("web_search", nodes._execute_web_search)
    workflow.add_node("python_repl", nodes._execute_python_repl)
    workflow.add_node("manim_animation", nodes._execute_manim_animation)
    
    # Format answer node
    def format_answer(state: StudyAgentState) -> StudyAgentState:
        tool_result = state.get("tool_result", "No result")
        tool_used = state.get("tool_used", "Unknown")
        
        if state.get("document_qa_failed") and state.get("tried_document_qa"):
            final_answer = f"Note: Document not found, searched web instead.\n\n{tool_result}"
        else:
            final_answer = tool_result
        
        from langchain_core.messages import AIMessage
        return {
            **state,
            "final_answer": final_answer,
            "messages": state["messages"] + [AIMessage(content=final_answer)]
        }
    
    workflow.add_node("format_answer", format_answer)
    
    # Check result node
    def check_result(state: StudyAgentState) -> StudyAgentState:
        return {**state, "iteration": state.get("iteration", 0) + 1}
    
    workflow.add_node("check_result", check_result)
    
    # Add user choice check node
    workflow.add_node("check_user_choice", nodes.check_user_choice)
    
    # Set entry point - check user choice first
    workflow.set_entry_point("check_user_choice")
    
    # Route from user choice check
    def route_after_choice_check(state: StudyAgentState) -> str:
        """Route after checking if user made a choice."""
        if state.get("user_choice_web_search"):
            return "handle_web_choice"
        elif state.get("user_choice_upload"):
            return "handle_upload_choice"
        else:
            return "detect_complexity"  # Continue normal flow
    
    # Add nodes for handling user choices
    def handle_web_search_choice(state: StudyAgentState) -> StudyAgentState:
        """Handle web search after user permission."""
        return {**state, "tool_used": "Web_Search"}
    
    def handle_upload_choice(state: StudyAgentState) -> StudyAgentState:
        """Handle upload choice."""
        return state  # tool_result already set in check_user_choice
    
    workflow.add_node("handle_web_choice", handle_web_search_choice)
    workflow.add_node("handle_upload_choice", handle_upload_choice)
    
    workflow.add_conditional_edges(
        "check_user_choice",
        route_after_choice_check,
        {
            "handle_web_choice": "handle_web_choice",
            "handle_upload_choice": "handle_upload_choice",
            "detect_complexity": "detect_complexity"
        }
    )
    
    # After user choice, go to appropriate tool
    workflow.add_edge("handle_web_choice", "web_search")
    workflow.add_edge("handle_upload_choice", "format_answer")
    
    # Complexity routing
    workflow.add_conditional_edges(
        "detect_complexity",
        router.route_by_complexity,
        {"plan_complex": "plan_complex_task", "route_simple": "route_question"}
    )
    
    # Complex path
    workflow.add_conditional_edges(
        "plan_complex_task",
        router.check_plan_steps,
        {
            "execute_step": "execute_plan",
            "synthesize": "synthesize_results",
            "fallback_to_simple": "route_question"
        }
    )
    
    workflow.add_conditional_edges(
        "execute_plan",
        router.check_plan_steps,
        {"execute_step": "execute_plan", "synthesize": "synthesize_results"}
    )
    
    workflow.add_edge("synthesize_results", "self_reflect")
    
    # Simple path
    workflow.add_conditional_edges(
        "route_question",
        router.route_to_tool,
        {
            "document_qa": "document_qa",
            "web_search": "web_search",
            "python_repl": "python_repl",
            "manim_animation": "manim_animation",
        }
    )
    
    workflow.add_edge("document_qa", "check_result")
    workflow.add_edge("web_search", "check_result")
    workflow.add_edge("python_repl", "check_result")
    workflow.add_edge("manim_animation", "check_result")
    
    workflow.add_conditional_edges(
        "check_result",
        router.should_retry,
        {"retry": "web_search", "finish": "format_answer"}
    )
    
    workflow.add_edge("format_answer", "self_reflect")
    
    # Self-reflection routing
    workflow.add_conditional_edges(
        "self_reflect",
        router.route_after_reflection,
        {"retry": "route_question", "clarify": END, "finish": END}
    )
    
    return workflow

