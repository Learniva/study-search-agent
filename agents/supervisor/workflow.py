"""LangGraph workflow construction for Supervisor Agent."""

from langgraph.graph import StateGraph, END

from .state import SupervisorState
from .nodes import SupervisorAgentNodes
from .routing import SupervisorAgentRouter


def build_supervisor_workflow(llm, routing_history: list, routing_patterns: dict) -> StateGraph:
    """
    Build LangGraph workflow for Supervisor Agent.
    
    Flow:
    START → enrich_context → classify_intent → check_access 
         → [study_agent | grading_agent | deny_access]
         → evaluate_result → END
    """
    workflow = StateGraph(SupervisorState)
    
    # Initialize nodes and routing
    nodes = SupervisorAgentNodes(llm, routing_history, routing_patterns)
    router = SupervisorAgentRouter()
    
    # Note: Agent execution nodes will be added at runtime
    # because agents need to be lazy-loaded
    
    # Add core nodes
    workflow.add_node("enrich_context", nodes.enrich_context)
    workflow.add_node("classify_intent", nodes.classify_intent)
    workflow.add_node("check_access", nodes.check_access)
    workflow.add_node("deny_access", nodes.access_denied)
    workflow.add_node("evaluate_result", nodes.evaluate_result)
    
    # Set entry point
    workflow.set_entry_point("enrich_context")
    
    # Flow: enrich → classify → check
    workflow.add_edge("enrich_context", "classify_intent")
    workflow.add_edge("classify_intent", "check_access")
    
    # Conditional routing based on access
    # Note: study_agent and grading_agent nodes are added dynamically
    workflow.add_conditional_edges(
        "check_access",
        router.route_based_on_access,
        {
            "study": "study_agent",
            "grading": "grading_agent",
            "denied": "deny_access"
        }
    )
    
    # Agent nodes → evaluate
    # These edges are added after agent nodes are created
    
    # Terminal nodes
    workflow.add_edge("deny_access", END)
    workflow.add_edge("evaluate_result", END)
    
    return workflow, nodes

