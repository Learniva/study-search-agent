"""
Performance Monitoring & Routing System

Combines two key features:
1. Performance Monitoring - Track metrics, response times, cache hits, cost savings
2. Performance-Based Routing - Route to best-performing tools based on metrics

Features:
- Track tool performance (response time, success rate, quality)
- Dynamic routing based on historical performance
- Cost tracking and savings analysis
- Health monitoring and automatic failover
- Fallback chains for reliability
- Persistent state across restarts
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    timestamp: datetime
    question: str
    response_time: float
    llm_calls: int
    pattern_routed: bool
    cache_hit: bool
    tool_used: Optional[str] = None
    tokens_used: Optional[int] = None
    

class PerformanceMonitor:
    """
    Monitor and track performance metrics across requests.
    
    Tracks:
    - Response times (avg, min, max)
    - Cache hit rates
    - Pattern routing success rates
    - LLM call reduction
    - Cost savings
    """
    
    def __init__(self):
        self.metrics: List[RequestMetrics] = []
        self.total_requests = 0
        self.cache_hits = 0
        self.pattern_routes = 0
        self.llm_routes = 0
        self.total_llm_calls = 0
        self.total_saved_llm_calls = 0
        
    def log_request(
        self,
        question: str,
        response_time: float,
        llm_calls: int,
        pattern_routed: bool = False,
        cache_hit: bool = False,
        tool_used: Optional[str] = None,
        tokens_used: Optional[int] = None
    ):
        """
        Log metrics for a single request.
        
        Args:
            question: The user's question
            response_time: Time taken in seconds
            llm_calls: Number of LLM API calls made
            pattern_routed: Whether pattern routing was used
            cache_hit: Whether result was from cache
            tool_used: Which tool was used
            tokens_used: Total tokens used
        """
        self.total_requests += 1
        
        if cache_hit:
            self.cache_hits += 1
            self.total_saved_llm_calls += 2  # Typical request saves 2-3 LLM calls
        
        if pattern_routed:
            self.pattern_routes += 1
            self.total_saved_llm_calls += 1  # Pattern routing saves 1 LLM call
        else:
            self.llm_routes += 1
        
        self.total_llm_calls += llm_calls
        
        # Store detailed metrics
        metric = RequestMetrics(
            timestamp=datetime.now(),
            question=question[:100],  # Truncate for storage
            response_time=response_time,
            llm_calls=llm_calls,
            pattern_routed=pattern_routed,
            cache_hit=cache_hit,
            tool_used=tool_used,
            tokens_used=tokens_used
        )
        self.metrics.append(metric)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        if self.total_requests == 0:
            return {
                'total_requests': 0,
                'message': 'No requests logged yet'
            }
        
        # Calculate response time stats
        response_times = [m.response_time for m in self.metrics]
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Calculate rates
        cache_hit_rate = (self.cache_hits / self.total_requests) * 100
        pattern_route_rate = (self.pattern_routes / self.total_requests) * 100
        
        # Calculate cost savings (assuming $0.002 per LLM call average)
        cost_per_llm_call = 0.002
        total_cost = self.total_llm_calls * cost_per_llm_call
        potential_cost = (self.total_llm_calls + self.total_saved_llm_calls) * cost_per_llm_call
        cost_saved = potential_cost - total_cost
        savings_rate = (cost_saved / potential_cost * 100) if potential_cost > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'avg_response_time': f"{avg_response_time:.2f}s",
            'min_response_time': f"{min_response_time:.2f}s",
            'max_response_time': f"{max_response_time:.2f}s",
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'pattern_route_rate': f"{pattern_route_rate:.1f}%",
            'llm_route_rate': f"{(100-pattern_route_rate):.1f}%",
            'total_llm_calls': self.total_llm_calls,
            'saved_llm_calls': self.total_saved_llm_calls,
            'actual_cost': f"${total_cost:.4f}",
            'potential_cost': f"${potential_cost:.4f}",
            'cost_saved': f"${cost_saved:.4f}",
            'savings_rate': f"{savings_rate:.1f}%"
        }
    
    def print_report(self):
        """Print a formatted performance report."""
        stats = self.get_stats()
        
        print("\n" + "="*70)
        print("📊 PERFORMANCE REPORT")
        print("="*70)
        
        if stats.get('message'):
            print(stats['message'])
            return
        
        print(f"\n📈 Request Statistics:")
        print(f"  Total Requests:     {stats['total_requests']}")
        print(f"  Avg Response Time:  {stats['avg_response_time']}")
        print(f"  Min Response Time:  {stats['min_response_time']}")
        print(f"  Max Response Time:  {stats['max_response_time']}")
        
        print(f"\n⚡ Optimization Impact:")
        print(f"  Cache Hit Rate:     {stats['cache_hit_rate']}")
        print(f"  Pattern Route Rate: {stats['pattern_route_rate']}")
        print(f"  LLM Route Rate:     {stats['llm_route_rate']}")
        
        print(f"\n💰 Cost Analysis:")
        print(f"  LLM Calls Made:     {stats['total_llm_calls']}")
        print(f"  LLM Calls Saved:    {stats['saved_llm_calls']}")
        print(f"  Actual Cost:        {stats['actual_cost']}")
        print(f"  Potential Cost:     {stats['potential_cost']}")
        print(f"  Cost Saved:         {stats['cost_saved']}")
        print(f"  Savings Rate:       {stats['savings_rate']}")
        
        print("\n" + "="*70 + "\n")
    
    def export_metrics(self, filepath: str = "performance_metrics.json"):
        """Export metrics to JSON file for analysis."""
        data = {
            'summary': self.get_stats(),
            'detailed_metrics': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'question': m.question,
                    'response_time': m.response_time,
                    'llm_calls': m.llm_calls,
                    'pattern_routed': m.pattern_routed,
                    'cache_hit': m.cache_hit,
                    'tool_used': m.tool_used,
                    'tokens_used': m.tokens_used
                }
                for m in self.metrics
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Metrics exported to {filepath}")


# =============================================================================
# TOOL PERFORMANCE TRACKING
# =============================================================================

class ToolPerformanceTracker:
    """
    Track performance metrics for each tool.
    
    Metrics:
    - Average response time
    - Success rate
    - Quality score (from user feedback)
    - Recent performance trend
    """
    
    def __init__(self, tool_name: str):
        """Initialize performance tracker for a tool."""
        self.tool_name = tool_name
        
        # Performance metrics
        self.call_count = 0
        self.success_count = 0
        self.total_response_time = 0.0
        self.avg_response_time = 0.0
        
        # Recent performance (last 20 calls)
        self.recent_calls = deque(maxlen=20)
        
        # Quality tracking
        self.quality_scores = []  # From user feedback
        self.avg_quality = 0.0
        
        # Trend tracking
        self.performance_trend = 0.0  # -1 to 1, positive = improving
        
        # Reliability
        self.consecutive_failures = 0
        self.max_consecutive_failures = 0
        
        # Last updated
        self.last_update = datetime.now()
    
    def record_call(
        self,
        success: bool,
        response_time: float,
        quality_score: Optional[float] = None,
        error: Optional[str] = None
    ):
        """
        Record a tool call.
        
        Args:
            success: Whether the call succeeded
            response_time: Response time in seconds
            quality_score: Optional quality rating (0-1)
            error: Optional error message
        """
        self.call_count += 1
        
        if success:
            self.success_count += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.max_consecutive_failures = max(
                self.max_consecutive_failures,
                self.consecutive_failures
            )
        
        # Update response time
        self.total_response_time += response_time
        self.avg_response_time = self.total_response_time / self.call_count
        
        # Record recent call
        call_record = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'response_time': response_time,
            'quality_score': quality_score,
            'error': error
        }
        self.recent_calls.append(call_record)
        
        # Update quality
        if quality_score is not None:
            self.quality_scores.append(quality_score)
            self.avg_quality = sum(self.quality_scores) / len(self.quality_scores)
        
        # Calculate performance trend
        self._update_trend()
        
        self.last_update = datetime.now()
    
    def _update_trend(self):
        """Calculate performance trend from recent calls."""
        if len(self.recent_calls) < 10:
            self.performance_trend = 0.0
            return
        
        # Compare first half vs second half
        mid = len(self.recent_calls) // 2
        first_half = list(self.recent_calls)[:mid]
        second_half = list(self.recent_calls)[mid:]
        
        # Calculate success rates
        first_success = sum(1 for c in first_half if c['success']) / len(first_half)
        second_success = sum(1 for c in second_half if c['success']) / len(second_half)
        
        # Calculate average response times
        first_rt = sum(c['response_time'] for c in first_half) / len(first_half)
        second_rt = sum(c['response_time'] for c in second_half) / len(second_half)
        
        # Trend combines success rate improvement and speed improvement
        success_trend = second_success - first_success
        speed_trend = (first_rt - second_rt) / max(first_rt, 0.1)  # Positive = getting faster
        
        self.performance_trend = (success_trend * 0.6 + speed_trend * 0.4)
    
    def get_success_rate(self) -> float:
        """Get overall success rate."""
        if self.call_count == 0:
            return 0.0
        return self.success_count / self.call_count
    
    def get_recent_success_rate(self, lookback: int = 10) -> float:
        """Get recent success rate."""
        recent = list(self.recent_calls)[-lookback:]
        if not recent:
            return 0.0
        return sum(1 for c in recent if c['success']) / len(recent)
    
    def get_performance_score(self) -> float:
        """
        Calculate overall performance score (0-100).
        
        Combines:
        - Success rate (40%)
        - Speed (30%)
        - Quality (20%)
        - Trend (10%)
        """
        # Success rate component (0-40)
        success_rate = self.get_success_rate()
        success_component = success_rate * 40
        
        # Speed component (0-30)
        # Normalize response time (faster = higher score)
        # Assume 0-10s range, with 1s = excellent, 10s = poor
        if self.avg_response_time > 0:
            speed_score = max(0, 1 - (self.avg_response_time / 10.0))
        else:
            speed_score = 1.0
        speed_component = speed_score * 30
        
        # Quality component (0-20)
        quality_component = self.avg_quality * 20 if self.avg_quality > 0 else 15  # Default to 15 if no feedback
        
        # Trend component (-10 to +10)
        trend_component = self.performance_trend * 10
        
        total = success_component + speed_component + quality_component + trend_component
        
        # Penalty for consecutive failures
        if self.consecutive_failures > 3:
            total *= 0.5
        elif self.consecutive_failures > 1:
            total *= 0.8
        
        return max(0, min(100, total))
    
    def is_healthy(self) -> bool:
        """Check if tool is currently healthy."""
        return (
            self.consecutive_failures < 3 and
            self.get_recent_success_rate(5) > 0.6
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            'tool_name': self.tool_name,
            'call_count': self.call_count,
            'success_rate': f"{self.get_success_rate() * 100:.1f}%",
            'avg_response_time': f"{self.avg_response_time:.2f}s",
            'performance_score': f"{self.get_performance_score():.1f}/100",
            'trend': 'improving' if self.performance_trend > 0.1 else 'declining' if self.performance_trend < -0.1 else 'stable',
            'is_healthy': self.is_healthy(),
            'consecutive_failures': self.consecutive_failures,
            'avg_quality': f"{self.avg_quality:.2f}" if self.avg_quality > 0 else "N/A"
        }


# =============================================================================
# PERFORMANCE-BASED ROUTING
# =============================================================================

class PerformanceBasedRouter:
    """
    Route queries to tools based on performance metrics.
    
    Features:
    - Selects best-performing tool for query type
    - Falls back to alternatives if primary fails
    - Learns from routing decisions
    - Prevents overload on single tool
    """
    
    def __init__(self):
        """Initialize performance-based router."""
        # Tool performance trackers
        self.tool_trackers = {}  # tool_name -> ToolPerformanceTracker
        
        # Query type -> tool preferences
        self.query_type_preferences = defaultdict(lambda: defaultdict(float))
        
        # Routing history
        self.routing_history = deque(maxlen=100)
        
        # Load balancing
        self.tool_load = defaultdict(int)  # Current load per tool
        self.max_concurrent_load = 5
        
        print("🎯 Performance-Based Router initialized")
    
    def get_or_create_tracker(self, tool_name: str) -> ToolPerformanceTracker:
        """Get or create performance tracker for a tool."""
        if tool_name not in self.tool_trackers:
            self.tool_trackers[tool_name] = ToolPerformanceTracker(tool_name)
        return self.tool_trackers[tool_name]
    
    def select_tool(
        self,
        query: str,
        available_tools: List[str],
        query_type: Optional[str] = None,
        prefer_fastest: bool = False
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Select best tool based on performance.
        
        Args:
            query: The user query
            available_tools: List of available tool names
            query_type: Optional query type for better selection
            prefer_fastest: Prioritize speed over reliability
            
        Returns:
            (selected_tool, confidence, reasoning)
        """
        if not available_tools:
            return ("", 0.0, {"error": "No tools available"})
        
        # Filter out unhealthy tools
        healthy_tools = [
            tool for tool in available_tools
            if tool not in self.tool_trackers or self.tool_trackers[tool].is_healthy()
        ]
        
        # If no healthy tools, use all (with warning)
        if not healthy_tools:
            print("⚠️  No healthy tools, using all available")
            healthy_tools = available_tools
        
        # Score each tool
        tool_scores = {}
        reasoning = {}
        
        for tool in healthy_tools:
            score = self._score_tool(tool, query, query_type, prefer_fastest)
            tool_scores[tool] = score
            
            # Get tracker if exists
            if tool in self.tool_trackers:
                tracker = self.tool_trackers[tool]
                reasoning[tool] = {
                    'performance_score': tracker.get_performance_score(),
                    'success_rate': tracker.get_success_rate(),
                    'avg_response_time': tracker.avg_response_time,
                    'is_healthy': tracker.is_healthy(),
                    'load': self.tool_load.get(tool, 0)
                }
            else:
                reasoning[tool] = {'note': 'No historical data - default scoring'}
        
        # Select best tool
        best_tool = max(tool_scores, key=tool_scores.get)
        confidence = tool_scores[best_tool] / 100.0  # Normalize to 0-1
        
        # Record routing decision
        self.routing_history.append({
            'timestamp': datetime.now().isoformat(),
            'query': query[:100],
            'query_type': query_type,
            'selected_tool': best_tool,
            'confidence': confidence,
            'available_tools': available_tools,
            'scores': tool_scores
        })
        
        return best_tool, confidence, reasoning
    
    def _score_tool(
        self,
        tool: str,
        query: str,
        query_type: Optional[str],
        prefer_fastest: bool
    ) -> float:
        """
        Score a tool for the given query.
        
        Returns score 0-100.
        """
        # Base score from performance
        if tool in self.tool_trackers:
            tracker = self.tool_trackers[tool]
            base_score = tracker.get_performance_score()
            
            # Adjust for speed preference
            if prefer_fastest and tracker.avg_response_time > 0:
                speed_bonus = max(0, 20 - tracker.avg_response_time * 2)
                base_score += speed_bonus
        else:
            # New tool - give it a chance
            base_score = 60  # Neutral score
        
        # Boost based on query type preference
        if query_type and query_type in self.query_type_preferences:
            preference = self.query_type_preferences[query_type].get(tool, 0)
            base_score += preference * 10  # Max +10 boost
        
        # Penalize if tool is overloaded
        if tool in self.tool_load and self.tool_load[tool] >= self.max_concurrent_load:
            base_score *= 0.3  # Heavy penalty
        
        return max(0, min(100, base_score))
    
    def record_result(
        self,
        tool: str,
        query: str,
        success: bool,
        response_time: float,
        query_type: Optional[str] = None,
        quality_score: Optional[float] = None,
        error: Optional[str] = None
    ):
        """
        Record the result of a tool call.
        
        Args:
            tool: Tool that was used
            query: The query
            success: Whether it succeeded
            response_time: Response time in seconds
            query_type: Optional query type
            quality_score: Optional quality rating (0-1)
            error: Optional error message
        """
        # Update tool tracker
        tracker = self.get_or_create_tracker(tool)
        tracker.record_call(success, response_time, quality_score, error)
        
        # Update query type preferences
        if query_type:
            # Increase preference if successful, decrease if failed
            adjustment = 0.1 if success else -0.1
            current = self.query_type_preferences[query_type][tool]
            self.query_type_preferences[query_type][tool] = max(-1, min(1, current + adjustment))
        
        # Decrease load
        if tool in self.tool_load:
            self.tool_load[tool] = max(0, self.tool_load[tool] - 1)
        
        print(f"📊 Performance recorded: {tool} - {'✅' if success else '❌'} - {response_time:.2f}s")
    
    def get_fallback_chain(
        self,
        primary_tool: str,
        available_tools: List[str],
        max_fallbacks: int = 2
    ) -> List[str]:
        """
        Get ordered fallback chain if primary tool fails.
        
        Args:
            primary_tool: The primary tool
            available_tools: All available tools
            max_fallbacks: Maximum number of fallbacks
            
        Returns:
            Ordered list of fallback tools
        """
        # Remove primary from available
        fallback_options = [t for t in available_tools if t != primary_tool]
        
        if not fallback_options:
            return []
        
        # Score fallback options
        fallback_scores = {}
        for tool in fallback_options:
            if tool in self.tool_trackers:
                tracker = self.tool_trackers[tool]
                # For fallbacks, prioritize reliability over speed
                fallback_scores[tool] = (
                    tracker.get_success_rate() * 70 +
                    (1 if tracker.is_healthy() else 0) * 30
                )
            else:
                fallback_scores[tool] = 50  # Neutral
        
        # Sort by score and take top N
        sorted_fallbacks = sorted(fallback_scores, key=fallback_scores.get, reverse=True)
        return sorted_fallbacks[:max_fallbacks]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        # Collect tool statistics
        tool_stats = {}
        for tool_name, tracker in self.tool_trackers.items():
            tool_stats[tool_name] = tracker.get_stats()
        
        # Calculate overall metrics
        total_calls = sum(t.call_count for t in self.tool_trackers.values())
        total_successes = sum(t.success_count for t in self.tool_trackers.values())
        overall_success_rate = (total_successes / total_calls * 100) if total_calls > 0 else 0
        
        # Identify best and worst performers
        if self.tool_trackers:
            best_tool = max(
                self.tool_trackers.items(),
                key=lambda x: x[1].get_performance_score()
            )[0]
            
            worst_tool = min(
                self.tool_trackers.items(),
                key=lambda x: x[1].get_performance_score()
            )[0]
        else:
            best_tool = "N/A"
            worst_tool = "N/A"
        
        # Recent routing decisions
        recent_routing = list(self.routing_history)[-10:]
        
        return {
            'overall_metrics': {
                'total_calls': total_calls,
                'overall_success_rate': f"{overall_success_rate:.1f}%",
                'tools_tracked': len(self.tool_trackers),
                'routing_decisions': len(self.routing_history)
            },
            'tool_performance': tool_stats,
            'best_performer': best_tool,
            'worst_performer': worst_tool,
            'recent_routing': recent_routing,
            'query_type_preferences': dict(self.query_type_preferences)
        }
    
    def save_to_file(self, filepath: str):
        """Save router state to file."""
        data = {
            'tool_trackers': {
                name: {
                    'call_count': t.call_count,
                    'success_count': t.success_count,
                    'total_response_time': t.total_response_time,
                    'avg_response_time': t.avg_response_time,
                    'recent_calls': list(t.recent_calls),
                    'quality_scores': t.quality_scores,
                    'avg_quality': t.avg_quality,
                    'performance_trend': t.performance_trend,
                    'consecutive_failures': t.consecutive_failures,
                    'max_consecutive_failures': t.max_consecutive_failures
                }
                for name, t in self.tool_trackers.items()
            },
            'query_type_preferences': {
                qt: dict(prefs) for qt, prefs in self.query_type_preferences.items()
            },
            'routing_history': list(self.routing_history),
            'saved_at': datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Performance router saved: {filepath}")
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'PerformanceBasedRouter':
        """Load router state from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        router = cls()
        
        # Restore tool trackers
        for tool_name, tracker_data in data.get('tool_trackers', {}).items():
            tracker = ToolPerformanceTracker(tool_name)
            tracker.call_count = tracker_data['call_count']
            tracker.success_count = tracker_data['success_count']
            tracker.total_response_time = tracker_data['total_response_time']
            tracker.avg_response_time = tracker_data['avg_response_time']
            tracker.recent_calls = deque(tracker_data['recent_calls'], maxlen=20)
            tracker.quality_scores = tracker_data['quality_scores']
            tracker.avg_quality = tracker_data['avg_quality']
            tracker.performance_trend = tracker_data['performance_trend']
            tracker.consecutive_failures = tracker_data['consecutive_failures']
            tracker.max_consecutive_failures = tracker_data['max_consecutive_failures']
            
            router.tool_trackers[tool_name] = tracker
        
        # Restore query type preferences
        for qt, prefs in data.get('query_type_preferences', {}).items():
            router.query_type_preferences[qt] = defaultdict(float, prefs)
        
        # Restore routing history
        router.routing_history = deque(data.get('routing_history', []), maxlen=100)
        
        print(f"📂 Performance router loaded: {filepath}")
        return router


# =============================================================================
# GLOBAL INSTANCES & CONVENIENCE FUNCTIONS
# =============================================================================

# Global monitor instance
_global_monitor = PerformanceMonitor()

# Global router instance
_performance_router = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _global_monitor


def log_request(*args, **kwargs):
    """Convenience function to log a request."""
    _global_monitor.log_request(*args, **kwargs)


def print_performance_report():
    """Convenience function to print performance report."""
    _global_monitor.print_report()


def get_performance_stats() -> Dict[str, Any]:
    """Convenience function to get performance stats."""
    return _global_monitor.get_stats()


def get_performance_router() -> PerformanceBasedRouter:
    """Get or create global performance router."""
    global _performance_router
    if _performance_router is None:
        # Try to load from file
        filepath = ".performance_router/router_state.json"
        if os.path.exists(filepath):
            try:
                _performance_router = PerformanceBasedRouter.load_from_file(filepath)
            except Exception as e:
                print(f"⚠️  Could not load router state: {e}")
                _performance_router = PerformanceBasedRouter()
        else:
            _performance_router = PerformanceBasedRouter()
    return _performance_router


def save_performance_router():
    """Save global performance router to file."""
    global _performance_router
    if _performance_router is not None:
        filepath = ".performance_router/router_state.json"
        _performance_router.save_to_file(filepath)
