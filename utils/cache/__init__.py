"""Cache utilities and strategies."""

try:
    from utils.core.advanced_cache import (
        MultiTierCache,
        get_cache,
        async_cached
    )
    ADVANCED_CACHE_AVAILABLE = True
except ImportError:
    ADVANCED_CACHE_AVAILABLE = False

try:
    from .cache_strategies import (
        CacheWarmer,
        CacheInvalidator,
        SmartPrefetcher,
        CacheOptimizer,
        get_cache_optimizer,
    )
    CACHE_STRATEGIES_AVAILABLE = True
except ImportError:
    CACHE_STRATEGIES_AVAILABLE = False

# Import basic cache that should always be available
from utils.core.cache import ResultCache

# Import redis client for token storage
try:
    from .redis_client import token_store
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    token_store = None

__all__ = [
    "ResultCache",
    "token_store",
    "ADVANCED_CACHE_AVAILABLE",
    "CACHE_STRATEGIES_AVAILABLE",
    "REDIS_AVAILABLE",
]

# Add advanced cache exports if available
if ADVANCED_CACHE_AVAILABLE:
    __all__.extend([
        "MultiTierCache",
        "get_cache",
        "async_cached",
    ])

# Add cache strategies exports if available
if CACHE_STRATEGIES_AVAILABLE:
    __all__.extend([
        "CacheWarmer",
        "CacheInvalidator",
        "SmartPrefetcher",
        "CacheOptimizer",
        "get_cache_optimizer",
    ])


