"""LangGraph nodes for Study Agent."""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state import StudyAgentState
from utils import MAX_AGENT_ITERATIONS


class StudyAgentNodes:
    """LangGraph node implementations for Study Agent."""
    
    def __init__(self, llm, tool_map: Dict[str, Any]):
        self.llm = llm
        self.tool_map = tool_map
    
    def detect_complexity(self, state: StudyAgentState) -> StudyAgentState:
        """Detect if question requires multi-step planning."""
        question = state["question"].lower()
        
        # Check for multi-part indicators
        is_multi_part = any(ind in question for ind in [" and ", " also ", " then "])
        has_multiple_questions = question.count("?") > 1
        
        # Check for multi-tool requirements
        tools_mentioned = sum(1 for keywords in [
            ["document", "notes", "file"],
            ["search", "internet", "web"],
            ["code", "python", "execute"],
            ["animate", "animation", "video"]
        ] if any(k in question for k in keywords))
        
        is_complex = is_multi_part or has_multiple_questions or tools_mentioned > 1
        
        return {
            **state,
            "original_question": state.get("original_question", state["question"]),
            "is_complex_task": is_complex,
            "tools_used_history": state.get("tools_used_history", [])
        }
    
    def plan_complex_task(self, state: StudyAgentState) -> StudyAgentState:
        """Create execution plan for complex tasks."""
        question = state["question"]
        
        planning_prompt = f"""Break this complex question into executable steps:

Question: {question}

Available tools:
- Document_QA: Search documents
- Web_Search: Internet search
- Python_REPL: Execute code
- Manim_Animation: Create animations

Return JSON array:
[{{"step": 1, "description": "...", "tool": "..."}}, ...]

Keep it 2-4 steps maximum."""
        
        try:
            import json
            response = self.llm.invoke([HumanMessage(content=planning_prompt)])
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            plan = json.loads(content)
            
            return {
                **state,
                "task_plan": plan,
                "current_step": 0,
                "completed_steps": [],
                "intermediate_answers": []
            }
        except Exception:
            return {**state, "task_plan": None, "is_complex_task": False}
    
    def execute_plan(self, state: StudyAgentState) -> StudyAgentState:
        """Execute one step from the task plan."""
        plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        
        if not plan or current_step >= len(plan):
            return state
        
        step = plan[current_step]
        tool_name = step.get("tool", "")
        
        # Map tool names to execution methods
        tool_executors = {
            "web_search": self._execute_web_search,
            "Web_Search": self._execute_web_search,
            "document_qa": self._execute_document_qa,
            "Document_QA": self._execute_document_qa,
            "python_repl": self._execute_python_repl,
            "Python_REPL": self._execute_python_repl,
        }
        
        if tool_name in tool_executors:
            result_state = tool_executors[tool_name](state)
            
            intermediate = state.get("intermediate_answers", [])
            intermediate.append({
                "step": current_step + 1,
                "description": step.get("description", ""),
                "tool": tool_name,
                "result": result_state.get("tool_result", "")
            })
            
            tools_used = state.get("tools_used_history", [])
            tools_used.append(tool_name)
            
            completed = state.get("completed_steps", [])
            completed.append(f"step_{current_step + 1}")
            
            return {
                **result_state,
                "current_step": current_step + 1,
                "completed_steps": completed,
                "intermediate_answers": intermediate,
                "tools_used_history": tools_used
            }
        
        return {**state, "current_step": current_step + 1}
    
    def synthesize_results(self, state: StudyAgentState) -> StudyAgentState:
        """Synthesize multi-step results into final answer."""
        intermediate = state.get("intermediate_answers", [])
        question = state["question"]
        
        if not intermediate:
            return state
        
        steps_context = "\n\n".join([
            f"Step {r['step']} ({r['tool']}): {r['result']}"
            for r in intermediate
        ])
        
        synthesis_prompt = f"""Synthesize these step-by-step results:

Question: {question}

Results:
{steps_context}

Provide a complete answer."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            final_answer = response.content
            
            return {
                **state,
                "final_answer": final_answer,
                "tool_result": final_answer,
                "messages": state["messages"] + [AIMessage(content=final_answer)]
            }
        except Exception:
            last_result = intermediate[-1]["result"] if intermediate else "No results"
            return {**state, "final_answer": last_result, "tool_result": last_result}
    
    def self_reflect(self, state: StudyAgentState) -> StudyAgentState:
        """Self-reflect on answer quality."""
        answer = state.get("final_answer") or state.get("tool_result", "")
        question = state["question"]
        
        quality_issues = []
        confidence = 1.0
        
        if len(answer) < 50:
            quality_issues.append("Response too short")
            confidence -= 0.3
        
        error_indicators = ["error", "failed", "not found"]
        if any(ind in answer.lower() for ind in error_indicators):
            quality_issues.append("Contains errors")
            confidence -= 0.4
        
        confidence = max(0.0, min(1.0, confidence))
        needs_retry = confidence < 0.5 and state.get("iteration", 0) < MAX_AGENT_ITERATIONS
        
        return {
            **state,
            "response_confidence": confidence,
            "quality_issues": quality_issues,
            "needs_retry": needs_retry
        }
    
    def _execute_document_qa(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Document QA tool."""
        tool = self.tool_map.get("Document_QA")
        if not tool:
            return {
                **state,
                "tool_result": "Document QA not available",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
        
        try:
            result = tool.func(state["question"])
            failed = any(p in result.lower() for p in [
                "no relevant content", "no documents", "not found"
            ])
            
            return {
                **state,
                "tool_result": result,
                "tried_document_qa": True,
                "document_qa_failed": failed
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error: {str(e)}",
                "tried_document_qa": True,
                "document_qa_failed": True
            }
    
    def _execute_web_search(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Web Search tool."""
        tool = self.tool_map.get("Web_Search")
        if not tool:
            return {**state, "tool_result": "Web search not available"}
        
        try:
            raw_results = tool.func(state["question"])
            
            synthesis_prompt = f"""Synthesize search results:

Question: {state["question"]}

Results: {raw_results}

Provide comprehensive answer with sources."""
            
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            
            return {**state, "tool_result": response.content}
        except Exception as e:
            return {**state, "tool_result": f"Search error: {str(e)}"}
    
    def _execute_python_repl(self, state: StudyAgentState) -> StudyAgentState:
        """Execute Python REPL tool."""
        tool = self.tool_map.get("Python_REPL")
        if not tool:
            return {**state, "tool_result": "Python REPL not available"}
        
        try:
            question = state["question"]
            
            if "print" not in question.lower() and any(op in question for op in ['+', '-', '*', '/']):
                code = f"print({question})"
            else:
                code = question
            
            result = tool.func(code)
            return {**state, "tool_result": str(result)}
        except Exception as e:
            return {**state, "tool_result": f"Execution error: {str(e)}"}

