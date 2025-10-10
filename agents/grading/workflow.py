"""LangGraph workflow construction for Grading Agent."""

from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from .state import GradingAgentState
from .nodes import GradingAgentNodes
from .routing import GradingAgentRouter


def build_grading_workflow(llm, tool_map: dict) -> StateGraph:
    """
    Build LangGraph workflow for Grading Agent.
    
    Flow:
    START → analyze → detect_complexity → [simple | complex]
    Simple: route → tool → check → reflect → [review|improve|finalize]
    Complex: plan → execute (loop) → check → reflect → [review|improve|finalize]
    """
    workflow = StateGraph(GradingAgentState)
    
    # Initialize nodes and routing
    nodes = GradingAgentNodes(llm, tool_map)
    router = GradingAgentRouter(llm)
    
    # Add nodes
    workflow.add_node("analyze_submission", nodes.analyze_submission)
    workflow.add_node("detect_complexity", nodes.detect_grading_complexity)
    workflow.add_node("plan_complex", nodes.plan_complex_grading)
    workflow.add_node("execute_plan", nodes.execute_grading_plan)
    workflow.add_node("check_consistency", nodes.check_consistency)
    workflow.add_node("self_reflect_grade", nodes.self_reflect_grade)
    workflow.add_node("flag_for_review", nodes.flag_for_review)
    workflow.add_node("improve_grade", nodes.improve_grade)
    workflow.add_node("route_task", router.route_task)
    
    # Tool execution nodes
    def grade_essay(state: GradingAgentState) -> GradingAgentState:
        tool = tool_map.get("grade_essay")
        result = tool.func(state["question"]) if tool else "Essay grading unavailable"
        return {**state, "tool_result": result}
    
    def review_code(state: GradingAgentState) -> GradingAgentState:
        tool = tool_map.get("review_code")
        result = tool.func(state["question"]) if tool else "Code review unavailable"
        return {**state, "tool_result": result}
    
    def grade_mcq(state: GradingAgentState) -> GradingAgentState:
        tool = tool_map.get("grade_mcq")
        result = tool.func(state["question"]) if tool else "MCQ grading unavailable"
        return {**state, "tool_result": result}
    
    def evaluate_rubric(state: GradingAgentState) -> GradingAgentState:
        tool = tool_map.get("evaluate_with_rubric")
        result = tool.func(state["question"]) if tool else "Rubric evaluation unavailable"
        return {**state, "tool_result": result}
    
    def generate_feedback(state: GradingAgentState) -> GradingAgentState:
        tool = tool_map.get("generate_feedback")
        result = tool.func(state["question"]) if tool else "Feedback generation unavailable"
        return {**state, "tool_result": result}
    
    workflow.add_node("grade_essay", grade_essay)
    workflow.add_node("review_code", review_code)
    workflow.add_node("grade_mcq", grade_mcq)
    workflow.add_node("evaluate_rubric", evaluate_rubric)
    workflow.add_node("generate_feedback", generate_feedback)
    
    # Format result node
    def format_result(state: GradingAgentState) -> GradingAgentState:
        import time
        
        tool_result = state.get("tool_result", "No result")
        
        # Calculate processing time
        processing_time = None
        if state.get("processing_start_time"):
            processing_time = time.time() - state["processing_start_time"]
        
        # Add metadata footer
        footer = f"\n\n{'─' * 60}"
        
        grading_confidence = state.get("grading_confidence")
        if grading_confidence is not None:
            emoji = "✅" if grading_confidence > 0.8 else "⚠️" if grading_confidence > 0.6 else "❌"
            footer += f"\n{emoji} AI Confidence: {grading_confidence:.0%}"
        
        consistency_score = state.get("consistency_score")
        if consistency_score and consistency_score < 1.0:
            footer += f"\n📊 Consistency: {consistency_score:.0%}"
        
        detected_issues = state.get("detected_issues", [])
        if detected_issues:
            footer += "\n\n⚠️ Detected Issues:"
            for issue in detected_issues:
                footer += f"\n   • {issue}"
        
        is_complex = state.get("is_complex_grading", False)
        if is_complex:
            grading_plan = state.get("grading_plan", [])
            if grading_plan:
                footer += f"\n\n🔄 Multi-Step Workflow ({len(grading_plan)} steps)"
        
        footer += "\n\n⚠️  IMPORTANT:"
        footer += "\n   • AI-generated evaluation"
        footer += "\n   • Review and adjust as needed"
        footer += "\n   • Professional judgment required"
        
        if state.get("needs_human_review"):
            footer += "\n   • ⚠️  FLAGGED FOR EXTRA REVIEW"
        
        footer += f"\n{'─' * 60}"
        
        final_answer = tool_result + footer
        
        return {
            **state,
            "final_answer": final_answer,
            "messages": state["messages"] + [AIMessage(content=final_answer)]
        }
    
    workflow.add_node("format_result", format_result)
    
    # Set entry point
    workflow.set_entry_point("analyze_submission")
    
    # Flow: analyze → detect complexity
    workflow.add_edge("analyze_submission", "detect_complexity")
    
    # Complexity routing
    workflow.add_conditional_edges(
        "detect_complexity",
        router.complexity_router,
        {"plan": "plan_complex", "route": "route_task"}
    )
    
    # Complex path
    workflow.add_edge("plan_complex", "execute_plan")
    
    workflow.add_conditional_edges(
        "execute_plan",
        router.plan_execution_router,
        {"continue": "execute_plan", "done": "check_consistency"}
    )
    
    # Simple path
    workflow.add_conditional_edges(
        "route_task",
        router.route_to_tool,
        {
            "essay": "grade_essay",
            "code": "review_code",
            "mcq": "grade_mcq",
            "rubric": "evaluate_rubric",
            "feedback": "generate_feedback"
        }
    )
    
    # All tools → consistency check
    workflow.add_edge("grade_essay", "check_consistency")
    workflow.add_edge("review_code", "check_consistency")
    workflow.add_edge("grade_mcq", "check_consistency")
    workflow.add_edge("evaluate_rubric", "check_consistency")
    workflow.add_edge("generate_feedback", "check_consistency")
    
    # Consistency → self-reflection
    workflow.add_edge("check_consistency", "self_reflect_grade")
    
    # Reflection routing
    workflow.add_conditional_edges(
        "self_reflect_grade",
        router.grading_reflection_router,
        {
            "review": "flag_for_review",
            "improve": "improve_grade",
            "finalize": "format_result"
        }
    )
    
    # Review and improve → format
    workflow.add_edge("flag_for_review", "format_result")
    workflow.add_edge("improve_grade", "format_result")
    
    # Format → END
    workflow.add_edge("format_result", END)
    
    return workflow

