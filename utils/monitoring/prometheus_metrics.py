"""
Prometheus metrics integration.

Tracks application performance metrics for monitoring and alerting.
"""

from typing import Dict, Any, Optional
import time
from functools import wraps

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    REGISTRY,
)

from config import settings

# Request metrics
request_count = Counter(
    'app_requests_total',
    'Total request count',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'app_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

request_in_progress = Gauge(
    'app_requests_in_progress',
    'Requests currently being processed',
    ['endpoint']
)

# Agent metrics
agent_execution_count = Counter(
    'agent_executions_total',
    'Total agent execution count',
    ['agent_type', 'status']
)

agent_execution_duration = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution duration in seconds',
    ['agent_type'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
)

# LLM metrics
llm_requests = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status']
)

llm_tokens = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model', 'type']  # type: prompt or completion
)

llm_latency = Histogram(
    'llm_request_latency_seconds',
    'LLM request latency',
    ['provider', 'model'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# Cache metrics
cache_operations = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # operation: get/set/delete, result: hit/miss/success/error
)

cache_size = Gauge(
    'cache_size_bytes',
    'Current cache size in bytes',
    ['tier']
)

cache_hit_ratio = Gauge(
    'cache_hit_ratio',
    'Cache hit ratio (0-1)',
    ['tier']
)

# Database metrics
db_queries = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table', 'status']
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
)

db_pool_connections = Gauge(
    'db_pool_connections',
    'Database pool connections',
    ['state']  # state: in_use, available, total
)

# Error metrics
error_count = Counter(
    'errors_total',
    'Total error count',
    ['error_type', 'component']
)

# System metrics
system_info = Info(
    'app_system',
    'Application system information'
)

active_sessions = Gauge(
    'active_sessions_total',
    'Number of active user sessions'
)


class PrometheusMetrics:
    """Centralized Prometheus metrics manager."""
    
    def __init__(self):
        self.enabled = settings.enable_metrics
        
        if self.enabled:
            # Set system info
            system_info.info({
                'version': '1.0.0',
                'environment': 'production' if not settings.is_development else 'development',
            })
    
    def track_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ):
        """Track HTTP request metrics."""
        if not self.enabled:
            return
        
        request_count.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def track_agent_execution(
        self,
        agent_type: str,
        duration: float,
        status: str = "success"
    ):
        """Track agent execution metrics."""
        if not self.enabled:
            return
        
        agent_execution_count.labels(
            agent_type=agent_type,
            status=status
        ).inc()
        
        agent_execution_duration.labels(
            agent_type=agent_type
        ).observe(duration)
    
    def track_llm_request(
        self,
        provider: str,
        model: str,
        latency: float,
        prompt_tokens: int,
        completion_tokens: int,
        status: str = "success"
    ):
        """Track LLM request metrics."""
        if not self.enabled:
            return
        
        llm_requests.labels(
            provider=provider,
            model=model,
            status=status
        ).inc()
        
        llm_tokens.labels(
            provider=provider,
            model=model,
            type="prompt"
        ).inc(prompt_tokens)
        
        llm_tokens.labels(
            provider=provider,
            model=model,
            type="completion"
        ).inc(completion_tokens)
        
        llm_latency.labels(
            provider=provider,
            model=model
        ).observe(latency)
    
    def track_cache_operation(
        self,
        operation: str,
        result: str
    ):
        """Track cache operation metrics."""
        if not self.enabled:
            return
        
        cache_operations.labels(
            operation=operation,
            result=result
        ).inc()
    
    def update_cache_metrics(
        self,
        tier: str,
        size_bytes: int,
        hit_ratio: float
    ):
        """Update cache metrics."""
        if not self.enabled:
            return
        
        cache_size.labels(tier=tier).set(size_bytes)
        cache_hit_ratio.labels(tier=tier).set(hit_ratio)
    
    def track_db_query(
        self,
        operation: str,
        table: str,
        duration: float,
        status: str = "success"
    ):
        """Track database query metrics."""
        if not self.enabled:
            return
        
        db_queries.labels(
            operation=operation,
            table=table,
            status=status
        ).inc()
        
        db_query_duration.labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def update_db_pool_metrics(
        self,
        in_use: int,
        available: int,
        total: int
    ):
        """Update database pool metrics."""
        if not self.enabled:
            return
        
        db_pool_connections.labels(state="in_use").set(in_use)
        db_pool_connections.labels(state="available").set(available)
        db_pool_connections.labels(state="total").set(total)
    
    def track_error(
        self,
        error_type: str,
        component: str
    ):
        """Track error occurrence."""
        if not self.enabled:
            return
        
        error_count.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    def update_active_sessions(self, count: int):
        """Update active sessions count."""
        if not self.enabled:
            return
        
        active_sessions.set(count)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest(REGISTRY)


# Global metrics instance
_metrics: Optional[PrometheusMetrics] = None


def get_metrics() -> PrometheusMetrics:
    """Get or create global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = PrometheusMetrics()
    return _metrics


# Decorators
def track_time(metric_name: str = None, labels: Dict[str, str] = None):
    """
    Decorator to track execution time.
    
    Usage:
        @track_time("my_function", {"component": "api"})
        async def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track custom metric or use agent execution
                metrics = get_metrics()
                if metric_name:
                    # Custom tracking logic here
                    pass
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                return result
            except Exception as e:
                duration = time.time() - start_time
                raise
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

