"""Metrics collection and tracking."""

from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import time

from config import settings


class MetricsCollector:
    """Lightweight metrics collector."""
    
    def __init__(self):
        self.query_count = 0
        self.error_count = 0
        self.total_latency_ms = 0
        self.tool_usage = defaultdict(int)
        self.agent_usage = defaultdict(int)
        self.error_types = defaultdict(int)
        self.cache_hits = 0
        self.cache_misses = 0
    
    def track_query(
        self,
        agent: str,
        tool: Optional[str],
        latency_ms: int,
        success: bool,
        cache_hit: bool = False
    ):
        """Track query metrics."""
        self.query_count += 1
        self.total_latency_ms += latency_ms
        
        if not success:
            self.error_count += 1
        
        self.agent_usage[agent] += 1
        
        if tool:
            self.tool_usage[tool] += 1
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def track_error(self, error_type: str):
        """Track error occurrence."""
        self.error_types[error_type] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        avg_latency = (
            self.total_latency_ms / self.query_count
            if self.query_count > 0 else 0
        )
        
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            (self.cache_hits / cache_total * 100)
            if cache_total > 0 else 0
        )
        
        return {
            "total_queries": self.query_count,
            "total_errors": self.error_count,
            "error_rate_percent": round(
                (self.error_count / self.query_count * 100)
                if self.query_count > 0 else 0,
                2
            ),
            "avg_latency_ms": round(avg_latency, 2),
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "agent_usage": dict(self.agent_usage),
            "tool_usage": dict(self.tool_usage),
            "error_types": dict(self.error_types),
        }
    
    def reset(self):
        """Reset all metrics."""
        self.query_count = 0
        self.error_count = 0
        self.total_latency_ms = 0
        self.tool_usage.clear()
        self.agent_usage.clear()
        self.error_types.clear()
        self.cache_hits = 0
        self.cache_misses = 0


# Global metrics collector
_metrics = MetricsCollector()


def track_query(
    agent: str,
    tool: Optional[str],
    latency_ms: int,
    success: bool,
    cache_hit: bool = False
):
    """Track query metrics."""
    if settings.enable_metrics:
        _metrics.track_query(agent, tool, latency_ms, success, cache_hit)


def track_error(error_type: str):
    """Track error occurrence."""
    if settings.enable_metrics:
        _metrics.track_error(error_type)


def get_metrics_summary() -> Dict[str, Any]:
    """Get current metrics summary."""
    return _metrics.get_summary()


def reset_metrics():
    """Reset all metrics."""
    _metrics.reset()


class QueryTimer:
    """Context manager for timing queries."""
    
    def __init__(self, agent: str, tool: Optional[str] = None):
        self.agent = agent
        self.tool = tool
        self.start_time = None
        self.latency_ms = 0
        self.success = True
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.latency_ms = int((time.time() - self.start_time) * 1000)
        self.success = exc_type is None
        
        track_query(
            agent=self.agent,
            tool=self.tool,
            latency_ms=self.latency_ms,
            success=self.success
        )

