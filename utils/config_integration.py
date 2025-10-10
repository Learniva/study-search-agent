"""Configuration integration utilities."""

from typing import Any, Dict, Optional
from functools import lru_cache

from config import settings


class ConfigManager:
    """Centralized configuration manager for agents and utilities."""
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_llm_config(use_case: str = "study") -> Dict[str, Any]:
        """
        Get LLM configuration for specific use case.
        
        Args:
            use_case: study, grading, routing, creative, or precise
            
        Returns:
            LLM configuration dictionary
        """
        return {
            "provider": settings.llm_provider,
            "model": settings.default_model,
            "temperature": settings.temperature_settings.get(use_case, 0.7),
            "api_key": settings.google_api_key,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_cache_config() -> Dict[str, Any]:
        """Get cache configuration."""
        return {
            "enabled": settings.cache_enabled,
            "ttl": settings.cache_ttl,
            "max_size": settings.cache_max_size,
            "redis_url": settings.redis_url,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_database_config() -> Dict[str, Any]:
        """Get database configuration."""
        return {
            "url": settings.database_url,
            "async_url": settings.async_database_url,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_recycle": settings.db_pool_recycle,
            "pool_pre_ping": settings.db_pool_pre_ping,
            "echo": settings.db_echo,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_performance_config() -> Dict[str, Any]:
        """Get performance configuration."""
        return {
            "max_concurrent_requests": settings.max_concurrent_requests,
            "request_timeout": settings.request_timeout,
            "max_context_tokens": settings.max_context_tokens,
            "max_agent_iterations": settings.max_agent_iterations,
            "max_grading_iterations": settings.max_grading_iterations,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_api_config() -> Dict[str, Any]:
        """Get API configuration."""
        return {
            "host": settings.api_host,
            "port": settings.api_port,
            "workers": settings.api_workers,
            "reload": settings.api_reload,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "rate_limit_per_hour": settings.rate_limit_per_hour,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_feature_flags() -> Dict[str, bool]:
        """Get feature flags."""
        return {
            "ml_features": settings.enable_ml_features,
            "performance_routing": settings.enable_performance_routing,
            "streaming": settings.enable_streaming,
            "manim": settings.enable_manim,
            "metrics": settings.enable_metrics,
            "tracing": settings.enable_tracing,
        }
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_documents_config() -> Dict[str, Any]:
        """Get document processing configuration."""
        return {
            "dir": settings.documents_dir,
            "max_size_mb": settings.max_document_size_mb,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        }
    
    @staticmethod
    def is_feature_enabled(feature: str) -> bool:
        """Check if a feature is enabled."""
        flags = ConfigManager.get_feature_flags()
        return flags.get(feature, False)
    
    @staticmethod
    def get_timeout(operation: str = "default") -> int:
        """Get timeout for specific operation."""
        timeouts = {
            "default": settings.request_timeout,
            "llm": settings.request_timeout,
            "database": 30,
            "cache": 5,
            "tool": settings.request_timeout,
        }
        return timeouts.get(operation, settings.request_timeout)
    
    @staticmethod
    def get_max_iterations(agent_type: str = "study") -> int:
        """Get max iterations for agent type."""
        iterations = {
            "study": settings.max_agent_iterations,
            "grading": settings.max_grading_iterations,
            "supervisor": 3,
        }
        return iterations.get(agent_type, settings.max_agent_iterations)


# Convenience functions
def get_config(category: str) -> Dict[str, Any]:
    """
    Get configuration for a category.
    
    Args:
        category: llm, cache, database, performance, api, features, documents
        
    Returns:
        Configuration dictionary
    """
    config_getters = {
        "llm": ConfigManager.get_llm_config,
        "cache": ConfigManager.get_cache_config,
        "database": ConfigManager.get_database_config,
        "performance": ConfigManager.get_performance_config,
        "api": ConfigManager.get_api_config,
        "features": ConfigManager.get_feature_flags,
        "documents": ConfigManager.get_documents_config,
    }
    
    getter = config_getters.get(category)
    if not getter:
        raise ValueError(f"Unknown config category: {category}")
    
    return getter()


def is_development() -> bool:
    """Check if running in development mode."""
    return settings.is_development


def is_production() -> bool:
    """Check if running in production mode."""
    return not settings.is_development

