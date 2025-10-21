"""API Routers."""

from .query import router as query_router
from .documents import router as documents_router
from .grading import router as grading_router
from .ml_features import router as ml_router
from .health import router as health_router
from .videos import router as videos_router
from .profile import router as profile_router
from .settings import router as settings_router
from .help import router as help_router
from .integrations import router as integrations_router
from .billing import router as billing_router
from .payments import router as payments_router
from .auth import router as auth_router

__all__ = [
    "query_router",
    "documents_router",
    "grading_router",
    "ml_router",
    "health_router",
    "videos_router",
    "profile_router",
    "settings_router",
    "help_router",
    "integrations_router",
    "billing_router",
    "payments_router",
    "auth_router",
]




