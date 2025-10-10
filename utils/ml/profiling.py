"""
Phase 3.3: ML Profiling Tools for Adaptive Grading

Tools for querying student/professor profiles from L3 Learning Store
to enable personalized, context-aware grading and feedback.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Database imports
try:
    from database.database import get_session
    from database.models import GradeException, GradingSession
    from sqlalchemy import and_, func, desc
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


def check_past_overrides(
    professor_id: str,
    rubric_type: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Tool: Check past professor overrides from L3.
    
    Phase 3.2: Queries grade_exceptions table for patterns where this
    professor has corrected AI grades. Returns systematic biases and
    correction patterns.
    
    Args:
        professor_id: Professor's user ID
        rubric_type: Type of rubric (essay, code, etc.)
        limit: Maximum number of exceptions to retrieve
    
    Returns:
        Dictionary containing:
        - found: Whether any overrides were found
        - count: Number of overrides
        - patterns: List of correction patterns
        - systematic_bias: Detected biases per criterion
        - recommendation: Whether to apply reconciliation
    """
    if not DATABASE_AVAILABLE:
        return {
            "found": False,
            "count": 0,
            "patterns": [],
            "systematic_bias": {},
            "recommendation": "No database available",
            "error": "Database not configured"
        }
    
    try:
        db = get_session()
        try:
            # Query grade_exceptions
            exceptions = db.query(GradeException).filter(
                and_(
                    GradeException.user_id == professor_id,
                    GradeException.exception_type == 'grading_correction',
                    GradeException.rubric_type == rubric_type,
                    GradeException.status.in_(['analyzed', 'learned'])
                )
            ).order_by(desc(GradeException.created_at)).limit(limit).all()
            
            if not exceptions:
                return {
                    "found": False,
                    "count": 0,
                    "patterns": [],
                    "systematic_bias": {},
                    "recommendation": "Use original AI grade"
                }
            
            # Analyze patterns
            patterns = []
            criterion_adjustments = {}
            
            for exc in exceptions:
                ai_decision = exc.ai_decision or {}
                correct_decision = exc.correct_decision or {}
                
                ai_scores = ai_decision.get("criterion_scores", {})
                prof_scores = correct_decision.get("criterion_scores", {})
                
                # Calculate differences
                for criterion, prof_score in prof_scores.items():
                    if criterion in ai_scores:
                        diff = prof_score - ai_scores[criterion]
                        if criterion not in criterion_adjustments:
                            criterion_adjustments[criterion] = []
                        criterion_adjustments[criterion].append(diff)
                
                patterns.append({
                    "date": exc.created_at.isoformat() if exc.created_at else None,
                    "ai_scores": ai_scores,
                    "professor_scores": prof_scores,
                    "reason": exc.correction_reason,
                    "score_difference": exc.score_difference
                })
            
            # Calculate systematic bias
            systematic_bias = {}
            for criterion, adjustments in criterion_adjustments.items():
                avg_adjustment = sum(adjustments) / len(adjustments)
                std_dev = (sum((x - avg_adjustment) ** 2 for x in adjustments) / len(adjustments)) ** 0.5
                
                # Only flag as systematic if consistent (low std dev) and significant
                if abs(avg_adjustment) > 2.0 and std_dev < 5.0:
                    systematic_bias[criterion] = {
                        "average_adjustment": round(avg_adjustment, 2),
                        "std_dev": round(std_dev, 2),
                        "sample_size": len(adjustments)
                    }
            
            recommendation = "Apply reconciliation" if systematic_bias else "Use original AI grade"
            
            return {
                "found": True,
                "count": len(exceptions),
                "patterns": patterns,
                "systematic_bias": systematic_bias,
                "recommendation": recommendation,
                "analysis": f"Found {len(exceptions)} past corrections with {len(systematic_bias)} systematic biases detected"
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "found": False,
            "count": 0,
            "patterns": [],
            "systematic_bias": {},
            "recommendation": "Use original AI grade",
            "error": str(e)
        }


def get_student_profile(
    student_id: str,
    professor_id: Optional[str] = None,
    course_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: Get student learning profile from L3.
    
    Phase 3.3: Retrieves student's historical performance, common errors,
    and improvement patterns to enable personalized feedback.
    
    Args:
        student_id: Student's user ID
        professor_id: Optional professor ID to filter by
        course_id: Optional course ID to filter by
    
    Returns:
        Dictionary containing:
        - student_id: Student identifier
        - total_submissions: Number of past submissions
        - average_score: Average score across submissions
        - common_errors: List of recurring error patterns
        - improvement_trend: Whether student is improving
        - strengths: Identified strengths
        - areas_for_improvement: Identified weaknesses
        - recommendations: Suggestions for personalized feedback
    """
    if not DATABASE_AVAILABLE:
        return {
            "student_id": student_id,
            "total_submissions": 0,
            "average_score": None,
            "common_errors": [],
            "improvement_trend": "unknown",
            "strengths": [],
            "areas_for_improvement": [],
            "recommendations": ["Use generic feedback (database not available)"],
            "error": "Database not configured"
        }
    
    try:
        db = get_session()
        try:
            # Build query filters
            filters = [GradingSession.student_id == student_id]
            if professor_id:
                filters.append(GradingSession.professor_id == professor_id)
            if course_id:
                filters.append(GradingSession.course_id == course_id)
            
            # Get past grading sessions
            sessions = db.query(GradingSession).filter(
                and_(*filters)
            ).order_by(desc(GradingSession.created_at)).limit(20).all()
            
            if not sessions:
                return {
                    "student_id": student_id,
                    "total_submissions": 0,
                    "average_score": None,
                    "common_errors": [],
                    "improvement_trend": "no_data",
                    "strengths": [],
                    "areas_for_improvement": [],
                    "recommendations": ["No past submissions found for this student"]
                }
            
            # Calculate statistics
            scores = [s.score for s in sessions if s.score is not None]
            average_score = sum(scores) / len(scores) if scores else None
            
            # Analyze improvement trend
            if len(scores) >= 3:
                recent_avg = sum(scores[:3]) / 3
                older_avg = sum(scores[3:]) / len(scores[3:]) if len(scores) > 3 else recent_avg
                improvement_trend = "improving" if recent_avg > older_avg else "stable" if recent_avg == older_avg else "declining"
            else:
                improvement_trend = "insufficient_data"
            
            # Extract common errors from grade exceptions
            error_filters = [
                GradeException.query.like(f"%student:{student_id}%"),
                GradeException.exception_type == 'grading_correction'
            ]
            if professor_id:
                error_filters.append(GradeException.user_id == professor_id)
            
            exceptions = db.query(GradeException).filter(
                and_(*error_filters)
            ).limit(10).all()
            
            common_errors = []
            error_categories = {}
            
            for exc in exceptions:
                if exc.error_category:
                    error_categories[exc.error_category] = error_categories.get(exc.error_category, 0) + 1
                if exc.error_description:
                    common_errors.append(exc.error_description)
            
            # Identify top error categories
            top_errors = sorted(error_categories.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Analyze criterion performance
            criterion_performance = {}
            for session in sessions:
                if session.criterion_scores:
                    for criterion, score in session.criterion_scores.items():
                        if criterion not in criterion_performance:
                            criterion_performance[criterion] = []
                        criterion_performance[criterion].append(score)
            
            # Identify strengths and weaknesses
            strengths = []
            areas_for_improvement = []
            
            for criterion, scores_list in criterion_performance.items():
                avg = sum(scores_list) / len(scores_list)
                if avg >= 85:
                    strengths.append(f"{criterion} (avg: {avg:.1f})")
                elif avg < 70:
                    areas_for_improvement.append(f"{criterion} (avg: {avg:.1f})")
            
            # Generate recommendations
            recommendations = []
            
            if improvement_trend == "improving":
                recommendations.append("Acknowledge the student's improvement in feedback")
            elif improvement_trend == "declining":
                recommendations.append("Express concern about declining performance and offer support")
            
            if top_errors:
                recommendations.append(f"Address recurring error: {top_errors[0][0]}")
            
            if areas_for_improvement:
                recommendations.append(f"Focus feedback on weakest area: {areas_for_improvement[0]}")
            
            if strengths:
                recommendations.append(f"Acknowledge strength: {strengths[0]}")
            
            return {
                "student_id": student_id,
                "total_submissions": len(sessions),
                "average_score": round(average_score, 2) if average_score else None,
                "common_errors": common_errors[:5],
                "top_error_categories": [{"category": cat, "count": count} for cat, count in top_errors],
                "improvement_trend": improvement_trend,
                "strengths": strengths,
                "areas_for_improvement": areas_for_improvement,
                "recommendations": recommendations,
                "criterion_performance": {
                    k: round(sum(v) / len(v), 2) for k, v in criterion_performance.items()
                }
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "student_id": student_id,
            "total_submissions": 0,
            "average_score": None,
            "common_errors": [],
            "improvement_trend": "error",
            "strengths": [],
            "areas_for_improvement": [],
            "recommendations": [],
            "error": str(e)
        }


def get_professor_grading_style(
    professor_id: str,
    rubric_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: Get professor's grading style profile from L3.
    
    Analyzes professor's past gradings and corrections to identify
    their grading patterns, preferences, and biases.
    
    Args:
        professor_id: Professor's user ID
        rubric_type: Optional rubric type to filter by
    
    Returns:
        Dictionary containing:
        - professor_id: Professor identifier
        - total_gradings: Number of past gradings
        - average_strictness: How strict the professor is (0-1)
        - criterion_preferences: Which criteria they weigh more heavily
        - common_corrections: Common types of corrections they make
        - grading_patterns: Identified grading patterns
    """
    if not DATABASE_AVAILABLE:
        return {
            "professor_id": professor_id,
            "total_gradings": 0,
            "average_strictness": None,
            "criterion_preferences": {},
            "common_corrections": [],
            "grading_patterns": [],
            "error": "Database not configured"
        }
    
    try:
        db = get_session()
        try:
            # Get professor's grading sessions
            filters = [GradingSession.professor_id == professor_id]
            if rubric_type:
                filters.append(GradingSession.grading_type == rubric_type)
            
            sessions = db.query(GradingSession).filter(
                and_(*filters)
            ).limit(50).all()
            
            if not sessions:
                return {
                    "professor_id": professor_id,
                    "total_gradings": 0,
                    "average_strictness": None,
                    "criterion_preferences": {},
                    "common_corrections": [],
                    "grading_patterns": []
                }
            
            # Calculate average strictness (how often they correct AI grades)
            reviewed_sessions = [s for s in sessions if s.reviewed_by_professor]
            corrections = [s for s in reviewed_sessions if s.professor_feedback != s.ai_feedback]
            strictness = len(corrections) / len(reviewed_sessions) if reviewed_sessions else None
            
            # Analyze criterion preferences
            criterion_weights = {}
            for session in sessions:
                if session.criterion_scores:
                    for criterion, score in session.criterion_scores.items():
                        if criterion not in criterion_weights:
                            criterion_weights[criterion] = []
                        # Higher variance in scores indicates more emphasis
                        criterion_weights[criterion].append(score)
            
            criterion_preferences = {}
            for criterion, scores in criterion_weights.items():
                avg = sum(scores) / len(scores)
                variance = sum((x - avg) ** 2 for x in scores) / len(scores)
                criterion_preferences[criterion] = {
                    "average_score": round(avg, 2),
                    "variance": round(variance, 2),
                    "emphasis": "high" if variance > 100 else "medium" if variance > 50 else "low"
                }
            
            # Get common corrections
            exception_filters = [
                GradeException.user_id == professor_id,
                GradeException.exception_type == 'grading_correction'
            ]
            if rubric_type:
                exception_filters.append(GradeException.rubric_type == rubric_type)
            
            exceptions = db.query(GradeException).filter(
                and_(*exception_filters)
            ).limit(20).all()
            
            correction_categories = {}
            for exc in exceptions:
                if exc.error_category:
                    correction_categories[exc.error_category] = correction_categories.get(exc.error_category, 0) + 1
            
            common_corrections = [
                {"category": cat, "count": count}
                for cat, count in sorted(correction_categories.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            
            # Identify patterns
            patterns = []
            
            if strictness and strictness > 0.3:
                patterns.append("Frequently reviews and corrects AI grades")
            elif strictness and strictness < 0.1:
                patterns.append("Generally trusts AI grading")
            
            for criterion, data in criterion_preferences.items():
                if data["emphasis"] == "high":
                    patterns.append(f"Places high emphasis on '{criterion}' criterion")
            
            return {
                "professor_id": professor_id,
                "total_gradings": len(sessions),
                "total_reviewed": len(reviewed_sessions),
                "average_strictness": round(strictness, 2) if strictness else None,
                "criterion_preferences": criterion_preferences,
                "common_corrections": common_corrections,
                "grading_patterns": patterns,
                "rubric_type": rubric_type
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "professor_id": professor_id,
            "total_gradings": 0,
            "average_strictness": None,
            "criterion_preferences": {},
            "common_corrections": [],
            "grading_patterns": [],
            "error": str(e)
        }


# Export as LangChain tools
def get_ml_profiling_tools():
    """
    Get ML profiling tools for LangChain agents.
    
    Returns list of tools for:
    - Checking past professor overrides
    - Getting student profiles
    - Getting professor grading styles
    """
    from langchain.tools import Tool
    
    return [
        Tool(
            name="check_past_overrides",
            func=lambda params: check_past_overrides(**params),
            description="""Check past professor override patterns from L3 Learning Store.
            
Input: JSON with professor_id, rubric_type, and optional limit.
Example: {"professor_id": "prof123", "rubric_type": "essay", "limit": 20}

Returns patterns of AI grade corrections and systematic biases.
Use this to decide if grade reconciliation is needed."""
        ),
        Tool(
            name="get_student_profile",
            func=lambda params: get_student_profile(**params),
            description="""Get student learning profile from L3.
            
Input: JSON with student_id, optional professor_id and course_id.
Example: {"student_id": "student456", "professor_id": "prof123"}

Returns historical performance, common errors, and personalization recommendations.
Use this to personalize feedback."""
        ),
        Tool(
            name="get_professor_grading_style",
            func=lambda params: get_professor_grading_style(**params),
            description="""Get professor's grading style profile from L3.
            
Input: JSON with professor_id and optional rubric_type.
Example: {"professor_id": "prof123", "rubric_type": "essay"}

Returns grading patterns, criterion preferences, and common corrections.
Use this to align AI grading with professor's style."""
        )
    ]

