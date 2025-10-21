"""
A/B Testing Framework for Routing Strategies

Allows experimentation with different routing approaches:
- Pattern-based vs LLM-based routing
- Different pattern sets
- Confidence thresholds
- Fallback strategies

Tracks performance metrics:
- Routing accuracy
- Response time
- User satisfaction
- Tool success rates
"""

import json
import os
import random
import time
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ABExperiment:
    """Configuration for an A/B test experiment."""
    experiment_id: str
    name: str
    description: str
    variants: Dict[str, Dict[str, Any]]  # {"variant_a": {config}, "variant_b": {config}}
    traffic_split: Dict[str, float]  # {"variant_a": 0.5, "variant_b": 0.5}
    metrics_to_track: List[str]  # ["accuracy", "latency", "user_satisfaction"]
    start_date: str
    end_date: Optional[str] = None
    status: Literal["active", "paused", "completed"] = "active"


@dataclass
class ABTestResult:
    """Result of a single A/B test interaction."""
    experiment_id: str
    variant: str
    timestamp: str
    query: str
    predicted_intent: str
    actual_tool: str
    routing_method: str  # "pattern" or "llm"
    latency_ms: float
    success: bool
    user_satisfaction: Optional[float] = None  # 0-1 scale
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ABTestingFramework:
    """
    A/B Testing framework for routing strategy experiments.
    
    Features:
    - Traffic splitting (e.g., 50/50, 70/30)
    - Multiple concurrent experiments
    - Metric tracking (accuracy, latency, satisfaction)
    - Statistical analysis
    - Experiment management (start, pause, stop)
    - Logging of routing decisions
    """
    
    def __init__(self, experiments_dir: str = "experiments"):
        """Initialize A/B testing framework."""
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(exist_ok=True)
        
        self.results_dir = self.experiments_dir / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        self.experiments: Dict[str, ABExperiment] = {}
        self.load_experiments()
    
    def load_experiments(self):
        """Load active experiments from disk."""
        config_file = self.experiments_dir / "experiments.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                for exp_data in data.get("experiments", []):
                    exp = ABExperiment(**exp_data)
                    self.experiments[exp.experiment_id] = exp
    
    def save_experiments(self):
        """Save experiments to disk."""
        config_file = self.experiments_dir / "experiments.json"
        data = {
            "experiments": [asdict(exp) for exp in self.experiments.values()]
        }
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        variants: Dict[str, Dict[str, Any]],
        traffic_split: Optional[Dict[str, float]] = None
    ) -> ABExperiment:
        """
        Create a new A/B test experiment.
        
        Args:
            experiment_id: Unique identifier
            name: Human-readable name
            description: What is being tested
            variants: Configuration for each variant
            traffic_split: Traffic distribution (defaults to equal split)
        
        Example:
            framework.create_experiment(
                experiment_id="routing_pattern_v2",
                name="New Pattern Set vs Current",
                description="Test improved pattern matching",
                variants={
                    "control": {"routing": "pattern", "pattern_set": "v1"},
                    "treatment": {"routing": "pattern", "pattern_set": "v2"}
                },
                traffic_split={"control": 0.5, "treatment": 0.5}
            )
        """
        if traffic_split is None:
            # Equal split
            n = len(variants)
            traffic_split = {v: 1.0/n for v in variants}
        
        # Validate traffic split sums to 1.0
        if abs(sum(traffic_split.values()) - 1.0) > 0.01:
            raise ValueError("Traffic split must sum to 1.0")
        
        experiment = ABExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            variants=variants,
            traffic_split=traffic_split,
            metrics_to_track=["accuracy", "latency", "success_rate"],
            start_date=datetime.utcnow().isoformat(),
            status="active"
        )
        
        self.experiments[experiment_id] = experiment
        self.save_experiments()
        
        return experiment
    
    def assign_variant(self, experiment_id: str, user_id: Optional[str] = None) -> str:
        """
        Assign a variant for this request.
        
        Args:
            experiment_id: Which experiment
            user_id: User identifier (for consistent assignment)
        
        Returns:
            Variant name (e.g., "control", "treatment")
        """
        experiment = self.experiments.get(experiment_id)
        if not experiment or experiment.status != "active":
            # Default to first variant if experiment not active
            return list(experiment.variants.keys())[0] if experiment else "control"
        
        if user_id:
            # Consistent assignment based on user_id
            # Simple hash-based assignment
            hash_val = hash(f"{experiment_id}:{user_id}")
            rand_val = (hash_val % 1000) / 1000.0
        else:
            # Random assignment
            rand_val = random.random()
        
        # Assign based on traffic split
        cumulative = 0.0
        for variant, split in experiment.traffic_split.items():
            cumulative += split
            if rand_val < cumulative:
                return variant
        
        # Fallback to first variant
        return list(experiment.variants.keys())[0]
    
    def get_variant_config(self, experiment_id: str, variant: str) -> Dict[str, Any]:
        """Get configuration for a specific variant."""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return {}
        
        return experiment.variants.get(variant, {})
    
    def log_result(self, result: ABTestResult):
        """
        Log a single A/B test result.
        
        Args:
            result: ABTestResult containing all metrics
        """
        # Append to daily results file
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        results_file = self.results_dir / f"{result.experiment_id}_{date_str}.jsonl"
        
        with open(results_file, 'a') as f:
            f.write(json.dumps(asdict(result)) + '\n')
    
    def get_experiment_stats(
        self,
        experiment_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Calculate statistics for an experiment.
        
        Args:
            experiment_id: Which experiment
            days: Number of days to analyze
        
        Returns:
            Dictionary with stats per variant:
            {
                "control": {
                    "total_requests": 1000,
                    "accuracy": 0.85,
                    "avg_latency_ms": 120,
                    "success_rate": 0.92,
                    "user_satisfaction": 0.78
                },
                "treatment": {...}
            }
        """
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return {}
        
        # Load results from last N days
        results_by_variant = {v: [] for v in experiment.variants.keys()}
        
        from datetime import timedelta
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            results_file = self.results_dir / f"{experiment_id}_{date_str}.jsonl"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    for line in f:
                        result = json.loads(line)
                        variant = result.get("variant")
                        if variant in results_by_variant:
                            results_by_variant[variant].append(result)
        
        # Calculate stats per variant
        stats = {}
        for variant, results in results_by_variant.items():
            if not results:
                stats[variant] = {
                    "total_requests": 0,
                    "accuracy": 0.0,
                    "avg_latency_ms": 0.0,
                    "success_rate": 0.0,
                    "user_satisfaction": 0.0
                }
                continue
            
            total = len(results)
            successful = sum(1 for r in results if r.get("success", False))
            latencies = [r.get("latency_ms", 0) for r in results]
            satisfactions = [r.get("user_satisfaction") for r in results if r.get("user_satisfaction") is not None]
            
            stats[variant] = {
                "total_requests": total,
                "success_rate": successful / total if total > 0 else 0.0,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "median_latency_ms": sorted(latencies)[len(latencies)//2] if latencies else 0.0,
                "p95_latency_ms": sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0.0,
                "user_satisfaction": sum(satisfactions) / len(satisfactions) if satisfactions else 0.0,
            }
        
        return stats
    
    def compare_variants(self, experiment_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Compare variants and determine if there's a statistically significant difference.
        
        Returns:
            {
                "winner": "treatment" or "control" or "no_significant_difference",
                "confidence": 0.95,
                "stats": {...},
                "recommendation": "Switch to treatment" or "Keep control"
            }
        """
        stats = self.get_experiment_stats(experiment_id, days)
        
        if len(stats) < 2:
            return {
                "winner": "insufficient_data",
                "confidence": 0.0,
                "stats": stats,
                "recommendation": "Collect more data"
            }
        
        # Simple comparison (for production, use proper statistical tests)
        variants = list(stats.keys())
        v1, v2 = variants[0], variants[1]
        
        s1, s2 = stats[v1], stats[v2]
        
        # Compare success rate (primary metric)
        success_diff = abs(s1["success_rate"] - s2["success_rate"])
        latency_diff = abs(s1["avg_latency_ms"] - s2["avg_latency_ms"])
        
        # Simple heuristic (should use t-test in production)
        min_requests = 100
        if s1["total_requests"] < min_requests or s2["total_requests"] < min_requests:
            return {
                "winner": "insufficient_data",
                "confidence": 0.0,
                "stats": stats,
                "recommendation": f"Collect at least {min_requests} samples per variant"
            }
        
        # If success rates are very close, consider latency
        if success_diff < 0.05:
            if latency_diff > 50:  # 50ms difference
                winner = v1 if s1["avg_latency_ms"] < s2["avg_latency_ms"] else v2
                return {
                    "winner": winner,
                    "confidence": 0.8,
                    "stats": stats,
                    "recommendation": f"Switch to {winner} (faster with similar accuracy)"
                }
            else:
                return {
                    "winner": "no_significant_difference",
                    "confidence": 0.9,
                    "stats": stats,
                    "recommendation": "Keep current implementation"
                }
        else:
            # Clear winner on success rate
            winner = v1 if s1["success_rate"] > s2["success_rate"] else v2
            return {
                "winner": winner,
                "confidence": 0.95,
                "stats": stats,
                "recommendation": f"Switch to {winner} (significantly better accuracy)"
            }
    
    def pause_experiment(self, experiment_id: str):
        """Pause an experiment."""
        if experiment_id in self.experiments:
            self.experiments[experiment_id].status = "paused"
            self.save_experiments()
    
    def resume_experiment(self, experiment_id: str):
        """Resume a paused experiment."""
        if experiment_id in self.experiments:
            self.experiments[experiment_id].status = "active"
            self.save_experiments()
    
    def complete_experiment(self, experiment_id: str):
        """Mark experiment as completed."""
        if experiment_id in self.experiments:
            self.experiments[experiment_id].status = "completed"
            self.experiments[experiment_id].end_date = datetime.utcnow().isoformat()
            self.save_experiments()


# Global instance
_ab_testing_framework = None


def get_ab_testing_framework() -> ABTestingFramework:
    """Get singleton A/B testing framework instance."""
    global _ab_testing_framework
    if _ab_testing_framework is None:
        experiments_dir = os.getenv("AB_TESTING_DIR", "experiments")
        _ab_testing_framework = ABTestingFramework(experiments_dir)
    return _ab_testing_framework


# Helper function for easy integration
def track_routing_decision(
    experiment_id: str,
    variant: str,
    query: str,
    predicted_intent: str,
    actual_tool: str,
    routing_method: str,
    latency_ms: float,
    success: bool,
    user_satisfaction: Optional[float] = None
):
    """
    Track a routing decision for A/B testing.
    
    Example:
        track_routing_decision(
            experiment_id="routing_v2",
            variant="treatment",
            query="What is photosynthesis?",
            predicted_intent="Web_Search",
            actual_tool="Web_Search",
            routing_method="pattern",
            latency_ms=45.2,
            success=True,
            user_satisfaction=0.9
        )
    """
    framework = get_ab_testing_framework()
    
    result = ABTestResult(
        experiment_id=experiment_id,
        variant=variant,
        timestamp=datetime.utcnow().isoformat(),
        query=query,
        predicted_intent=predicted_intent,
        actual_tool=actual_tool,
        routing_method=routing_method,
        latency_ms=latency_ms,
        success=success,
        user_satisfaction=user_satisfaction
    )
    
    framework.log_result(result)



