"""
Utilities Package

Organized by purpose for better maintainability:
- core: Essential system utilities (LLM, cache, constants)
- patterns: Shared agent patterns (base agent, graph builder, state manager)
- api: REST API utilities (auth, streaming)
- rag: RAG-specific utilities (context, query enrichment)
- routing: Tool/agent routing (pattern-based, performance-based)
- prompts: Centralized prompt templates
- ml: Machine learning & adaptive features
- monitoring: Logging, metrics, error handling

All modules provide graceful degradation for optional dependencies.
"""

# =============================================================================
# CORE UTILITIES
# =============================================================================

# LLM imports are commented out to avoid langchain dependencies for auth-only operations
# These can be imported directly from utils.core.llm when needed
from .core import (
    ResultCache,
    DEFAULT_CACHE_TTL,
    MAX_CONTEXT_TOKENS,
    MAX_AGENT_ITERATIONS,
    MAX_GRADING_ITERATIONS,
    VAGUE_QUESTION_PATTERNS,
    FOLLOW_UP_PRONOUNS,
    GENERIC_SUBJECTS,
    REALTIME_QUERY_PATTERNS,
    GRADING_ERROR_INDICATORS,
    GRADING_UNCERTAINTY_INDICATORS,
)
# from .core.advanced_cache import MultiTierCache, get_cache, async_cached

# =============================================================================
# SHARED PATTERNS
# =============================================================================

# from .patterns import BaseAgent, GraphBuilder, StateManager

# =============================================================================
# RAG UTILITIES
# =============================================================================

# from .rag import (
#     get_smart_context,
#     estimate_tokens,
#     truncate_to_tokens,
#     detect_realtime_query,
#     needs_query_enrichment,
#     enrich_query_with_context,
#     format_realtime_warning
# )

# =============================================================================
# ROUTING UTILITIES
# =============================================================================

# from .routing import (
#     fast_study_route,
#     fast_grading_route,
#     fast_intent_classification,
#     calculate_text_similarity,
#     PerformanceMonitor,
#     RequestMetrics,
#     get_performance_monitor,
#     log_request,
#     print_performance_report,
#     get_performance_stats,
#     PerformanceBasedRouter,
#     ToolPerformanceTracker,
#     get_performance_router,
#     save_performance_router
# )

# =============================================================================
# PROMPTS
# =============================================================================

# from .prompts import (
#     get_agent_prompt,
#     get_grading_prompt,
#     get_grading_prompt_for_rubric,
#     get_essay_grading_prompt,
#     get_code_review_prompt,
#     get_rubric_evaluation_prompt,
#     get_feedback_prompt,
#     get_feedback_generation_prompt,
#     get_citation_check_prompt,
#     format_rubric_for_prompt,
#     get_mcq_grading_prompt,
#     get_supervisor_prompt,
#     get_intent_classification_prompt,
#     GRADING_AGENT_SYSTEM_PROMPT,
#     SUPERVISOR_INTENT_CLASSIFICATION_PROMPT,
#     SUPERVISOR_ACCESS_CONTROL_EXPLANATION,
#     MANIM_ANIMATION_SYSTEM_PROMPT,
# )

# =============================================================================
# MONITORING
# =============================================================================

from .monitoring import (
    get_correlation_id,
    set_correlation_id,
    get_logger,
    setup_logging,
    track_query,
    track_error,
    get_metrics_summary,
    handle_error,
    AgentError,
    DatabaseError,
    LLMError,
)

# =============================================================================
# ML & ADAPTIVE FEATURES (Optional)
# =============================================================================

try:
    from .ml import (
        QueryLearner,
        QueryRecord,
        get_query_learner,
        save_query_learner,
        AdaptiveRubric,
        AdaptiveRubricManager,
        get_adaptive_rubric_manager,
        UserProfile,
        UserProfileManager,
        get_user_profile_manager,
        get_user_preferences,
        update_user_profile,
        check_past_overrides,
        get_student_profile,
        get_professor_grading_style,
    )
    ML_FEATURES_AVAILABLE = True
except ImportError as e:
    ML_FEATURES_AVAILABLE = False
    print(f"⚠️  ML features not available: {e}")

# =============================================================================
# API SUPPORT (Optional)
# =============================================================================

try:
    from .api import (
        create_access_token,
        decode_access_token,
        get_current_user,
        get_current_teacher,
        require_role,
        TokenData,
        User,
        StreamingResponse,
        stream_llm_response,
        format_sse_message,
        is_streaming_supported,
    )
    API_FEATURES_AVAILABLE = True
except ImportError as e:
    API_FEATURES_AVAILABLE = False
    print(f"⚠️  API features not available: {e}")

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core
    'ResultCache',
    'DEFAULT_CACHE_TTL',
    'MAX_CONTEXT_TOKENS',
    'MAX_AGENT_ITERATIONS',
    'MAX_GRADING_ITERATIONS',
    'VAGUE_QUESTION_PATTERNS',
    'FOLLOW_UP_PRONOUNS',
    'GENERIC_SUBJECTS',
    'REALTIME_QUERY_PATTERNS',
    'GRADING_ERROR_INDICATORS',
    'GRADING_UNCERTAINTY_INDICATORS',
    'fast_intent_classification',
    'calculate_text_similarity',
    'PerformanceMonitor',
    'RequestMetrics',
    'get_performance_monitor',
    'log_request',
    'print_performance_report',
    'get_performance_stats',
    'PerformanceBasedRouter',
    'ToolPerformanceTracker',
    'get_performance_router',
    'save_performance_router',
    
    # Prompts
    # Monitoring
    'get_correlation_id',
    'set_correlation_id',
    'get_logger',
    'setup_logging',
    'track_query',
    'track_error',
    'get_metrics_summary',
    'handle_error',
    'AgentError',
    'DatabaseError',
    'LLMError',
    
    # Feature flags
    'ML_FEATURES_AVAILABLE',
    'API_FEATURES_AVAILABLE',
]

# Add ML exports if available
if ML_FEATURES_AVAILABLE:
    __all__.extend([
        'QueryLearner',
        'QueryRecord',
        'get_query_learner',
        'save_query_learner',
        'AdaptiveRubric',
        'AdaptiveRubricManager',
        'get_adaptive_rubric_manager',
        'UserProfile',
        'UserProfileManager',
        'get_user_profile_manager',
        'get_user_preferences',
        'update_user_profile',
        'check_past_overrides',
        'get_student_profile',
        'get_professor_grading_style',
    ])

# Add API exports if available
if API_FEATURES_AVAILABLE:
    __all__.extend([
        'create_access_token',
        'decode_access_token',
        'get_current_user',
        'get_current_teacher',
        'require_role',
        'TokenData',
        'User',
        'StreamingResponse',
        'stream_llm_response',
        'format_sse_message',
        'is_streaming_supported',
    ])
