"""Shared utilities for building LangGraph workflows."""

from typing import Callable, Dict, List, Any, Optional
from langgraph.graph import StateGraph


class GraphBuilder:
    """Utility class for building LangGraph workflows with common patterns."""
    
    @staticmethod
    def add_conditional_routing(
        workflow: StateGraph,
        from_node: str,
        router_func: Callable,
        destinations: Dict[str, str],
        description: str = ""
    ):
        """
        Add conditional routing with validation.
        
        Args:
            workflow: LangGraph workflow
            from_node: Source node
            router_func: Routing function
            destinations: Mapping of route names to node names
            description: Optional description for documentation
        """
        workflow.add_conditional_edges(
            from_node,
            router_func,
            destinations
        )
    
    @staticmethod
    def add_linear_flow(
        workflow: StateGraph,
        nodes: List[str]
    ):
        """
        Add linear flow between nodes.
        
        Args:
            workflow: LangGraph workflow
            nodes: List of node names in order
        """
        for i in range(len(nodes) - 1):
            workflow.add_edge(nodes[i], nodes[i + 1])
    
    @staticmethod
    def add_loop(
        workflow: StateGraph,
        loop_node: str,
        condition_func: Callable,
        exit_node: str,
        max_iterations: int = 5
    ):
        """
        Add a loop pattern with max iterations.
        
        Args:
            workflow: LangGraph workflow
            loop_node: Node that loops
            condition_func: Function to determine continue/exit
            exit_node: Node to go to when exiting loop
            max_iterations: Maximum loop iterations
        """
        workflow.add_conditional_edges(
            loop_node,
            condition_func,
            {
                "continue": loop_node,
                "exit": exit_node
            }
        )
    
    @staticmethod
    def create_tool_execution_node(
        tool_map: Dict[str, Any],
        tool_name: str,
        state_question_key: str = "question",
        state_result_key: str = "tool_result"
    ) -> Callable:
        """
        Create a tool execution node function.
        
        Args:
            tool_map: Dictionary of tool name to tool object
            tool_name: Name of the tool to execute
            state_question_key: Key in state for question
            state_result_key: Key in state to store result
            
        Returns:
            Node function
        """
        def execute_tool(state: Dict[str, Any]) -> Dict[str, Any]:
            tool = tool_map.get(tool_name)
            if not tool:
                return {
                    **state,
                    state_result_key: f"{tool_name} not available"
                }
            
            try:
                question = state[state_question_key]
                result = tool.func(question)
                return {**state, state_result_key: result}
            except Exception as e:
                return {
                    **state,
                    state_result_key: f"Error in {tool_name}: {str(e)}"
                }
        
        return execute_tool
    
    @staticmethod
    def create_retry_logic(
        workflow: StateGraph,
        check_node: str,
        retry_node: str,
        success_node: str,
        max_retries: int = 3
    ):
        """
        Add retry logic pattern.
        
        Args:
            workflow: LangGraph workflow
            check_node: Node that checks if retry needed
            retry_node: Node to execute on retry
            success_node: Node to go to on success
            max_retries: Maximum retry attempts
        """
        def should_retry(state: Dict[str, Any]) -> str:
            iteration = state.get("iteration", 0)
            needs_retry = state.get("needs_retry", False)
            
            if needs_retry and iteration < max_retries:
                return "retry"
            return "success"
        
        workflow.add_conditional_edges(
            check_node,
            should_retry,
            {
                "retry": retry_node,
                "success": success_node
            }
        )
    
    @staticmethod
    def add_error_handling(
        workflow: StateGraph,
        nodes: List[str],
        error_node: str
    ):
        """
        Add error handling to multiple nodes.
        
        Args:
            workflow: LangGraph workflow
            nodes: List of nodes to add error handling to
            error_node: Node to route to on error
        """
        # Note: LangGraph doesn't have built-in error routing
        # This is a placeholder for future implementation
        pass


