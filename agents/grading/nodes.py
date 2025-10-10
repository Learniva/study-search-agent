"""LangGraph nodes for Grading Agent."""

import time
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

from .state import GradingAgentState
from utils import (
    MAX_GRADING_ITERATIONS,
    GRADING_ERROR_INDICATORS,
    GRADING_UNCERTAINTY_INDICATORS,
)


class GradingAgentNodes:
    """LangGraph node implementations for Grading Agent."""
    
    def __init__(self, llm, tool_map: Dict[str, Any]):
        self.llm = llm
        self.tool_map = tool_map
    
    def analyze_submission(self, state: GradingAgentState) -> GradingAgentState:
        """Analyze submission for potential issues."""
        question = state["question"]
        detected_issues = []
        potential_errors = []
        
        if len(question) < 100:
            detected_issues.append("Submission very short (< 100 characters)")
        
        plagiarism_indicators = ["http://", "https://", "www.", "©", "copyright"]
        if any(ind in question.lower() for ind in plagiarism_indicators):
            detected_issues.append("Contains potential plagiarism indicators")
        
        if any(char in question for char in ["{", "}", "def ", "class "]):
            if "```" not in question:
                potential_errors.append({
                    "type": "formatting",
                    "description": "Code detected without code blocks",
                    "severity": "low"
                })
        
        return {
            **state,
            "original_question": question,
            "detected_issues": detected_issues,
            "potential_errors": potential_errors,
            "tools_used_history": [],
            "iteration": 0,
            "max_iterations": MAX_GRADING_ITERATIONS,
            "needs_human_review": False,
            "review_reasons": [],
            "suggested_improvements": [],
            "positive_highlights": [],
            "auto_corrections": [],
            "adapted_rubric": False
        }
    
    def detect_grading_complexity(self, state: GradingAgentState) -> GradingAgentState:
        """Detect if grading requires multi-step planning."""
        question = state["question"].lower()
        
        multi_tool_indicators = [
            ("rubric" in question or "criteria" in question) and ("grade" in question),
            ("feedback" in question) and ("grade" in question),
            ("compare" in question) and ("grade" in question),
            question.count(" and ") >= 2,
            "also" in question and "grade" in question,
        ]
        
        is_complex = any(multi_tool_indicators)
        
        return {
            **state,
            "is_complex_grading": is_complex,
            "current_grading_step": 0,
            "completed_grading_steps": [],
            "intermediate_grading_results": []
        }
    
    def plan_complex_grading(self, state: GradingAgentState) -> GradingAgentState:
        """Create multi-step grading plan."""
        question = state["question"]
        
        planning_prompt = f"""Break down this grading request into sequential steps.

Available tools:
- grade_essay: Grade text submissions
- review_code: Review code
- grade_mcq: Grade MCQs
- evaluate_rubric: Evaluate against rubric
- generate_feedback: Generate feedback

Request: {question}

Return JSON:
{{"steps": [{{"step": 1, "description": "...", "tool": "..."}}]}}

Maximum 4 steps."""
        
        try:
            import json
            response = self.llm.invoke([HumanMessage(content=planning_prompt)])
            plan_text = response.content.strip()
            
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
            plan_data = json.loads(plan_text)
            grading_plan = plan_data.get("steps", [])
            
            return {**state, "grading_plan": grading_plan}
        except Exception:
            return {
                **state,
                "grading_plan": [{"step": 1, "description": "Grade", "tool": "grade_essay"}],
                "is_complex_grading": False
            }
    
    def execute_grading_plan(self, state: GradingAgentState) -> GradingAgentState:
        """Execute multi-step grading plan."""
        grading_plan = state.get("grading_plan", [])
        current_step = state.get("current_grading_step", 0)
        intermediate_results = state.get("intermediate_grading_results", [])
        
        if current_step >= len(grading_plan):
            final_result = "\n\n---\n\n".join([
                f"**{r['step_description']}**\n{r['result']}"
                for r in intermediate_results
            ])
            return {**state, "tool_result": final_result, "final_answer": final_result}
        
        step = grading_plan[current_step]
        tool_name = step["tool"]
        step_description = step["description"]
        
        context_parts = [state["question"]]
        if intermediate_results:
            context_parts.append("\n\nPrevious results:")
            for prev in intermediate_results:
                context_parts.append(f"- {prev['step_description']}: {prev['result'][:200]}...")
        
        context = "\n".join(context_parts)
        
        try:
            tool = self.tool_map.get(tool_name)
            result = tool.invoke(context) if tool else f"Tool '{tool_name}' not found"
            
            intermediate_results.append({
                "step": current_step + 1,
                "step_description": step_description,
                "tool": tool_name,
                "result": result
            })
            
            completed_steps = state.get("completed_grading_steps", [])
            completed_steps.append(step_description)
            
            return {
                **state,
                "current_grading_step": current_step + 1,
                "completed_grading_steps": completed_steps,
                "intermediate_grading_results": intermediate_results,
                "tool_used": tool_name,
                "tool_result": result
            }
        except Exception as e:
            return {
                **state,
                "tool_result": f"Error: {str(e)}",
                "current_grading_step": len(grading_plan)
            }
    
    def check_consistency(self, state: GradingAgentState) -> GradingAgentState:
        """Check grading consistency with past grades."""
        import re
        
        tool_result = state.get("tool_result", "")
        consistency_score = 1.0
        
        score_match = re.search(r'Score:\s*(\d+)', tool_result)
        current_score = int(score_match.group(1)) if score_match else None
        
        if current_score:
            if current_score > 100:
                consistency_score = 0.3
            elif current_score < 0:
                consistency_score = 0.3
        
        tools_used = state.get("tools_used_history", [])
        if state.get("tool_used"):
            tools_used.append(state["tool_used"])
        
        return {
            **state,
            "consistency_score": consistency_score,
            "tools_used_history": tools_used
        }
    
    def self_reflect_grade(self, state: GradingAgentState) -> GradingAgentState:
        """Self-reflect on grading quality."""
        import re
        
        tool_result = state.get("tool_result", "")
        detected_issues = state.get("detected_issues", [])
        consistency_score = state.get("consistency_score", 1.0)
        
        grading_confidence = 1.0
        needs_review = False
        review_reasons = []
        
        if detected_issues:
            grading_confidence -= 0.2 * min(len(detected_issues), 3)
            needs_review = True
            review_reasons.append(f"Submission has {len(detected_issues)} issues")
        
        if consistency_score < 0.7:
            grading_confidence -= 0.3
            needs_review = True
            review_reasons.append(f"Low consistency score ({consistency_score:.2f})")
        
        required_sections = ["score", "feedback", "strengths", "improvement"]
        missing_sections = [s for s in required_sections if s.lower() not in tool_result.lower()]
        if missing_sections:
            grading_confidence -= 0.1 * len(missing_sections)
            review_reasons.append(f"Missing: {', '.join(missing_sections)}")
        
        if len(tool_result) < 200:
            grading_confidence -= 0.2
            needs_review = True
            review_reasons.append("Feedback too brief")
        
        grading_confidence = max(0.0, min(1.0, grading_confidence))
        
        score_match = re.search(r'Score:\s*(\d+)(?:/(\d+))?', tool_result)
        criterion_scores = {}
        if score_match:
            score = int(score_match.group(1))
            max_score = int(score_match.group(2)) if score_match.group(2) else 100
            criterion_scores = {"overall": float(score) / max_score if max_score > 0 else 0.0}
        
        return {
            **state,
            "grading_confidence": grading_confidence,
            "needs_human_review": needs_review,
            "review_reasons": review_reasons,
            "criterion_scores": criterion_scores
        }
    
    def flag_for_review(self, state: GradingAgentState) -> GradingAgentState:
        """Flag grading for human review."""
        review_reasons = state.get("review_reasons", [])
        
        review_notice = f"\n\n{'='*60}\n"
        review_notice += "⚠️  **REQUIRES PROFESSOR REVIEW**\n"
        review_notice += f"{'='*60}\n\n"
        review_notice += "Flagged for human review:\n"
        for i, reason in enumerate(review_reasons, 1):
            review_notice += f"  {i}. {reason}\n"
        review_notice += "\nPlease review and adjust as needed.\n"
        
        tool_result = state.get("tool_result", "")
        return {**state, "tool_result": tool_result + review_notice}
    
    def improve_grade(self, state: GradingAgentState) -> GradingAgentState:
        """Attempt to improve grading quality."""
        tool_result = state.get("tool_result", "")
        suggested_improvements = state.get("suggested_improvements", [])
        iteration = state.get("iteration", 0)
        
        if suggested_improvements:
            improvement_section = "\n\n**Additional Suggestions:**\n"
            for i, suggestion in enumerate(suggested_improvements, 1):
                improvement_section += f"  {i}. {suggestion}\n"
            tool_result += improvement_section
        
        return {
            **state,
            "tool_result": tool_result,
            "iteration": iteration + 1,
            "grading_confidence": min(1.0, state.get("grading_confidence", 0.7) + 0.1)
        }

