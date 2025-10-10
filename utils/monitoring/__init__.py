"""Enhanced monitoring and observability package."""

from .logging import (
    get_logger,
    setup_logging,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
)
from .metrics import (
    track_query,
    track_error,
    get_metrics_summary,
)
from .errors import (
    handle_error,
    AgentError,
    DatabaseError,
    LLMError,
)

# Optional: Prometheus metrics (requires prometheus-client)
try:
    from .prometheus_metrics import (
        get_metrics,
        track_time,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False
    get_metrics = None
    track_time = None

# Optional: Distributed tracing (requires opentelemetry)
try:
    from .tracing import (
        get_tracer,
        trace_function,
        trace_agent_execution,
        trace_llm_call,
        trace_db_query,
        TracingMiddleware,
    )
    _HAS_TRACING = True
except ImportError:
    _HAS_TRACING = False
    get_tracer = None
    trace_function = None
    trace_agent_execution = None
    trace_llm_call = None
    trace_db_query = None
    TracingMiddleware = None

__all__ = [
    # Logging
    "get_logger",
    "setup_logging",
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    # Metrics
    "track_query",
    "track_error",
    "get_metrics_summary",
    # Errors
    "handle_error",
    "AgentError",
    "DatabaseError",
    "LLMError",
    # Prometheus (optional)
    "get_metrics",
    "track_time",
    # Tracing (optional)
    "get_tracer",
    "trace_function",
    "trace_agent_execution",
    "trace_llm_call",
    "trace_db_query",
    "TracingMiddleware",
]
