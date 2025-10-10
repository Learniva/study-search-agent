"""Structured logging system with performance tracking and correlation IDs."""

import logging
import sys
import uuid
from typing import Any, Optional
from datetime import datetime
from pathlib import Path
from contextvars import ContextVar

from config import settings

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> str:
    """Get or generate correlation ID for request tracking."""
    correlation_id = correlation_id_var.get()
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
    return correlation_id


def set_correlation_id(correlation_id: str):
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def clear_correlation_id():
    """Clear correlation ID from context."""
    correlation_id_var.set(None)


class StructuredFormatter(logging.Formatter):
    """Custom formatter with structured output and correlation IDs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured data."""
        timestamp = datetime.utcnow().isoformat()
        
        # Base log structure
        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),  # Add correlation ID
        }
        
        # Add context data if available
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        # Add error details if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Format as JSON if in production, pretty print in dev
        if settings.is_development:
            parts = [f"{timestamp} [{record.levelname}] {record.name} [{get_correlation_id()[:8]}]"]
            parts.append(f"  Message: {record.getMessage()}")
            if hasattr(record, "context"):
                parts.append(f"  Context: {record.context}")
            if record.exc_info:
                parts.append(f"  Error: {self.formatException(record.exc_info)}")
            return "\n".join(parts)
        else:
            import json
            return json.dumps(log_data)


def setup_logging():
    """Setup logging configuration."""
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    
    # Create file handler if not in testing mode
    if not settings.testing:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log")
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class AgentLogger:
    """Logger wrapper with structured logging support."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, **context):
        """Log info message with context."""
        extra = {"context": context} if context else {}
        self.logger.info(message, extra=extra)
    
    def error(self, message: str, error: Optional[Exception] = None, **context):
        """Log error with context and exception."""
        extra = {"context": context} if context else {}
        self.logger.error(message, exc_info=error, extra=extra)
    
    def warning(self, message: str, **context):
        """Log warning with context."""
        extra = {"context": context} if context else {}
        self.logger.warning(message, extra=extra)
    
    def debug(self, message: str, **context):
        """Log debug message with context."""
        if settings.debug:
            extra = {"context": context} if context else {}
            self.logger.debug(message, extra=extra)
    
    def query_start(
        self,
        query_id: str,
        agent: str,
        user_id: Optional[str] = None,
        **context
    ):
        """Log query start."""
        self.info(
            f"Query started: {query_id}",
            query_id=query_id,
            agent=agent,
            user_id=user_id,
            **context
        )
    
    def query_end(
        self,
        query_id: str,
        success: bool,
        latency_ms: int,
        **context
    ):
        """Log query completion."""
        level = "info" if success else "error"
        getattr(self, level)(
            f"Query {'completed' if success else 'failed'}: {query_id}",
            query_id=query_id,
            success=success,
            latency_ms=latency_ms,
            **context
        )
    
    def tool_execution(
        self,
        tool: str,
        success: bool,
        latency_ms: int,
        **context
    ):
        """Log tool execution."""
        self.info(
            f"Tool {tool} {'succeeded' if success else 'failed'}",
            tool=tool,
            success=success,
            latency_ms=latency_ms,
            **context
        )


def get_logger(name: str) -> AgentLogger:
    """Get logger instance for a module."""
    if not logging.getLogger().handlers:
        setup_logging()
    return AgentLogger(name)

