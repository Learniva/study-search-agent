"""
Adaptive Rubric System

Rubrics that learn from professor feedback and adapt over time.
Improves AI-professor grading agreement and consistency.
"""

import os
import json
import copy
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict, deque


class AdaptiveRubric:
    """
    Rubric that learns from grading patterns and professor feedback.
    
    Features:
    - Learns from professor corrections
    - Adjusts criterion weights
    - Adapts thresholds
    - Tracks adjustment history
    - Per-professor customization
    """
    
    def __init__(self, base_rubric: Dict[str, Any], rubric_id: str = "default"):
        """
        Initialize adaptive rubric.
        
        Args:
            base_rubric: Base rubric structure with criteria
            rubric_id: Unique identifier for this rubric
        """
        self.rubric_id = rubric_id
        self.base_rubric = base_rubric
        self.base_criteria = base_rubric.get('criteria', [])
        
        # Initialize learned weights (1.0 = no adjustment)
        self.learned_weights = {}
        for criterion in self.base_criteria:
            name = criterion.get('name', 'unknown')
            self.learned_weights[name] = 1.0
        
        # Track adjustments
        self.adjustment_history = deque(maxlen=100)  # Keep last 100 adjustments
        
        # Learning parameters
        self.learning_rate = 0.05  # How fast to adapt
        self.min_weight = 0.5  # Minimum weight multiplier
        self.max_weight = 2.0  # Maximum weight multiplier
        
        # Statistics
        self.total_gradings = 0
        self.professor_adjustments = 0
        self.total_error = 0.0
        
        print(f"📋 Adaptive Rubric initialized: {rubric_id}")
    
    def adapt_from_feedback(
        self,
        criterion_name: str,
        ai_score: float,
        professor_score: float,
        submission_context: Optional[str] = None
    ):
        """
        Adapt rubric based on professor correction.
        
        Uses gradient descent to adjust weights based on error.
        
        Args:
            criterion_name: Name of criterion being adjusted
            ai_score: AI's original score
            professor_score: Professor's corrected score
            submission_context: Optional context about the submission
        """
        if criterion_name not in self.learned_weights:
            print(f"⚠️  Unknown criterion: {criterion_name}")
            return
        
        # Calculate error
        error = professor_score - ai_score
        
        # Update weight using gradient descent
        # Positive error = AI scored too low → increase weight
        # Negative error = AI scored too high → decrease weight
        adjustment = self.learning_rate * error
        old_weight = self.learned_weights[criterion_name]
        new_weight = old_weight + adjustment
        
        # Clip to reasonable range
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))
        
        self.learned_weights[criterion_name] = new_weight
        
        # Record adjustment
        adjustment_record = {
            'timestamp': datetime.now().isoformat(),
            'criterion': criterion_name,
            'ai_score': ai_score,
            'professor_score': professor_score,
            'error': error,
            'adjustment': adjustment,
            'old_weight': old_weight,
            'new_weight': new_weight,
            'context': submission_context
        }
        
        self.adjustment_history.append(adjustment_record)
        
        # Update statistics
        self.professor_adjustments += 1
        self.total_error += abs(error)
        
        print(f"📊 Adapted '{criterion_name}': weight {old_weight:.2f} → {new_weight:.2f} "
              f"(error: {error:+.1f})")
    
    def get_adapted_rubric(self) -> Dict[str, Any]:
        """
        Get rubric with learned adjustments applied.
        
        Returns:
            Adapted rubric with modified criterion weights
        """
        adapted = copy.deepcopy(self.base_rubric)
        
        # Apply learned weights to criteria
        if 'criteria' in adapted:
            for criterion in adapted['criteria']:
                name = criterion.get('name', 'unknown')
                if name in self.learned_weights:
                    # Apply learned weight multiplier
                    original_weight = criterion.get('weight', 1.0)
                    criterion['weight'] = original_weight * self.learned_weights[name]
                    
                    # Add metadata about adaptation
                    criterion['adapted'] = True
                    criterion['original_weight'] = original_weight
                    criterion['weight_multiplier'] = self.learned_weights[name]
        
        # Renormalize weights to sum to 1.0
        if 'criteria' in adapted:
            total_weight = sum(c.get('weight', 0) for c in adapted['criteria'])
            if total_weight > 0:
                for criterion in adapted['criteria']:
                    criterion['weight'] /= total_weight
        
        # Add adaptation metadata
        adapted['is_adapted'] = True
        adapted['total_gradings'] = self.total_gradings
        adapted['professor_adjustments'] = self.professor_adjustments
        adapted['avg_error'] = self.total_error / self.professor_adjustments if self.professor_adjustments > 0 else 0
        
        return adapted
    
    def get_adaptation_stats(self) -> Dict[str, Any]:
        """Get statistics about rubric adaptation."""
        avg_error = self.total_error / self.professor_adjustments if self.professor_adjustments > 0 else 0
        
        # Calculate weight changes
        weight_changes = {}
        for name, weight in self.learned_weights.items():
            change_pct = (weight - 1.0) * 100
            weight_changes[name] = {
                'current_weight': weight,
                'change_from_base': f"{change_pct:+.1f}%"
            }
        
        # Recent adjustments summary
        recent_adjustments = list(self.adjustment_history)[-10:]  # Last 10
        
        return {
            'rubric_id': self.rubric_id,
            'total_gradings': self.total_gradings,
            'professor_adjustments': self.professor_adjustments,
            'avg_absolute_error': f"{avg_error:.2f}",
            'adjustment_rate': f"{(self.professor_adjustments / self.total_gradings * 100):.1f}%" if self.total_gradings > 0 else "N/A",
            'weight_changes': weight_changes,
            'recent_adjustments': recent_adjustments
        }
    
    def save_to_file(self, filepath: str):
        """Save adaptive rubric state to file."""
        data = {
            'rubric_id': self.rubric_id,
            'base_rubric': self.base_rubric,
            'learned_weights': self.learned_weights,
            'adjustment_history': list(self.adjustment_history),
            'statistics': {
                'total_gradings': self.total_gradings,
                'professor_adjustments': self.professor_adjustments,
                'total_error': self.total_error
            },
            'saved_at': datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Adaptive rubric saved: {filepath}")
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'AdaptiveRubric':
        """Load adaptive rubric state from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        rubric = cls(
            base_rubric=data['base_rubric'],
            rubric_id=data['rubric_id']
        )
        
        rubric.learned_weights = data['learned_weights']
        rubric.adjustment_history = deque(data['adjustment_history'], maxlen=100)
        
        stats = data.get('statistics', {})
        rubric.total_gradings = stats.get('total_gradings', 0)
        rubric.professor_adjustments = stats.get('professor_adjustments', 0)
        rubric.total_error = stats.get('total_error', 0.0)
        
        print(f"📂 Adaptive rubric loaded: {filepath}")
        return rubric


class ConsistencyChecker:
    """
    Check grading consistency and suggest improvements.
    
    Analyzes professor's grading patterns to identify:
    - Systematic biases
    - Inconsistencies
    - Areas needing calibration
    """
    
    def __init__(self):
        self.grading_history = []
    
    def add_grading(
        self,
        ai_score: float,
        professor_score: float,
        grading_type: str,
        criterion_scores: Optional[Dict[str, float]] = None
    ):
        """Add a grading to history for analysis."""
        self.grading_history.append({
            'ai_score': ai_score,
            'professor_score': professor_score,
            'grading_type': grading_type,
            'criterion_scores': criterion_scores or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def check_consistency(
        self,
        grading_type: Optional[str] = None,
        lookback: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze grading consistency.
        
        Args:
            grading_type: Filter by type (essay, code, etc.)
            lookback: Number of recent gradings to analyze
            
        Returns:
            Consistency report with metrics and recommendations
        """
        # Filter history
        history = self.grading_history[-lookback:]
        
        if grading_type:
            history = [g for g in history if g['grading_type'] == grading_type]
        
        if len(history) < 5:
            return {
                'status': 'insufficient_data',
                'message': f'Need at least 5 gradings (have {len(history)})',
                'gradings_count': len(history)
            }
        
        # Calculate metrics
        ai_scores = [g['ai_score'] for g in history]
        prof_scores = [g['professor_score'] for g in history]
        differences = [abs(a - p) for a, p in zip(ai_scores, prof_scores)]
        
        avg_difference = sum(differences) / len(differences)
        max_difference = max(differences)
        
        # Agreement rate (within 5 points)
        agreement_count = sum(1 for d in differences if d < 5)
        agreement_rate = (agreement_count / len(differences)) * 100
        
        # Systematic bias
        bias = sum(prof_scores) / len(prof_scores) - sum(ai_scores) / len(ai_scores)
        
        # Consistency score (lower variance = more consistent)
        variance = sum((d - avg_difference) ** 2 for d in differences) / len(differences)
        consistency_score = max(0, 100 - variance)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            avg_difference,
            agreement_rate,
            bias,
            consistency_score
        )
        
        return {
            'status': 'analyzed',
            'gradings_count': len(history),
            'grading_type': grading_type or 'all',
            'metrics': {
                'avg_difference': f"{avg_difference:.2f}",
                'max_difference': f"{max_difference:.2f}",
                'agreement_rate': f"{agreement_rate:.1f}%",
                'systematic_bias': f"{bias:+.2f}",
                'consistency_score': f"{consistency_score:.1f}/100"
            },
            'recommendation': recommendation,
            'calibration_needed': abs(bias) > 5 or agreement_rate < 70
        }
    
    def _generate_recommendation(
        self,
        avg_diff: float,
        agreement: float,
        bias: float,
        consistency: float
    ) -> str:
        """Generate recommendation based on metrics."""
        if avg_diff < 3 and agreement > 90:
            return "✅ Excellent consistency - AI is well-calibrated"
        
        elif abs(bias) > 7:
            direction = "lower" if bias > 0 else "higher"
            return f"⚠️  Systematic bias detected: AI tends to grade {abs(bias):.1f} points {direction}. Consider rubric adjustment."
        
        elif agreement < 70:
            return "⚠️  Low agreement rate. Review rubric criteria with AI to improve alignment."
        
        elif consistency < 60:
            return "⚠️  High variance in differences. Grading criteria may need clarification."
        
        elif avg_diff < 5 and agreement > 80:
            return "✅ Good consistency - Minor improvements possible"
        
        else:
            return "💡 Moderate consistency - Continue monitoring and adjusting"


class AdaptiveRubricManager:
    """
    Manage multiple adaptive rubrics for different professors and assignment types.
    """
    
    def __init__(self, storage_dir: str = ".adaptive_rubrics"):
        """
        Initialize adaptive rubric manager.
        
        Args:
            storage_dir: Directory to store rubric data
        """
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
        # Cache of loaded rubrics
        self.rubrics = {}  # key: (professor_id, rubric_type)
        
        # Consistency checkers per professor
        self.consistency_checkers = defaultdict(ConsistencyChecker)
        
        print(f"📋 Adaptive Rubric Manager initialized (storage: {storage_dir})")
    
    def get_or_create_rubric(
        self,
        professor_id: str,
        rubric_type: str,
        base_rubric: Dict[str, Any]
    ) -> AdaptiveRubric:
        """
        Get existing adaptive rubric or create new one.
        
        Args:
            professor_id: Professor identifier
            rubric_type: Type of rubric (essay, code, etc.)
            base_rubric: Base rubric structure
            
        Returns:
            AdaptiveRubric instance
        """
        key = (professor_id, rubric_type)
        
        # Check cache
        if key in self.rubrics:
            return self.rubrics[key]
        
        # Try to load from file
        filepath = self._get_rubric_filepath(professor_id, rubric_type)
        
        if os.path.exists(filepath):
            rubric = AdaptiveRubric.load_from_file(filepath)
        else:
            # Create new
            rubric_id = f"{professor_id}_{rubric_type}"
            rubric = AdaptiveRubric(base_rubric, rubric_id)
        
        # Cache it
        self.rubrics[key] = rubric
        
        return rubric
    
    def record_grading(
        self,
        professor_id: str,
        rubric_type: str,
        ai_scores: Dict[str, float],
        professor_scores: Optional[Dict[str, float]] = None,
        overall_ai_score: Optional[float] = None,
        overall_professor_score: Optional[float] = None
    ):
        """
        Record a grading and update adaptive rubric if professor made corrections.
        
        Args:
            professor_id: Professor identifier
            rubric_type: Type of rubric
            ai_scores: AI's criterion scores
            professor_scores: Professor's corrected scores (if any)
            overall_ai_score: Overall AI score
            overall_professor_score: Overall professor score
        """
        key = (professor_id, rubric_type)
        
        if key not in self.rubrics:
            print(f"⚠️  No rubric found for {professor_id}/{rubric_type}")
            return
        
        rubric = self.rubrics[key]
        rubric.total_gradings += 1
        
        # Update consistency checker
        if overall_ai_score and overall_professor_score:
            checker = self.consistency_checkers[professor_id]
            checker.add_grading(
                overall_ai_score,
                overall_professor_score,
                rubric_type,
                professor_scores
            )
        
        # If professor made corrections, adapt rubric
        if professor_scores:
            for criterion_name, prof_score in professor_scores.items():
                ai_score = ai_scores.get(criterion_name)
                
                if ai_score is not None and prof_score != ai_score:
                    rubric.adapt_from_feedback(
                        criterion_name,
                        ai_score,
                        prof_score
                    )
        
        # Save updated rubric
        self._save_rubric(rubric, professor_id, rubric_type)
    
    def get_consistency_report(
        self,
        professor_id: str,
        grading_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get consistency report for a professor."""
        checker = self.consistency_checkers[professor_id]
        return checker.check_consistency(grading_type)
    
    def _get_rubric_filepath(self, professor_id: str, rubric_type: str) -> str:
        """Get filepath for rubric storage."""
        safe_prof_id = professor_id.replace('/', '_').replace('\\', '_')
        safe_type = rubric_type.replace('/', '_').replace('\\', '_')
        return os.path.join(self.storage_dir, f"{safe_prof_id}_{safe_type}.json")
    
    def _save_rubric(self, rubric: AdaptiveRubric, professor_id: str, rubric_type: str):
        """Save rubric to file."""
        filepath = self._get_rubric_filepath(professor_id, rubric_type)
        rubric.save_to_file(filepath)


# Global manager instance
_adaptive_rubric_manager = None


def get_adaptive_rubric_manager() -> AdaptiveRubricManager:
    """Get or create global adaptive rubric manager."""
    global _adaptive_rubric_manager
    if _adaptive_rubric_manager is None:
        _adaptive_rubric_manager = AdaptiveRubricManager()
    return _adaptive_rubric_manager

