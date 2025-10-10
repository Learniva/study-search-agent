"""
Distributed tracing support with OpenTelemetry.

Provides request tracing across services for debugging and performance analysis.
"""

from typing import Optional, Dict, Any, Callable
from functools import wraps
import time

from config import settings
from .logging import get_correlation_id, set_correlation_id

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode
    
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = None


class DistributedTracer:
    """
    Distributed tracing manager.
    
    Features:
    - Request tracing across services
    - Span creation and management
    - Trace context propagation
    - Integration with correlation IDs
    """
    
    def __init__(self):
        self.enabled = settings.enable_tracing if hasattr(settings, 'enable_tracing') else False
        self.tracer = None
        
        if self.enabled and TRACING_AVAILABLE:
            self._init_tracer()
    
    def _init_tracer(self):
        """Initialize OpenTelemetry tracer."""
        try:
            # Create resource with service info
            resource = Resource.create({
                "service.name": "study-search-agent",
                "service.version": "1.0.0",
                "deployment.environment": "production" if not settings.is_development else "development",
            })
            
            # Create tracer provider
            provider = TracerProvider(resource=resource)
            
            # Add Jaeger exporter (can be replaced with other exporters)
            if hasattr(settings, 'jaeger_endpoint'):
                jaeger_exporter = JaegerExporter(
                    agent_host_name="localhost",
                    agent_port=6831,
                )
                provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            
            # Set global tracer provider
            trace.set_tracer_provider(provider)
            
            # Get tracer
            self.tracer = trace.get_tracer(__name__)
            
            print("✅ Distributed tracing initialized")
        except Exception as e:
            print(f"⚠️  Failed to initialize tracing: {e}")
            self.enabled = False
    
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Start a new span.
        
        Args:
            name: Span name
            attributes: Span attributes
            
        Returns:
            Span context manager
        """
        if not self.enabled or not self.tracer:
            # Return no-op context manager
            from contextlib import nullcontext
            return nullcontext()
        
        # Add correlation ID to attributes
        attrs = attributes or {}
        attrs["correlation_id"] = get_correlation_id()
        
        return self.tracer.start_as_current_span(
            name,
            attributes=attrs
        )
    
    def set_span_attribute(self, key: str, value: Any):
        """Set attribute on current span."""
        if not self.enabled or not self.tracer:
            return
        
        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute(key, value)
    
    def set_span_status(self, status: str, description: Optional[str] = None):
        """Set status on current span."""
        if not self.enabled or not self.tracer:
            return
        
        current_span = trace.get_current_span()
        if current_span:
            if status == "ok":
                current_span.set_status(Status(StatusCode.OK, description))
            elif status == "error":
                current_span.set_status(Status(StatusCode.ERROR, description))
    
    def record_exception(self, exception: Exception):
        """Record exception in current span."""
        if not self.enabled or not self.tracer:
            return
        
        current_span = trace.get_current_span()
        if current_span:
            current_span.record_exception(exception)
            current_span.set_status(Status(StatusCode.ERROR, str(exception)))
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to current span."""
        if not self.enabled or not self.tracer:
            return
        
        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(name, attributes=attributes)


# Global tracer instance
_tracer: Optional[DistributedTracer] = None


def get_tracer() -> DistributedTracer:
    """Get or create global tracer."""
    global _tracer
    if _tracer is None:
        _tracer = DistributedTracer()
    return _tracer


# Decorators
def trace_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Decorator to trace function execution.
    
    Usage:
        @trace_function("my_function", {"component": "api"})
        async def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            attrs = attributes or {}
            attrs["function"] = func.__name__
            
            with tracer.start_span(span_name, attrs):
                try:
                    result = await func(*args, **kwargs)
                    tracer.set_span_status("ok")
                    return result
                except Exception as e:
                    tracer.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            attrs = attributes or {}
            attrs["function"] = func.__name__
            
            with tracer.start_span(span_name, attrs):
                try:
                    result = func(*args, **kwargs)
                    tracer.set_span_status("ok")
                    return result
                except Exception as e:
                    tracer.record_exception(e)
                    raise
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def trace_agent_execution(agent_type: str):
    """
    Decorator to trace agent execution.
    
    Usage:
        @trace_agent_execution("study")
        async def execute_study_agent():
            pass
    """
    return trace_function(
        f"agent.{agent_type}.execute",
        {"agent_type": agent_type}
    )


def trace_llm_call(provider: str, model: str):
    """
    Decorator to trace LLM calls.
    
    Usage:
        @trace_llm_call("gemini", "gemini-pro")
        async def call_llm():
            pass
    """
    return trace_function(
        f"llm.{provider}.call",
        {"provider": provider, "model": model}
    )


def trace_db_query(operation: str, table: str):
    """
    Decorator to trace database queries.
    
    Usage:
        @trace_db_query("select", "users")
        async def get_user():
            pass
    """
    return trace_function(
        f"db.{operation}",
        {"operation": operation, "table": table}
    )


# FastAPI middleware for tracing
class TracingMiddleware:
    """Middleware to add tracing to FastAPI requests."""
    
    def __init__(self, app):
        self.app = app
        self.tracer = get_tracer()
    
    async def __call__(self, scope, receive, send):
        """Process request with tracing."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode()
        
        if not correlation_id:
            from .logging import get_correlation_id
            correlation_id = get_correlation_id()
        else:
            set_correlation_id(correlation_id)
        
        # Start span for request
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        with self.tracer.start_span(
            f"{method} {path}",
            attributes={
                "http.method": method,
                "http.path": path,
                "http.scheme": scope.get("scheme", ""),
            }
        ):
            # Add correlation ID to response headers
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = message.get("headers", [])
                    headers.append((b"x-correlation-id", correlation_id.encode()))
                    message["headers"] = headers
                await send(message)
            
            await self.app(scope, receive, send_wrapper)

