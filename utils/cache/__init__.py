"""Cache utilities and strategies."""

from utils.core.advanced_cache import (
    MultiTierCache,
    get_cache,
    async_cached,
    ResultCache,
)
from .cache_strategies import (
    CacheWarmer,
    CacheInvalidator,
    SmartPrefetcher,
    CacheOptimizer,
    get_cache_optimizer,
)

__all__ = [
    "MultiTierCache",
    "get_cache",
    "async_cached",
    "ResultCache",
    "CacheWarmer",
    "CacheInvalidator",
    "SmartPrefetcher",
    "CacheOptimizer",
    "get_cache_optimizer",
]


