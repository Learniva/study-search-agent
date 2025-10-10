"""
Phase 3: Grading Workflow with Adaptive Rubrics and ML Learning

Implements adaptive grading that learns from professor corrections:
- Step 3.1: Grading Sub-Graph (grade_essay → check_past_overrides → reconcile_grade)
- Step 3.2: Adaptive Rubric Logic (queries L3 for professor patterns)
- Step 3.3: ML Adaptation (personalizes feedback based on student history)

The system uses the L3 Learning Store to adapt rubric weights and feedback
based on past professor corrections, creating a self-improving grading system.

Note: This workflow orchestrates the ML profiling tools from utils.ml.profiling
"""

import time
from typing import TypedDict, Optional, List, Dict, Any, Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Database imports
try:
    from database.database import get_session
    from database.rag_operations import get_grade_exceptions, get_learning_insights
    from database.models import GradeException
    from sqlalchemy import and_
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

from langgraph.graph import StateGraph, END


class GradingState(TypedDict):
    """
    State for the adaptive grading workflow.
    
    Tracks the full grading process including professor override checks
    and reconciliation.
    """
    # Input
    submission: str
    rubric: Dict[str, Any]
    professor_id: str
    student_id: Optional[str]
    assignment_type: str
    
    # Initial grading
    ai_grade: Optional[Dict[str, Any]]  # Initial AI grading result
    ai_scores: Dict[str, float]  # Scores per criterion
    ai_feedback: str  # Generated feedback
    ai_confidence: float  # Confidence in grading
    
    # Past overrides (from L3)
    past_overrides_found: bool
    override_patterns: List[Dict[str, Any]]
    systematic_bias: Optional[Dict[str, float]]  # Detected biases per criterion
    
    # Reconciliation
    reconciliation_needed: bool
    reconciled_grade: Optional[Dict[str, Any]]
    reconciliation_reasoning: str
    adjusted_scores: Dict[str, float]
    
    # Few-shot learning from L3
    similar_past_gradings: List[Dict[str, Any]]
    professor_grading_style: Optional[Dict[str, Any]]
    
    # Student profiling (Step 3.3)
    student_history: Optional[Dict[str, Any]]
    personalized_feedback: str
    common_student_errors: List[str]
    
    # Metadata
    processing_time_ms: float
    used_adaptive_rubric: bool
    learning_applied: bool
    
    # Output
    final_grade: Optional[Dict[str, Any]]
    final_feedback: str
    metadata: Dict[str, Any]


class AdaptiveGradingWorkflow:
    """
    Phase 3: Adaptive Grading Workflow with ML Learning.
    
    Features:
    - Learns from professor corrections (L3 Learning Store)
    - Adapts rubric weights based on past overrides
    - Provides personalized feedback based on student history
    - Uses few-shot examples from similar past gradings
    """
    
    def __init__(self, llm):
        """
        Initialize adaptive grading workflow.
        
        Args:
            llm: Language model for grading and reconciliation
        """
        self.llm = llm
        
        # Build the grading sub-graph
        self.graph = self._build_grading_graph()
        self.app = self.graph.compile()
    
    def _build_grading_graph(self) -> StateGraph:
        """
        Build the Phase 3.1 grading sub-graph.
        
        Workflow:
        START → grade_essay → check_past_overrides → [reconcile_grade | accept_grade] → END
        """
        workflow = StateGraph(GradingState)
        
        # Phase 3.1: Core grading nodes
        workflow.add_node("grade_essay", self._grade_essay_node)
        workflow.add_node("check_past_overrides", self._check_past_overrides_node)
        workflow.add_node("reconcile_grade", self._reconcile_grade_node)
        workflow.add_node("accept_grade", self._accept_grade_node)
        workflow.add_node("personalize_feedback", self._personalize_feedback_node)
        
        # Set entry point
        workflow.set_entry_point("grade_essay")
        
        # grade_essay → check_past_overrides
        workflow.add_edge("grade_essay", "check_past_overrides")
        
        # check_past_overrides → [reconcile_grade | accept_grade]
        def route_after_override_check(state: GradingState) -> Literal["reconcile", "accept"]:
            """Route based on whether overrides were found."""
            if state["past_overrides_found"] and state["reconciliation_needed"]:
                return "reconcile"
            return "accept"
        
        workflow.add_conditional_edges(
            "check_past_overrides",
            route_after_override_check,
            {
                "reconcile": "reconcile_grade",
                "accept": "accept_grade"
            }
        )
        
        # Both paths → personalize_feedback
        workflow.add_edge("reconcile_grade", "personalize_feedback")
        workflow.add_edge("accept_grade", "personalize_feedback")
        
        # personalize_feedback → END
        workflow.add_edge("personalize_feedback", END)
        
        return workflow
    
    def _grade_essay_node(self, state: GradingState) -> GradingState:
        """
        Phase 3.1: Initial grading node.
        
        Performs initial rubric-based grading with LLM.
        """
        submission = state["submission"]
        rubric = state["rubric"]
        professor_id = state["professor_id"]
        assignment_type = state["assignment_type"]
        
        print("\n📝 Grading submission...")
        
        start_time = time.time()
        
        # Check if we have similar past gradings (few-shot learning)
        similar_gradings = self._get_similar_past_gradings(
            professor_id=professor_id,
            assignment_type=assignment_type
        )
        
        # Build grading prompt with few-shot examples
        grading_prompt = self._build_grading_prompt(
            submission=submission,
            rubric=rubric,
            similar_examples=similar_gradings
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=grading_prompt)])
            
            # Parse grading response
            ai_grade = self._parse_grading_response(response.content)
            
            processing_time = (time.time() - start_time) * 1000
            
            print(f"   ✅ Initial grade: {ai_grade.get('total_score', 0)}/{ai_grade.get('max_score', 100)}")
            print(f"   Confidence: {ai_grade.get('confidence', 0):.2f}")
            
            return {
                **state,
                "ai_grade": ai_grade,
                "ai_scores": ai_grade.get("criterion_scores", {}),
                "ai_feedback": ai_grade.get("feedback", ""),
                "ai_confidence": ai_grade.get("confidence", 0.7),
                "similar_past_gradings": similar_gradings,
                "processing_time_ms": processing_time,
                "used_adaptive_rubric": len(similar_gradings) > 0
            }
            
        except Exception as e:
            print(f"   ❌ Grading error: {e}")
            return {
                **state,
                "ai_grade": None,
                "ai_scores": {},
                "ai_feedback": f"Error during grading: {str(e)}",
                "ai_confidence": 0.0,
                "similar_past_gradings": [],
                "processing_time_ms": (time.time() - start_time) * 1000
            }
    
    def _check_past_overrides_node(self, state: GradingState) -> GradingState:
        """
        Phase 3.2: Check L3 for past professor overrides.
        
        Queries grade_exceptions table to find patterns where this professor
        has corrected AI grades in the past. Uses these patterns to determine
        if reconciliation is needed.
        """
        professor_id = state["professor_id"]
        assignment_type = state["assignment_type"]
        ai_scores = state["ai_scores"]
        
        print("\n🔍 Checking past professor overrides (L3 Learning Store)...")
        
        if not DATABASE_AVAILABLE:
            print("   ⚠️  Database not available - skipping override check")
            return {
                **state,
                "past_overrides_found": False,
                "override_patterns": [],
                "systematic_bias": None,
                "reconciliation_needed": False
            }
        
        try:
            db = get_session()
            try:
                # Query L3 for grade_exceptions (corrections by this professor)
                exceptions = db.query(GradeException).filter(
                    and_(
                        GradeException.user_id == professor_id,
                        GradeException.exception_type == 'grading_correction',
                        GradeException.rubric_type == assignment_type,
                        GradeException.status.in_(['analyzed', 'learned'])
                    )
                ).limit(20).all()
                
                if not exceptions:
                    print("   ℹ️  No past overrides found for this professor/assignment type")
                    return {
                        **state,
                        "past_overrides_found": False,
                        "override_patterns": [],
                        "systematic_bias": None,
                        "reconciliation_needed": False
                    }
                
                print(f"   📊 Found {len(exceptions)} past corrections")
                
                # Analyze patterns in corrections
                override_patterns = []
                criterion_adjustments = {}
                
                for exc in exceptions:
                    ai_decision = exc.ai_decision or {}
                    correct_decision = exc.correct_decision or {}
                    
                    # Extract score differences per criterion
                    ai_criterion_scores = ai_decision.get("criterion_scores", {})
                    prof_criterion_scores = correct_decision.get("criterion_scores", {})
                    
                    for criterion, prof_score in prof_criterion_scores.items():
                        if criterion in ai_criterion_scores:
                            diff = prof_score - ai_criterion_scores[criterion]
                            if criterion not in criterion_adjustments:
                                criterion_adjustments[criterion] = []
                            criterion_adjustments[criterion].append(diff)
                    
                    override_patterns.append({
                        "ai_scores": ai_criterion_scores,
                        "professor_scores": prof_criterion_scores,
                        "correction_reason": exc.correction_reason
                    })
                
                # Calculate systematic bias (average adjustment per criterion)
                systematic_bias = {}
                for criterion, adjustments in criterion_adjustments.items():
                    avg_adjustment = sum(adjustments) / len(adjustments)
                    if abs(avg_adjustment) > 2.0:  # Significant bias threshold
                        systematic_bias[criterion] = avg_adjustment
                
                # Determine if reconciliation is needed
                reconciliation_needed = len(systematic_bias) > 0
                
                if reconciliation_needed:
                    print(f"   ⚠️  Systematic bias detected in criteria: {list(systematic_bias.keys())}")
                    for criterion, bias in systematic_bias.items():
                        print(f"      • {criterion}: {bias:+.1f} points (avg adjustment)")
                else:
                    print("   ✅ No significant systematic bias detected")
                
                return {
                    **state,
                    "past_overrides_found": True,
                    "override_patterns": override_patterns,
                    "systematic_bias": systematic_bias,
                    "reconciliation_needed": reconciliation_needed
                }
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"   ❌ Error checking overrides: {e}")
            return {
                **state,
                "past_overrides_found": False,
                "override_patterns": [],
                "systematic_bias": None,
                "reconciliation_needed": False
            }
    
    def _reconcile_grade_node(self, state: GradingState) -> GradingState:
        """
        Phase 3.2: Reconcile grade using professor override patterns.
        
        Uses the LLM with past override patterns as few-shot examples
        to generate a more nuanced grade that aligns with professor's
        grading style.
        """
        ai_grade = state["ai_grade"]
        systematic_bias = state["systematic_bias"]
        override_patterns = state["override_patterns"]
        submission = state["submission"]
        rubric = state["rubric"]
        
        print("\n🔄 Reconciling grade based on professor patterns...")
        
        # Build few-shot examples from override patterns
        few_shot_examples = "\n\n".join([
            f"Example {i+1}:\n"
            f"AI Scores: {pattern['ai_scores']}\n"
            f"Professor Scores: {pattern['professor_scores']}\n"
            f"Reason: {pattern.get('correction_reason', 'N/A')}"
            for i, pattern in enumerate(override_patterns[:3])  # Use top 3 examples
        ])
        
        reconciliation_prompt = f"""You are reconciling an AI-generated grade based on this professor's past correction patterns.

**Original AI Grade:**
Total Score: {ai_grade.get('total_score', 0)}/{ai_grade.get('max_score', 100)}
Criterion Scores: {ai_grade.get('criterion_scores', {})}

**Detected Systematic Bias (from past corrections):**
{systematic_bias}

**Past Correction Examples:**
{few_shot_examples}

**Current Submission:**
{submission[:500]}...

**Rubric:**
{rubric}

**Task:**
Generate a reconciled grade that:
1. Applies the systematic bias adjustments to each criterion
2. Follows the professor's grading patterns from past corrections
3. Maintains fairness and consistency
4. Explains the adjustments made

Provide the reconciled grade in this format:
RECONCILED_SCORES: {{criterion: score, ...}}
TOTAL_SCORE: X/Y
REASONING: Why these adjustments were made based on professor patterns
ADJUSTED_FEEDBACK: Updated feedback incorporating the reconciliation"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=reconciliation_prompt)])
            
            # Parse reconciled grade
            reconciled_grade = self._parse_reconciliation_response(response.content)
            
            print(f"   ✅ Reconciled grade: {reconciled_grade.get('total_score', 0)}/{reconciled_grade.get('max_score', 100)}")
            print(f"   Adjustments: {reconciled_grade.get('adjustments', {})}")
            
            return {
                **state,
                "reconciled_grade": reconciled_grade,
                "reconciliation_reasoning": reconciled_grade.get("reasoning", ""),
                "adjusted_scores": reconciled_grade.get("criterion_scores", {}),
                "learning_applied": True
            }
            
        except Exception as e:
            print(f"   ❌ Reconciliation error: {e}")
            # Fall back to original grade
            return {
                **state,
                "reconciled_grade": ai_grade,
                "reconciliation_reasoning": f"Reconciliation failed: {str(e)}",
                "adjusted_scores": state["ai_scores"],
                "learning_applied": False
            }
    
    def _accept_grade_node(self, state: GradingState) -> GradingState:
        """
        Accept the original AI grade (no reconciliation needed).
        """
        print("\n✅ Accepting original AI grade (no systematic bias detected)")
        
        return {
            **state,
            "reconciled_grade": state["ai_grade"],
            "reconciliation_reasoning": "No significant bias detected; original grade accepted",
            "adjusted_scores": state["ai_scores"],
            "learning_applied": False
        }
    
    def _personalize_feedback_node(self, state: GradingState) -> GradingState:
        """
        Phase 3.3: Personalize feedback based on student history.
        
        Queries L3 for this student's past performance and common errors,
        then tailors the feedback to address recurring issues.
        """
        student_id = state.get("student_id")
        professor_id = state["professor_id"]
        final_grade = state.get("reconciled_grade") or state["ai_grade"]
        
        print("\n👤 Personalizing feedback based on student history...")
        
        if not student_id or not DATABASE_AVAILABLE:
            print("   ℹ️  Student history not available")
            return {
                **state,
                "student_history": None,
                "personalized_feedback": final_grade.get("feedback", ""),
                "common_student_errors": [],
                "final_grade": final_grade,
                "final_feedback": final_grade.get("feedback", ""),
                "metadata": {
                    "used_adaptive_rubric": state.get("used_adaptive_rubric", False),
                    "learning_applied": state.get("learning_applied", False),
                    "personalization_applied": False
                }
            }
        
        try:
            db = get_session()
            try:
                # Query past corrections for this student
                student_exceptions = db.query(GradeException).filter(
                    and_(
                        GradeException.user_id == professor_id,
                        GradeException.query.like(f"%student:{student_id}%"),
                        GradeException.exception_type == 'grading_correction'
                    )
                ).limit(5).all()
                
                if not student_exceptions:
                    print("   ℹ️  No past corrections for this student")
                    return {
                        **state,
                        "student_history": None,
                        "personalized_feedback": final_grade.get("feedback", ""),
                        "common_student_errors": [],
                        "final_grade": final_grade,
                        "final_feedback": final_grade.get("feedback", ""),
                        "metadata": {
                            "used_adaptive_rubric": state.get("used_adaptive_rubric", False),
                            "learning_applied": state.get("learning_applied", False),
                            "personalization_applied": False
                        }
                    }
                
                # Extract common error patterns
                common_errors = []
                for exc in student_exceptions:
                    if exc.error_description:
                        common_errors.append(exc.error_description)
                
                print(f"   📊 Found {len(common_errors)} past issues for this student")
                
                # Generate personalized feedback
                personalization_prompt = f"""Personalize this feedback for a student based on their history.

**Original Feedback:**
{final_grade.get('feedback', '')}

**Student's Past Issues (from {len(common_errors)} past assignments):**
{chr(10).join(f"- {error}" for error in common_errors[:3])}

**Task:**
Rewrite the feedback to:
1. Reference recurring issues if they appear in this submission
2. Acknowledge improvement if past issues are resolved
3. Provide specific guidance based on their learning patterns
4. Maintain an encouraging but honest tone

Keep the same overall assessment, just personalize the delivery."""
                
                response = self.llm.invoke([HumanMessage(content=personalization_prompt)])
                personalized_feedback = response.content.strip()
                
                print("   ✅ Feedback personalized")
                
                return {
                    **state,
                    "student_history": {"past_issues": common_errors},
                    "personalized_feedback": personalized_feedback,
                    "common_student_errors": common_errors,
                    "final_grade": final_grade,
                    "final_feedback": personalized_feedback,
                    "metadata": {
                        "used_adaptive_rubric": state.get("used_adaptive_rubric", False),
                        "learning_applied": state.get("learning_applied", False),
                        "personalization_applied": True
                    }
                }
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"   ❌ Personalization error: {e}")
            return {
                **state,
                "student_history": None,
                "personalized_feedback": final_grade.get("feedback", ""),
                "common_student_errors": [],
                "final_grade": final_grade,
                "final_feedback": final_grade.get("feedback", ""),
                "metadata": {
                    "used_adaptive_rubric": state.get("used_adaptive_rubric", False),
                    "learning_applied": state.get("learning_applied", False),
                    "personalization_applied": False
                }
            }
    
    def _get_similar_past_gradings(
        self,
        professor_id: str,
        assignment_type: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get similar past gradings for few-shot learning.
        
        Retrieves successful past gradings by this professor for this
        assignment type to use as examples.
        """
        if not DATABASE_AVAILABLE:
            return []
        
        try:
            db = get_session()
            try:
                # Get grading sessions from database
                from database.models import GradingSession
                
                past_sessions = db.query(GradingSession).filter(
                    and_(
                        GradingSession.professor_id == professor_id,
                        GradingSession.grading_type == assignment_type,
                        GradingSession.reviewed_by_professor == True  # Only use professor-approved
                    )
                ).limit(limit).all()
                
                return [
                    {
                        "submission_preview": str(session.submission)[:200] if session.submission else "",
                        "rubric_used": session.rubric_data,
                        "score": session.score,
                        "feedback": session.professor_feedback or ""
                    }
                    for session in past_sessions
                ]
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"   ⚠️  Error loading past gradings: {e}")
            return []
    
    def _build_grading_prompt(
        self,
        submission: str,
        rubric: Dict[str, Any],
        similar_examples: List[Dict[str, Any]]
    ) -> str:
        """Build grading prompt with few-shot examples."""
        
        few_shot_section = ""
        if similar_examples:
            few_shot_section = "\n\n**Similar Past Gradings (for reference):**\n"
            for i, example in enumerate(similar_examples, 1):
                few_shot_section += f"\nExample {i}:\n"
                few_shot_section += f"Submission Preview: {example['submission_preview']}...\n"
                few_shot_section += f"Score: {example['score']}\n"
                few_shot_section += f"Feedback: {example['feedback'][:150]}...\n"
        
        return f"""Grade this submission using the provided rubric.

**Submission:**
{submission}

**Rubric:**
{rubric}
{few_shot_section}

**Instructions:**
1. Evaluate each criterion in the rubric
2. Assign scores for each criterion
3. Provide specific, constructive feedback
4. Calculate total score
5. Estimate your confidence in this grading (0-1)

**Output Format:**
CRITERION_SCORES: {{criterion_name: score, ...}}
TOTAL_SCORE: X/Y
CONFIDENCE: 0.XX
FEEDBACK: Detailed feedback here...
"""
    
    def _parse_grading_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM grading response into structured format."""
        lines = response.strip().split('\n')
        
        result = {
            "criterion_scores": {},
            "total_score": 0,
            "max_score": 100,
            "confidence": 0.7,
            "feedback": ""
        }
        
        feedback_lines = []
        in_feedback = False
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("CRITERION_SCORES:"):
                # Parse criterion scores
                try:
                    import json
                    scores_str = line.split(":", 1)[1].strip()
                    result["criterion_scores"] = json.loads(scores_str)
                except:
                    pass
                    
            elif line.startswith("TOTAL_SCORE:"):
                # Parse total score
                try:
                    score_str = line.split(":", 1)[1].strip()
                    if "/" in score_str:
                        parts = score_str.split("/")
                        result["total_score"] = float(parts[0])
                        result["max_score"] = float(parts[1])
                except:
                    pass
                    
            elif line.startswith("CONFIDENCE:"):
                # Parse confidence
                try:
                    conf_str = line.split(":", 1)[1].strip()
                    result["confidence"] = float(conf_str)
                except:
                    pass
                    
            elif line.startswith("FEEDBACK:"):
                in_feedback = True
                feedback_text = line.split(":", 1)[1].strip()
                if feedback_text:
                    feedback_lines.append(feedback_text)
                    
            elif in_feedback:
                feedback_lines.append(line)
        
        result["feedback"] = "\n".join(feedback_lines)
        
        return result
    
    def _parse_reconciliation_response(self, response: str) -> Dict[str, Any]:
        """Parse reconciliation response."""
        result = {
            "criterion_scores": {},
            "total_score": 0,
            "max_score": 100,
            "reasoning": "",
            "feedback": "",
            "adjustments": {}
        }
        
        lines = response.strip().split('\n')
        
        in_reasoning = False
        in_feedback = False
        reasoning_lines = []
        feedback_lines = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("RECONCILED_SCORES:"):
                try:
                    import json
                    scores_str = line.split(":", 1)[1].strip()
                    result["criterion_scores"] = json.loads(scores_str)
                except:
                    pass
                    
            elif line.startswith("TOTAL_SCORE:"):
                try:
                    score_str = line.split(":", 1)[1].strip()
                    if "/" in score_str:
                        parts = score_str.split("/")
                        result["total_score"] = float(parts[0])
                        result["max_score"] = float(parts[1])
                except:
                    pass
                    
            elif line.startswith("REASONING:"):
                in_reasoning = True
                in_feedback = False
                reasoning_text = line.split(":", 1)[1].strip()
                if reasoning_text:
                    reasoning_lines.append(reasoning_text)
                    
            elif line.startswith("ADJUSTED_FEEDBACK:"):
                in_feedback = True
                in_reasoning = False
                feedback_text = line.split(":", 1)[1].strip()
                if feedback_text:
                    feedback_lines.append(feedback_text)
                    
            elif in_reasoning:
                reasoning_lines.append(line)
            elif in_feedback:
                feedback_lines.append(line)
        
        result["reasoning"] = "\n".join(reasoning_lines)
        result["feedback"] = "\n".join(feedback_lines)
        
        return result
    
    def execute(
        self,
        submission: str,
        rubric: Dict[str, Any],
        professor_id: str,
        assignment_type: str,
        student_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the adaptive grading workflow.
        
        Args:
            submission: Student submission text
            rubric: Grading rubric dictionary
            professor_id: Professor's ID for pattern lookup
            assignment_type: Type of assignment (essay, code, etc.)
            student_id: Optional student ID for personalization
        
        Returns:
            Dictionary with final grade, feedback, and metadata
        """
        initial_state = {
            "submission": submission,
            "rubric": rubric,
            "professor_id": professor_id,
            "student_id": student_id,
            "assignment_type": assignment_type,
            "ai_grade": None,
            "ai_scores": {},
            "ai_feedback": "",
            "ai_confidence": 0.0,
            "past_overrides_found": False,
            "override_patterns": [],
            "systematic_bias": None,
            "reconciliation_needed": False,
            "reconciled_grade": None,
            "reconciliation_reasoning": "",
            "adjusted_scores": {},
            "similar_past_gradings": [],
            "professor_grading_style": None,
            "student_history": None,
            "personalized_feedback": "",
            "common_student_errors": [],
            "processing_time_ms": 0.0,
            "used_adaptive_rubric": False,
            "learning_applied": False,
            "final_grade": None,
            "final_feedback": "",
            "metadata": {}
        }
        
        try:
            result = self.app.invoke(initial_state)
            return result
        except Exception as e:
            print(f"\n❌ Grading workflow error: {e}")
            return {
                **initial_state,
                "final_feedback": f"Error in grading workflow: {str(e)}"
            }

