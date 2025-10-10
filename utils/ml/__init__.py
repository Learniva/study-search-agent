"""
Machine Learning & Adaptive Features Package

Provides intelligent learning and adaptation capabilities:
- Query pattern learning and prediction
- Adaptive rubrics that learn from feedback (numerical & LLM-based)
- User profiling and personalization
- Student/Professor profiling from L3 Learning Store (Phase 3)

All features degrade gracefully if dependencies are unavailable.
"""

# Query learning
from .query_learner import (
    QueryLearner,
    QueryRecord,
    get_query_learner,
    save_query_learner,
    learn_from_query,
    predict_best_tool,
)

# Adaptive rubrics
from .adaptive_rubric import (
    AdaptiveRubric,
    AdaptiveRubricManager,
    get_adaptive_rubric_manager
)

# User profiling
from .user_profile import (
    UserProfile,
    UserProfileManager,
    get_user_profile_manager,
    get_user_preferences,
    update_user_profile
)

# Phase 3: Student/Professor profiling (LLM-based, L3 Learning Store)
from .profiling import (
    check_past_overrides,
    get_student_profile,
    get_professor_grading_style,
    get_ml_profiling_tools
)

__all__ = [
    # Query learner
    'QueryLearner',
    'QueryRecord',
    'get_query_learner',
    'save_query_learner',
    'learn_from_query',
    'predict_best_tool',
    
    # Adaptive rubrics
    'AdaptiveRubric',
    'AdaptiveRubricManager',
    'get_adaptive_rubric_manager',
    
    # User profiles
    'UserProfile',
    'UserProfileManager',
    'get_user_profile_manager',
    'get_user_preferences',
    'update_user_profile',
    
    # Phase 3: Profiling (L3-based)
    'check_past_overrides',
    'get_student_profile',
    'get_professor_grading_style',
    'get_ml_profiling_tools',
]

