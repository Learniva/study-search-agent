"""
User Profile Learning System

Learns user preferences, patterns, and adapts agent behavior accordingly.
"""

import os
import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict, field

# Try to import database modules
try:
    from database import get_db
    from database.models import UserLearningProfile
    from sqlalchemy.orm import Session
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    UserLearningProfile = None


@dataclass
class UserProfile:
    """
    User profile with learned preferences and patterns.
    
    Tracks:
    - Interaction patterns
    - Tool preferences
    - Response style preferences
    - Subject area expertise
    - Performance metrics
    """
    user_id: str
    role: str  # student, teacher, professor
    
    # Learning preferences
    preferred_explanation_depth: str = "moderate"  # brief, moderate, detailed
    preferred_citation_style: Optional[str] = None  # APA, MLA, Chicago
    typical_subject_areas: List[str] = field(default_factory=list)
    education_level: Optional[str] = None  # high_school, undergraduate, graduate
    
    # Interaction patterns (learned over time)
    average_question_length: float = 50.0
    common_tools_used: Dict[str, int] = field(default_factory=dict)
    typical_session_duration: float = 600.0  # 10 minutes
    queries_per_session: float = 5.0
    
    # Feedback history
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    neutral_feedback_count: int = 0
    correction_patterns: List[Dict] = field(default_factory=list)
    
    # Performance metrics (0-1 scale)
    satisfaction_score: float = 0.5  # Derived from feedback
    response_relevance_score: float = 0.5
    tool_selection_accuracy: float = 0.5
    
    # Adaptation weights (learned preferences)
    routing_preferences: Dict[str, float] = field(default_factory=dict)
    temperature_preference: float = 0.7  # LLM creativity level
    context_window_preference: int = 2  # Messages to include
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    interactions_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserProfile':
        """Create from dictionary."""
        # Handle nested default factories
        if 'typical_subject_areas' not in data:
            data['typical_subject_areas'] = []
        if 'common_tools_used' not in data:
            data['common_tools_used'] = {}
        if 'correction_patterns' not in data:
            data['correction_patterns'] = []
        if 'routing_preferences' not in data:
            data['routing_preferences'] = {}
        
        return cls(**data)


class UserProfileManager:
    """
    Manages user profiles with learning and adaptation.
    
    Features:
    - Profile CRUD operations
    - Online learning from interactions
    - Preference adaptation
    - Pattern recognition
    """
    
    def __init__(self, storage_backend: str = "file"):
        """
        Initialize profile manager.
        
        Args:
            storage_backend: "file" or "database"
        """
        self.storage_backend = storage_backend
        self.profiles = {}  # In-memory cache
        
        # File-based storage
        self.storage_dir = os.path.join(os.getcwd(), ".user_profiles")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Learning parameters
        self.learning_rate = 0.1  # For exponential moving average
        self.decay_factor = 0.95  # For topic relevance decay
        
        print(f"📊 User Profile Manager initialized (backend: {storage_backend})")
    
    def get_or_create_profile(self, user_id: str, role: str = "student") -> UserProfile:
        """
        Get existing profile or create new one.
        
        Args:
            user_id: User identifier
            role: User role (student, teacher, professor)
            
        Returns:
            UserProfile object
        """
        # Check cache
        if user_id in self.profiles:
            return self.profiles[user_id]
        
        # Try to load from storage
        profile = self._load_profile(user_id)
        
        if profile is None:
            # Create new profile
            profile = UserProfile(user_id=user_id, role=role)
            print(f"✨ Created new profile for user: {user_id} (role: {role})")
        else:
            print(f"📂 Loaded existing profile for user: {user_id}")
        
        # Cache it
        self.profiles[user_id] = profile
        
        return profile
    
    def update_from_interaction(
        self,
        user_id: str,
        query: str,
        tool_used: str,
        response_time: float,
        feedback: Optional[str] = None,  # positive, negative, neutral
        user_followup: Optional[str] = None
    ):
        """
        Update user profile based on interaction.
        
        Uses online learning with exponential moving average.
        
        Args:
            user_id: User identifier
            query: User's query
            tool_used: Tool that was used
            response_time: Time taken to respond
            feedback: Explicit feedback (optional)
            user_followup: User's follow-up question (optional)
        """
        profile = self.get_or_create_profile(user_id)
        
        # Update interaction count
        profile.interactions_count += 1
        
        # Update average question length (EMA)
        query_length = len(query.split())
        profile.average_question_length = (
            self.learning_rate * query_length +
            (1 - self.learning_rate) * profile.average_question_length
        )
        
        # Update tool usage counts
        if tool_used not in profile.common_tools_used:
            profile.common_tools_used[tool_used] = 0
        profile.common_tools_used[tool_used] += 1
        
        # Update routing preferences based on feedback
        if feedback == "positive":
            profile.positive_feedback_count += 1
            if tool_used not in profile.routing_preferences:
                profile.routing_preferences[tool_used] = 1.0
            profile.routing_preferences[tool_used] = min(
                2.0,
                profile.routing_preferences[tool_used] + 0.1
            )
        elif feedback == "negative":
            profile.negative_feedback_count += 1
            if tool_used not in profile.routing_preferences:
                profile.routing_preferences[tool_used] = 1.0
            profile.routing_preferences[tool_used] = max(
                0.5,
                profile.routing_preferences[tool_used] - 0.05
            )
        elif feedback == "neutral":
            profile.neutral_feedback_count += 1
        
        # Update satisfaction score (EMA)
        if feedback:
            feedback_value = {
                "positive": 1.0,
                "neutral": 0.5,
                "negative": 0.0
            }.get(feedback, 0.5)
            
            profile.satisfaction_score = (
                self.learning_rate * feedback_value +
                (1 - self.learning_rate) * profile.satisfaction_score
            )
        
        # Learn explanation depth preference from follow-up
        if user_followup:
            if any(phrase in user_followup.lower() for phrase in 
                   ["more detail", "explain further", "elaborate", "tell me more"]):
                profile.preferred_explanation_depth = "detailed"
                print(f"📝 Learned: User {user_id} prefers detailed explanations")
            
            elif any(phrase in user_followup.lower() for phrase in
                     ["too long", "summarize", "shorter", "brief", "tldr"]):
                profile.preferred_explanation_depth = "brief"
                print(f"📝 Learned: User {user_id} prefers brief explanations")
        
        # Extract and update subject areas
        extracted_topics = self._extract_topics(query)
        if extracted_topics:
            self._update_subject_areas(profile, extracted_topics)
        
        # Update timestamp
        profile.last_updated = datetime.now().isoformat()
        
        # Save profile
        self._save_profile(profile)
        
        print(f"📈 Updated profile for {user_id}: "
              f"satisfaction={profile.satisfaction_score:.2f}, "
              f"interactions={profile.interactions_count}")
    
    def _extract_topics(self, text: str) -> List[str]:
        """
        Extract topics from text using simple keyword extraction.
        
        In production, would use NLP/embeddings.
        """
        # Common academic/technical topics
        topic_keywords = {
            "machine learning", "deep learning", "neural networks",
            "calculus", "linear algebra", "statistics",
            "physics", "chemistry", "biology",
            "programming", "python", "javascript", "java",
            "history", "literature", "philosophy",
            "economics", "psychology", "sociology"
        }
        
        text_lower = text.lower()
        found_topics = []
        
        for topic in topic_keywords:
            if topic in text_lower:
                found_topics.append(topic)
        
        return found_topics
    
    def _update_subject_areas(self, profile: UserProfile, new_topics: List[str]):
        """
        Update subject areas with decay for old topics.
        
        Uses TF-IDF-like scoring with decay.
        """
        # Increment scores for new topics
        topic_scores = defaultdict(float)
        
        # Load existing topics with decayed scores
        for topic in profile.typical_subject_areas:
            topic_scores[topic] = 1.0 * self.decay_factor
        
        # Add new topics
        for topic in new_topics:
            topic_scores[topic] += 1.0
        
        # Keep top 10 topics
        sorted_topics = sorted(
            topic_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        profile.typical_subject_areas = [topic for topic, score in sorted_topics]
    
    def get_personalization_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get personalization settings for a user.
        
        Returns:
            Dict with temperature, context_window, explanation_depth, etc.
        """
        profile = self.get_or_create_profile(user_id)
        
        return {
            "temperature": profile.temperature_preference,
            "context_window_size": profile.context_window_preference,
            "explanation_depth": profile.preferred_explanation_depth,
            "citation_style": profile.preferred_citation_style,
            "typical_subjects": profile.typical_subject_areas,
            "routing_preferences": profile.routing_preferences
        }
    
    def get_tool_preference(self, user_id: str, tool_name: str) -> float:
        """
        Get user's preference weight for a specific tool.
        
        Args:
            user_id: User identifier
            tool_name: Name of tool
            
        Returns:
            Preference weight (0.5-2.0, default 1.0)
        """
        profile = self.get_or_create_profile(user_id)
        return profile.routing_preferences.get(tool_name, 1.0)
    
    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary of user profile for display/debugging.
        
        Returns:
            Dictionary with key profile metrics
        """
        profile = self.get_or_create_profile(user_id)
        
        # Calculate feedback percentages
        total_feedback = (
            profile.positive_feedback_count +
            profile.negative_feedback_count +
            profile.neutral_feedback_count
        )
        
        if total_feedback > 0:
            positive_pct = (profile.positive_feedback_count / total_feedback) * 100
            negative_pct = (profile.negative_feedback_count / total_feedback) * 100
        else:
            positive_pct = negative_pct = 0
        
        # Get most used tools
        top_tools = sorted(
            profile.common_tools_used.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        return {
            "user_id": profile.user_id,
            "role": profile.role,
            "interactions": profile.interactions_count,
            "satisfaction": f"{profile.satisfaction_score:.2f}",
            "positive_feedback": f"{positive_pct:.1f}%",
            "negative_feedback": f"{negative_pct:.1f}%",
            "preferred_depth": profile.preferred_explanation_depth,
            "top_tools": [f"{tool} ({count}x)" for tool, count in top_tools],
            "top_subjects": profile.typical_subject_areas[:5],
            "created": profile.created_at,
            "last_updated": profile.last_updated
        }
    
    def _load_profile(self, user_id: str) -> Optional[UserProfile]:
        """Load profile from storage."""
        if self.storage_backend == "file":
            return self._load_profile_from_file(user_id)
        elif self.storage_backend == "database" and DATABASE_AVAILABLE:
            return self._load_profile_from_database(user_id)
        return None
    
    def _save_profile(self, profile: UserProfile):
        """Save profile to storage."""
        if self.storage_backend == "file":
            self._save_profile_to_file(profile)
        elif self.storage_backend == "database" and DATABASE_AVAILABLE:
            self._save_profile_to_database(profile)
    
    def _load_profile_from_file(self, user_id: str) -> Optional[UserProfile]:
        """Load profile from JSON file."""
        # Create safe filename
        safe_id = hashlib.md5(user_id.encode()).hexdigest()
        filepath = os.path.join(self.storage_dir, f"{safe_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return UserProfile.from_dict(data)
        except Exception as e:
            print(f"⚠️  Failed to load profile: {e}")
            return None
    
    def _save_profile_to_file(self, profile: UserProfile):
        """Save profile to JSON file."""
        safe_id = hashlib.md5(profile.user_id.encode()).hexdigest()
        filepath = os.path.join(self.storage_dir, f"{safe_id}.json")
        
        try:
            with open(filepath, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save profile: {e}")
    
    def _load_profile_from_database(self, user_id: str) -> Optional[UserProfile]:
        """Load profile from PostgreSQL database."""
        if not DATABASE_AVAILABLE or UserLearningProfile is None:
            print("⚠️  Database not available, falling back to file storage")
            return None
        
        try:
            with get_db() as db:
                # Query for existing profile
                db_profile = db.query(UserLearningProfile).filter(
                    UserLearningProfile.user_id == user_id
                ).first()
                
                if not db_profile:
                    return None
                
                # Convert database model to UserProfile dataclass
                profile = UserProfile(
                    user_id=db_profile.user_id,
                    role=db_profile.role,
                    preferred_explanation_depth=db_profile.preferred_explanation_depth,
                    preferred_citation_style=db_profile.preferred_citation_style,
                    typical_subject_areas=db_profile.typical_subject_areas or [],
                    education_level=db_profile.education_level,
                    average_question_length=db_profile.average_question_length,
                    common_tools_used=db_profile.common_tools_used or {},
                    typical_session_duration=db_profile.typical_session_duration,
                    queries_per_session=db_profile.queries_per_session,
                    positive_feedback_count=db_profile.positive_feedback_count,
                    negative_feedback_count=db_profile.negative_feedback_count,
                    neutral_feedback_count=db_profile.neutral_feedback_count,
                    correction_patterns=db_profile.correction_patterns or [],
                    satisfaction_score=db_profile.satisfaction_score,
                    response_relevance_score=db_profile.response_relevance_score,
                    tool_selection_accuracy=db_profile.tool_selection_accuracy,
                    routing_preferences=db_profile.routing_preferences or {},
                    temperature_preference=db_profile.temperature_preference,
                    context_window_preference=db_profile.context_window_preference,
                    created_at=db_profile.created_at.isoformat(),
                    last_updated=db_profile.last_updated.isoformat(),
                    interactions_count=db_profile.interactions_count
                )
                
                return profile
                
        except Exception as e:
            print(f"⚠️  Failed to load profile from database: {e}")
            return None
    
    def _save_profile_to_database(self, profile: UserProfile):
        """Save profile to PostgreSQL database."""
        if not DATABASE_AVAILABLE or UserLearningProfile is None:
            print("⚠️  Database not available, profile saved to file only")
            return
        
        try:
            with get_db() as db:
                # Check if profile exists
                db_profile = db.query(UserLearningProfile).filter(
                    UserLearningProfile.user_id == profile.user_id
                ).first()
                
                if db_profile:
                    # Update existing profile
                    db_profile.role = profile.role
                    db_profile.preferred_explanation_depth = profile.preferred_explanation_depth
                    db_profile.preferred_citation_style = profile.preferred_citation_style
                    db_profile.typical_subject_areas = profile.typical_subject_areas
                    db_profile.education_level = profile.education_level
                    db_profile.average_question_length = profile.average_question_length
                    db_profile.common_tools_used = profile.common_tools_used
                    db_profile.typical_session_duration = profile.typical_session_duration
                    db_profile.queries_per_session = profile.queries_per_session
                    db_profile.positive_feedback_count = profile.positive_feedback_count
                    db_profile.negative_feedback_count = profile.negative_feedback_count
                    db_profile.neutral_feedback_count = profile.neutral_feedback_count
                    db_profile.correction_patterns = profile.correction_patterns
                    db_profile.satisfaction_score = profile.satisfaction_score
                    db_profile.response_relevance_score = profile.response_relevance_score
                    db_profile.tool_selection_accuracy = profile.tool_selection_accuracy
                    db_profile.routing_preferences = profile.routing_preferences
                    db_profile.temperature_preference = profile.temperature_preference
                    db_profile.context_window_preference = profile.context_window_preference
                    db_profile.interactions_count = profile.interactions_count
                    db_profile.last_updated = datetime.now()
                else:
                    # Create new profile
                    db_profile = UserLearningProfile(
                        user_id=profile.user_id,
                        role=profile.role,
                        preferred_explanation_depth=profile.preferred_explanation_depth,
                        preferred_citation_style=profile.preferred_citation_style,
                        typical_subject_areas=profile.typical_subject_areas,
                        education_level=profile.education_level,
                        average_question_length=profile.average_question_length,
                        common_tools_used=profile.common_tools_used,
                        typical_session_duration=profile.typical_session_duration,
                        queries_per_session=profile.queries_per_session,
                        positive_feedback_count=profile.positive_feedback_count,
                        negative_feedback_count=profile.negative_feedback_count,
                        neutral_feedback_count=profile.neutral_feedback_count,
                        correction_patterns=profile.correction_patterns,
                        satisfaction_score=profile.satisfaction_score,
                        response_relevance_score=profile.response_relevance_score,
                        tool_selection_accuracy=profile.tool_selection_accuracy,
                        routing_preferences=profile.routing_preferences,
                        temperature_preference=profile.temperature_preference,
                        context_window_preference=profile.context_window_preference,
                        interactions_count=profile.interactions_count
                    )
                    db.add(db_profile)
                
                db.commit()
                
        except Exception as e:
            print(f"⚠️  Failed to save profile to database: {e}")


# Global profile manager instance
_profile_manager = None


def get_profile_manager() -> UserProfileManager:
    """Get or create global profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = UserProfileManager(storage_backend="file")
    return _profile_manager


def update_user_profile(
    user_id: str,
    query: str,
    tool_used: str,
    response_time: float,
    feedback: Optional[str] = None,
    user_followup: Optional[str] = None
):
    """
    Convenience function to update user profile.
    
    Args:
        user_id: User identifier
        query: User's query
        tool_used: Tool that was used
        response_time: Response time in seconds
        feedback: positive/negative/neutral (optional)
        user_followup: User's follow-up question (optional)
    """
    manager = get_profile_manager()
    manager.update_from_interaction(
        user_id=user_id,
        query=query,
        tool_used=tool_used,
        response_time=response_time,
        feedback=feedback,
        user_followup=user_followup
    )


def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get personalization preferences for a user.
    
    Returns:
        Dict with user preferences
    """
    manager = get_profile_manager()
    return manager.get_personalization_settings(user_id)


def get_tool_preference(user_id: str, tool_name: str) -> float:
    """
    Get user's learned preference for a tool.
    
    Returns:
        Preference weight (0.5-2.0, default 1.0)
    """
    manager = get_profile_manager()
    return manager.get_tool_preference(user_id, tool_name)


def print_user_profile(user_id: str):
    """Print user profile summary."""
    manager = get_profile_manager()
    summary = manager.get_profile_summary(user_id)
    
    print("\n" + "=" * 70)
    print(f"📊 USER PROFILE: {summary['user_id']}")
    print("=" * 70)
    print(f"\n🎓 Role: {summary['role']}")
    print(f"💬 Interactions: {summary['interactions']}")
    print(f"😊 Satisfaction: {summary['satisfaction']}")
    print(f"👍 Positive: {summary['positive_feedback']}")
    print(f"👎 Negative: {summary['negative_feedback']}")
    print(f"\n📝 Preferences:")
    print(f"  • Explanation Depth: {summary['preferred_depth']}")
    print(f"\n🔧 Top Tools:")
    for tool in summary['top_tools']:
        print(f"  • {tool}")
    print(f"\n📚 Subject Areas:")
    for subject in summary['top_subjects']:
        print(f"  • {subject}")
    print(f"\n⏰ Created: {summary['created']}")
    print(f"🔄 Last Updated: {summary['last_updated']}")
    print("=" * 70 + "\n")


# Alias for consistency with import naming
get_user_profile_manager = get_profile_manager

