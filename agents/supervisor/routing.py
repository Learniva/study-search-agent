"""Routing logic for Supervisor Agent."""

from typing import Literal

from .state import SupervisorState


class SupervisorAgentRouter:
    """Routing logic for Supervisor Agent."""
    
    @staticmethod
    def route_based_on_access(state: SupervisorState) -> Literal["study", "grading", "denied"]:
        """Route based on access control result."""
        if state["access_denied"]:
            return "denied"
        elif state["agent_choice"] == "study_agent":
            return "study"
        elif state["agent_choice"] == "grading_agent":
            return "grading"
        else:
            return "denied"

