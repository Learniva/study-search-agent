"""
Machine Learning & Adaptive Features Package

Provides intelligent learning and adaptation capabilities:
- Query pattern learning and prediction
- Adaptive rubrics that learn from feedback
- User profiling and personalization

All features degrade gracefully if dependencies are unavailable.
"""

# Query learning
from .query_learner import (
    QueryLearner,
    QueryRecord,
    get_query_learner,
    save_query_learner
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

__all__ = [
    # Query learner
    'QueryLearner',
    'QueryRecord',
    'get_query_learner',
    'save_query_learner',
    
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
]

