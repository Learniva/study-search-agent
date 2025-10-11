#!/usr/bin/env python3
"""
CLI tool for managing A/B testing experiments.

Usage:
    python -m utils.routing.ab_cli create --experiment-id routing_v2 --name "New Patterns"
    python -m utils.routing.ab_cli list
    python -m utils.routing.ab_cli stats --experiment-id routing_v2
    python -m utils.routing.ab_cli compare --experiment-id routing_v2
    python -m utils.routing.ab_cli pause --experiment-id routing_v2
    python -m utils.routing.ab_cli resume --experiment-id routing_v2
    python -m utils.routing.ab_cli complete --experiment-id routing_v2
"""

import argparse
import json
from .ab_testing import get_ab_testing_framework


def cmd_create(args):
    """Create a new A/B test experiment."""
    framework = get_ab_testing_framework()
    
    # Default variants for routing experiments
    variants = {
        "control": {
            "routing": "pattern",
            "pattern_set": "current"
        },
        "treatment": {
            "routing": args.routing or "pattern",
            "pattern_set": args.pattern_set or "new"
        }
    }
    
    traffic_split = {
        "control": args.control_traffic,
        "treatment": args.treatment_traffic
    }
    
    experiment = framework.create_experiment(
        experiment_id=args.experiment_id,
        name=args.name,
        description=args.description or f"A/B test for {args.name}",
        variants=variants,
        traffic_split=traffic_split
    )
    
    print(f"✅ Created experiment: {experiment.name}")
    print(f"   ID: {experiment.experiment_id}")
    print(f"   Traffic split: {experiment.traffic_split}")
    print(f"   Status: {experiment.status}")


def cmd_list(args):
    """List all experiments."""
    framework = get_ab_testing_framework()
    
    if not framework.experiments:
        print("No experiments found.")
        return
    
    print(f"\n{'='*80}")
    print(f"A/B TEST EXPERIMENTS")
    print(f"{'='*80}\n")
    
    for exp_id, exp in framework.experiments.items():
        status_emoji = "🟢" if exp.status == "active" else "⏸️" if exp.status == "paused" else "✅"
        print(f"{status_emoji} {exp.name}")
        print(f"   ID: {exp.experiment_id}")
        print(f"   Status: {exp.status}")
        print(f"   Started: {exp.start_date}")
        print(f"   Variants: {', '.join(exp.variants.keys())}")
        print(f"   Traffic: {exp.traffic_split}")
        print()


def cmd_stats(args):
    """Show statistics for an experiment."""
    framework = get_ab_testing_framework()
    
    stats = framework.get_experiment_stats(args.experiment_id, days=args.days)
    
    if not stats:
        print(f"No data found for experiment: {args.experiment_id}")
        return
    
    print(f"\n{'='*80}")
    print(f"EXPERIMENT STATISTICS: {args.experiment_id}")
    print(f"Last {args.days} days")
    print(f"{'='*80}\n")
    
    for variant, data in stats.items():
        print(f"📊 {variant.upper()}")
        print(f"   Total Requests: {data['total_requests']}")
        print(f"   Success Rate: {data['success_rate']:.2%}")
        print(f"   Avg Latency: {data['avg_latency_ms']:.1f}ms")
        print(f"   Median Latency: {data['median_latency_ms']:.1f}ms")
        print(f"   P95 Latency: {data['p95_latency_ms']:.1f}ms")
        print(f"   User Satisfaction: {data['user_satisfaction']:.2f}/1.0")
        print()


def cmd_compare(args):
    """Compare variants and show winner."""
    framework = get_ab_testing_framework()
    
    comparison = framework.compare_variants(args.experiment_id, days=args.days)
    
    print(f"\n{'='*80}")
    print(f"VARIANT COMPARISON: {args.experiment_id}")
    print(f"{'='*80}\n")
    
    winner = comparison.get("winner", "unknown")
    confidence = comparison.get("confidence", 0.0)
    recommendation = comparison.get("recommendation", "")
    
    if winner == "insufficient_data":
        print("⚠️  INSUFFICIENT DATA")
        print(f"   {recommendation}")
    elif winner == "no_significant_difference":
        print("🤝 NO SIGNIFICANT DIFFERENCE")
        print(f"   Confidence: {confidence:.0%}")
        print(f"   Recommendation: {recommendation}")
    else:
        print(f"🏆 WINNER: {winner.upper()}")
        print(f"   Confidence: {confidence:.0%}")
        print(f"   Recommendation: {recommendation}")
    
    print("\n📊 Detailed Stats:")
    for variant, data in comparison.get("stats", {}).items():
        print(f"\n   {variant}:")
        print(f"     Requests: {data['total_requests']}")
        print(f"     Success Rate: {data['success_rate']:.2%}")
        print(f"     Avg Latency: {data['avg_latency_ms']:.1f}ms")


def cmd_pause(args):
    """Pause an experiment."""
    framework = get_ab_testing_framework()
    framework.pause_experiment(args.experiment_id)
    print(f"⏸️  Paused experiment: {args.experiment_id}")


def cmd_resume(args):
    """Resume an experiment."""
    framework = get_ab_testing_framework()
    framework.resume_experiment(args.experiment_id)
    print(f"▶️  Resumed experiment: {args.experiment_id}")


def cmd_complete(args):
    """Complete an experiment."""
    framework = get_ab_testing_framework()
    framework.complete_experiment(args.experiment_id)
    print(f"✅ Completed experiment: {args.experiment_id}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="A/B Testing CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create experiment
    create_parser = subparsers.add_parser("create", help="Create new experiment")
    create_parser.add_argument("--experiment-id", required=True, help="Unique experiment ID")
    create_parser.add_argument("--name", required=True, help="Experiment name")
    create_parser.add_argument("--description", help="Description")
    create_parser.add_argument("--routing", default="pattern", help="Routing method")
    create_parser.add_argument("--pattern-set", default="new", help="Pattern set version")
    create_parser.add_argument("--control-traffic", type=float, default=0.5, help="Control traffic (0-1)")
    create_parser.add_argument("--treatment-traffic", type=float, default=0.5, help="Treatment traffic (0-1)")
    create_parser.set_defaults(func=cmd_create)
    
    # List experiments
    list_parser = subparsers.add_parser("list", help="List all experiments")
    list_parser.set_defaults(func=cmd_list)
    
    # Show stats
    stats_parser = subparsers.add_parser("stats", help="Show experiment statistics")
    stats_parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    stats_parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Compare variants
    compare_parser = subparsers.add_parser("compare", help="Compare variants")
    compare_parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    compare_parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    compare_parser.set_defaults(func=cmd_compare)
    
    # Pause experiment
    pause_parser = subparsers.add_parser("pause", help="Pause experiment")
    pause_parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    pause_parser.set_defaults(func=cmd_pause)
    
    # Resume experiment
    resume_parser = subparsers.add_parser("resume", help="Resume experiment")
    resume_parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    resume_parser.set_defaults(func=cmd_resume)
    
    # Complete experiment
    complete_parser = subparsers.add_parser("complete", help="Complete experiment")
    complete_parser.add_argument("--experiment-id", required=True, help="Experiment ID")
    complete_parser.set_defaults(func=cmd_complete)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

