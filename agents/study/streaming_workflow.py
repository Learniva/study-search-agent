"""
Streaming workflow for Study Agent.

This module provides a streaming-enabled workflow for the Study Agent,
allowing token-by-token streaming throughout the entire agent execution.
"""

from typing import Dict, Any

from utils.patterns.streaming import (
    StreamingStateGraph,
    StreamingState,
    END
)
from .state import StudyAgentState
from .streaming_nodes import StreamingStudyNodes


def build_streaming_workflow(llm, streaming_llm, tool_map: Dict[str, Any]) -> StreamingStateGraph:
    """
    Build streaming-enabled workflow for Study Agent.
    
    Args:
        llm: Regular LLM for non-streaming operations
        streaming_llm: Streaming-enabled LLM for streaming operations
        tool_map: Map of tool names to tool objects
        
    Returns:
        Compiled streaming workflow
    """
    # Create streaming graph
    workflow = StreamingStateGraph(StudyAgentState)
    
    # Initialize streaming nodes
    nodes = StreamingStudyNodes(llm, streaming_llm, tool_map)
    
    # Add streaming-enabled nodes
    workflow.add_node("detect_complexity", nodes.detect_complexity, streaming=True)
    workflow.add_node("plan_complex_task", nodes.plan_complex_task, streaming=True)
    workflow.add_node("execute_plan", nodes.execute_plan, streaming=True)
    workflow.add_node("synthesize_results", nodes.synthesize_results, streaming=True)
    workflow.add_node("self_reflect", nodes.self_reflect, streaming=True)
    
    # Tool execution nodes (streaming)
    workflow.add_node("document_qa", nodes._execute_document_qa, streaming=True)
    workflow.add_node("web_search", nodes._execute_web_search, streaming=True)
    workflow.add_node("python_repl", nodes._execute_python_repl, streaming=True)
    workflow.add_node("manim_animation", nodes._execute_manim_animation, streaming=True)
    
    # Set entry point
    workflow.set_entry_point("detect_complexity")
    
    # Add edges for complex path
    workflow.add_conditional_edges(
        "detect_complexity",
        lambda state: "plan_complex" if state.get("is_complex_task") else "route_simple",
        {"plan_complex": "plan_complex_task", "route_simple": "route_question"}
    )
    
    # Define routing function
    def route_to_tool(state):
        """Route to appropriate tool based on question."""
        question = state.get("question", "").lower()
        
        if "document" in question or "uploaded" in question or "notes" in question:
            return "document_qa"
        elif "code" in question or "calculate" in question or "compute" in question:
            return "python_repl"
        elif "animate" in question or "animation" in question or "visualize" in question:
            return "manim_animation"
        else:
            return "web_search"  # Default
    
    # Add routing node
    workflow.add_node("route_question", route_to_tool)
    
    # Add edges for complex task execution
    workflow.add_conditional_edges(
        "plan_complex_task",
        lambda state: "execute_step" if state.get("current_step", 0) < len(state.get("task_plan", [])) else "synthesize",
        {"execute_step": "execute_plan", "synthesize": "synthesize_results"}
    )
    
    workflow.add_conditional_edges(
        "execute_plan",
        lambda state: "execute_step" if state.get("current_step", 0) < len(state.get("task_plan", [])) else "synthesize",
        {"execute_step": "execute_plan", "synthesize": "synthesize_results"}
    )
    
    workflow.add_edge("synthesize_results", "self_reflect")
    
    # Add edges for simple path
    workflow.add_conditional_edges(
        "route_question",
        route_to_tool,
        {
            "document_qa": "document_qa",
            "web_search": "web_search",
            "python_repl": "python_repl",
            "manim_animation": "manim_animation",
        }
    )
    
    # Connect tools to self-reflection
    workflow.add_edge("document_qa", "self_reflect")
    workflow.add_edge("web_search", "self_reflect")
    workflow.add_edge("python_repl", "self_reflect")
    workflow.add_edge("manim_animation", "self_reflect")
    
    # Add conditional edges from self-reflection
    workflow.add_conditional_edges(
        "self_reflect",
        lambda state: "retry" if state.get("needs_retry") else "finish",
        {"retry": "route_question", "finish": END}
    )
    
    return workflow
