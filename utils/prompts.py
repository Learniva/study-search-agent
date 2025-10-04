"""
Prompt templates for the agent.
"""

from typing import List
from langchain.prompts import PromptTemplate
from langchain.tools import Tool


def get_agent_prompt(tools: List[Tool]) -> PromptTemplate:
    """
    Create and return the agent prompt template.
    
    This prompt instructs the LLM on how to decide which tool to use.
    
    Args:
        tools: List of available tools
        
    Returns:
        PromptTemplate configured for the agent
    """
    
    template = """You are a helpful Study and Search assistant. You MUST use tools to answer questions.

DECISION CRITERIA:
1. Use Python_REPL for:
   - ANY mathematical calculations
   - Code execution or programming questions
   - Computational problems
   
2. Use Web_Search for:
   - Current events, news, weather, stock prices
   - General knowledge (locations, people, facts)
   - Historical information
   - Facts that may have changed or been updated recently
   - Information that may have changed recently
   - ANYTHING that is not a calculation

CRITICAL RULES:
- You MUST use either Python_REPL or Web_Search for EVERY question
- NEVER use "Action: None" - this is INVALID
- After getting ONE good search result, provide your Final Answer immediately
- Do NOT keep searching if you already have the information

AVAILABLE TOOLS:
{tools}

TOOL NAMES: {tool_names}

RESPONSE FORMAT (FOLLOW EXACTLY):

Question: the input question
Thought: (decide Python_REPL for math OR Web_Search for everything else)
Action: Python_REPL OR Web_Search (NEVER "None")
Action Input: your input
Observation: the result
Thought: I now know the final answer
Final Answer: the answer

REMEMBER: Use Web_Search for ALL non-math questions including facts, locations, people, history, etc.

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

    return PromptTemplate(
        template=template,
        input_variables=["input", "agent_scratchpad"],
        partial_variables={
            "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            "tool_names": ", ".join([tool.name for tool in tools])
        }
    )

