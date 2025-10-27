"""API Routers."""

# from .query import router as query_router  # Requires supervisor agent
# from .documents import router as documents_router  # Requires langchain
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
from .auth import router as auth_router, legacy_router as legacy_auth_router
# from .concurrent_query import router as concurrent_query_router  # Requires supervisor agent

__all__ = [
    # "query_router",  # Requires supervisor agent
    # "documents_router",  # Requires langchain
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
    "legacy_auth_router",
    # "concurrent_query_router",  # Requires supervisor agent
]




