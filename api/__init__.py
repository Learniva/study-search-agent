"""
API package for the Study and Search Agent.

Modular, scalable FastAPI application with:
- Separate routers for different features
- Proper dependency injection
- Rate limiting and monitoring
- Production-ready error handling
"""

from .app import app

__all__ = ["app"]
