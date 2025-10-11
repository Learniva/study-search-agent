"""
Routing Utilities Package

Tool and agent routing utilities:
- routing: Fast pattern-based routing (80-90% faster, no LLM)
- performance: Performance-based routing with monitoring
- ab_testing: A/B testing framework for routing strategy experiments
"""

from .routing import (
    pattern_based_route,
    fast_study_route,
    fast_grading_route,
    fast_intent_classification,
    calculate_text_similarity,
    find_similar_queries,
    STUDY_AGENT_PATTERNS,
    GRADING_AGENT_PATTERNS,
    SUPERVISOR_INTENT_PATTERNS,
)

from .performance import (
    PerformanceMonitor,
    ToolPerformanceTracker,
    PerformanceBasedRouter,
    RequestMetrics,
    get_performance_monitor,
    log_request,
    print_performance_report,
    get_performance_stats,
    get_performance_router,
    save_performance_router,
)

from .ab_testing import (
    ABTestingFramework,
    ABExperiment,
    ABTestResult,
    get_ab_testing_framework,
    track_routing_decision,
)

__all__ = [
    # Pattern routing
    'pattern_based_route',
    'fast_study_route',
    'fast_grading_route',
    'fast_intent_classification',
    'calculate_text_similarity',
    'find_similar_queries',
    'STUDY_AGENT_PATTERNS',
    'GRADING_AGENT_PATTERNS',
    'SUPERVISOR_INTENT_PATTERNS',
    
    # Performance routing
    'PerformanceMonitor',
    'ToolPerformanceTracker',
    'PerformanceBasedRouter',
    'RequestMetrics',
    'get_performance_monitor',
    'log_request',
    'print_performance_report',
    'get_performance_stats',
    'get_performance_router',
    'save_performance_router',
    
    # A/B Testing
    'ABTestingFramework',
    'ABExperiment',
    'ABTestResult',
    'get_ab_testing_framework',
    'track_routing_decision',
]


