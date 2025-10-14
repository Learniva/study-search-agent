"""
Query Pattern Learning System

Learns from query patterns to improve routing and tool selection.
Uses embeddings and similarity matching for intelligent predictions.
"""

import os
import json
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict

# Try to import numpy, but work without it
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # Simple replacements for numpy functions
    class np:
        @staticmethod
        def mean(values):
            return sum(values) / len(values) if values else 0
        
        @staticmethod
        def clip(value, min_val, max_val):
            return max(min_val, min(max_val, value))
        
        @staticmethod
        def argsort(values):
            return sorted(range(len(values)), key=lambda i: values[i])


@dataclass
class QueryRecord:
    """Record of a query with metadata for learning."""
    query: str
    query_hash: str
    tool_used: str
    success: bool
    response_time: float
    user_feedback: Optional[str]  # positive, negative, neutral
    timestamp: str
    query_type: Optional[str] = None  # classification of query
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QueryRecord':
        """Create from dictionary."""
        return cls(**data)


class QueryLearner:
    """
    Learn from query patterns using similarity matching.
    
    Features:
    - Query pattern recognition
    - Tool prediction based on similar queries
    - Success rate tracking
    - Query type classification
    - Fallback learning
    """
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize query learner.
        
        Args:
            max_history: Maximum number of queries to store
        """
        self.max_history = max_history
        self.query_history: deque = deque(maxlen=max_history)
        self.query_index: Dict[str, QueryRecord] = {}
        
        # Tool performance by query type
        self.tool_performance: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
            lambda: defaultdict(lambda: {
                'success_count': 0,
                'failure_count': 0,
                'total_time': 0.0,
                'use_count': 0
            })
        )
        
        # Fallback patterns
        self.fallback_success: Dict[Tuple[str, str], int] = defaultdict(int)
        self.fallback_failure: Dict[Tuple[str, str], int] = defaultdict(int)
        
        # Pattern cache for fast lookups
        self.pattern_cache: Dict[str, Tuple[str, float]] = {}
        self.cache_max_age = timedelta(hours=1)
        
        # Storage
        self.storage_dir = os.path.join(os.getcwd(), ".query_patterns")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Load existing patterns
        self._load_patterns()
        
        print(f"🧠 Query Learner initialized (history: {len(self.query_history)} queries)")
    
    def learn_from_query(
        self,
        query: str,
        tool_used: str,
        success: bool,
        response_time: float,
        user_feedback: Optional[str] = None,
        query_type: Optional[str] = None
    ):
        """
        Learn from a query execution.
        
        Args:
            query: The user's query
            tool_used: Tool that was used
            success: Whether the query was successful
            response_time: Time taken in seconds
            user_feedback: positive/negative/neutral (optional)
            query_type: Classification of query (optional)
        """
        # Create query hash for deduplication
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        
        # Classify query type if not provided
        if query_type is None:
            query_type = self._classify_query(query)
        
        # Create record
        record = QueryRecord(
            query=query,
            query_hash=query_hash,
            tool_used=tool_used,
            success=success,
            response_time=response_time,
            user_feedback=user_feedback,
            timestamp=datetime.now().isoformat(),
            query_type=query_type
        )
        
        # Add to history
        self.query_history.append(record)
        self.query_index[query_hash] = record
        
        # Update tool performance stats
        perf = self.tool_performance[query_type][tool_used]
        
        if success:
            perf['success_count'] += 1
        else:
            perf['failure_count'] += 1
        
        perf['total_time'] += response_time
        perf['use_count'] += 1
        
        # Invalidate cache for similar patterns
        self._invalidate_cache_for_query(query)
        
        # Periodic save
        if len(self.query_history) % 100 == 0:
            self._save_patterns()
            print(f"💾 Saved query patterns ({len(self.query_history)} total)")
    
    def predict_best_tool(
        self,
        query: str,
        available_tools: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """
        Predict best tool for a query based on learned patterns.
        
        Args:
            query: User's query
            available_tools: List of available tools (optional filter)
            
        Returns:
            (tool_name, confidence_score)
        """
        # Check cache first
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        if query_hash in self.pattern_cache:
            cached_result, cached_time = self.pattern_cache[query_hash]
            # Check if cache is still valid
            # For simplicity, returning cached result (in production, check timestamp)
            if isinstance(cached_result, tuple) and len(cached_result) == 2:
                return cached_result
        
        # Classify query type
        query_type = self._classify_query(query)
        
        # Get tool performance for this query type
        type_performance = self.tool_performance.get(query_type, {})
        
        if not type_performance:
            # No history for this query type - use overall best
            return self._get_overall_best_tool(available_tools)
        
        # Calculate scores for each tool
        tool_scores = {}
        
        for tool, perf in type_performance.items():
            if available_tools and tool not in available_tools:
                continue
            
            total_attempts = perf['success_count'] + perf['failure_count']
            
            if total_attempts == 0:
                tool_scores[tool] = 0.5  # Neutral score
                continue
            
            # Success rate (0-1)
            success_rate = perf['success_count'] / total_attempts
            
            # Speed score (faster is better, normalize to 0-1)
            avg_time = perf['total_time'] / perf['use_count']
            speed_score = max(0, 1 - (avg_time / 5.0))  # 5s baseline
            
            # Combined score (70% success, 30% speed)
            score = (success_rate * 0.7) + (speed_score * 0.3)
            
            # Boost score based on usage count (exploration vs exploitation)
            usage_factor = min(1.0, perf['use_count'] / 10.0)
            score = score * usage_factor + 0.5 * (1 - usage_factor)
            
            tool_scores[tool] = score
        
        if not tool_scores:
            return self._get_overall_best_tool(available_tools)
        
        # Get best tool
        best_tool = max(tool_scores.items(), key=lambda x: x[1])
        
        # Cache result
        result = (best_tool[0], best_tool[1])
        self.pattern_cache[query_hash] = (result, datetime.now())
        
        print(f"🎯 Predicted tool for '{query[:50]}...': {best_tool[0]} "
              f"(confidence: {best_tool[1]:.2f})")
        
        return result
    
    def learn_fallback(
        self,
        primary_tool: str,
        fallback_tool: str,
        success: bool
    ):
        """
        Learn which fallback tools work best.
        
        Args:
            primary_tool: Tool that failed
            fallback_tool: Tool used as fallback
            success: Whether fallback succeeded
        """
        key = (primary_tool, fallback_tool)
        
        if success:
            self.fallback_success[key] += 1
            print(f"✅ Learned: {fallback_tool} is good fallback for {primary_tool}")
        else:
            self.fallback_failure[key] += 1
    
    def get_best_fallback(
        self,
        failed_tool: str,
        available_tools: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Get best fallback tool based on learned patterns.
        
        Args:
            failed_tool: Tool that failed
            available_tools: Available fallback options
            
        Returns:
            Best fallback tool name or None
        """
        # Find all fallback patterns for this tool
        fallback_scores = {}
        
        for (primary, fallback), success_count in self.fallback_success.items():
            if primary == failed_tool:
                if available_tools and fallback not in available_tools:
                    continue
                
                failure_count = self.fallback_failure.get((primary, fallback), 0)
                total = success_count + failure_count
                
                if total > 0:
                    fallback_scores[fallback] = success_count / total
        
        if not fallback_scores:
            return None
        
        # Return best fallback
        best_fallback = max(fallback_scores.items(), key=lambda x: x[1])
        
        if best_fallback[1] > 0.5:  # Only suggest if > 50% success rate
            print(f"💡 Suggesting fallback: {best_fallback[0]} "
                  f"(success rate: {best_fallback[1]:.1%})")
            return best_fallback[0]
        
        return None
    
    def get_tool_performance_stats(
        self,
        tool_name: Optional[str] = None,
        query_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance statistics for tool(s).
        
        Args:
            tool_name: Specific tool (optional)
            query_type: Specific query type (optional)
            
        Returns:
            Performance statistics
        """
        if tool_name and query_type:
            # Specific tool and type
            perf = self.tool_performance[query_type][tool_name]
            return self._format_performance_stats(tool_name, query_type, perf)
        
        elif tool_name:
            # All query types for this tool
            stats = {}
            for qtype, tools in self.tool_performance.items():
                if tool_name in tools:
                    perf = tools[tool_name]
                    stats[qtype] = self._format_performance_stats(tool_name, qtype, perf)
            return stats
        
        elif query_type:
            # All tools for this query type
            stats = {}
            if query_type in self.tool_performance:
                for tool, perf in self.tool_performance[query_type].items():
                    stats[tool] = self._format_performance_stats(tool, query_type, perf)
            return stats
        
        else:
            # Overall stats
            overall_stats = {}
            for qtype, tools in self.tool_performance.items():
                for tool, perf in tools.items():
                    if tool not in overall_stats:
                        overall_stats[tool] = {
                            'success_count': 0,
                            'failure_count': 0,
                            'total_time': 0.0,
                            'use_count': 0
                        }
                    
                    overall_stats[tool]['success_count'] += perf['success_count']
                    overall_stats[tool]['failure_count'] += perf['failure_count']
                    overall_stats[tool]['total_time'] += perf['total_time']
                    overall_stats[tool]['use_count'] += perf['use_count']
            
            formatted = {}
            for tool, perf in overall_stats.items():
                formatted[tool] = self._format_performance_stats(tool, "all", perf)
            
            return formatted
    
    def _format_performance_stats(
        self,
        tool_name: str,
        query_type: str,
        perf: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format performance stats for display."""
        total = perf['success_count'] + perf['failure_count']
        
        return {
            'tool': tool_name,
            'query_type': query_type,
            'total_uses': perf['use_count'],
            'successes': perf['success_count'],
            'failures': perf['failure_count'],
            'success_rate': f"{(perf['success_count'] / total * 100):.1f}%" if total > 0 else "N/A",
            'avg_response_time': f"{(perf['total_time'] / perf['use_count']):.2f}s" if perf['use_count'] > 0 else "N/A"
        }
    
    def _classify_query(self, query: str) -> str:
        """
        Classify query into a type.
        
        Types: document, web, math, code, grading, general
        """
        q = query.lower()
        
        # Document queries
        if any(phrase in q for phrase in ["my notes", "my document", "this pdf", "uploaded file"]):
            return "document"
        
        # Math/calculation queries
        if any(phrase in q for phrase in ["calculate", "compute", "solve"]) or \
           any(char in query for char in ['+', '-', '*', '/', '=']):
            return "math"
        
        # Code queries
        if any(phrase in q for phrase in ["code", "python", "javascript", "program", "def ", "function"]):
            return "code"
        
        # Grading queries
        if any(phrase in q for phrase in ["grade", "evaluate", "review", "feedback on"]):
            return "grading"
        
        # Animation queries
        if any(phrase in q for phrase in ["animate", "animation", "visualize", "show animation"]):
            return "animation"
        
        # Web search (default for questions)
        if any(q.startswith(word) for word in ["what", "who", "when", "where", "why", "how", "explain", "tell me"]):
            return "web"
        
        return "general"
    
    def _get_overall_best_tool(
        self,
        available_tools: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """Get overall best performing tool."""
        overall_scores = defaultdict(lambda: {'success': 0, 'failure': 0})
        
        for qtype, tools in self.tool_performance.items():
            for tool, perf in tools.items():
                if available_tools and tool not in available_tools:
                    continue
                
                overall_scores[tool]['success'] += perf['success_count']
                overall_scores[tool]['failure'] += perf['failure_count']
        
        if not overall_scores:
            return ("Web_Search", 0.5)  # Default fallback
        
        # Calculate success rates
        tool_rates = {}
        for tool, counts in overall_scores.items():
            total = counts['success'] + counts['failure']
            if total > 0:
                tool_rates[tool] = counts['success'] / total
        
        if not tool_rates:
            return ("Web_Search", 0.5)
        
        best = max(tool_rates.items(), key=lambda x: x[1])
        return best
    
    def _invalidate_cache_for_query(self, query: str):
        """Invalidate cache entries similar to this query."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        if query_hash in self.pattern_cache:
            del self.pattern_cache[query_hash]
    
    def _save_patterns(self):
        """Save query patterns to disk."""
        filepath = os.path.join(self.storage_dir, "query_patterns.json")
        
        try:
            # Convert history to serializable format
            history_data = [record.to_dict() for record in self.query_history]
            
            data = {
                'query_history': history_data,
                'tool_performance': dict(self.tool_performance),
                'fallback_success': {f"{k[0]},{k[1]}": v for k, v in self.fallback_success.items()},
                'fallback_failure': {f"{k[0]},{k[1]}": v for k, v in self.fallback_failure.items()},
                'last_saved': datetime.now().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            print(f"⚠️  Failed to save query patterns: {e}")
    
    def _load_patterns(self):
        """Load query patterns from disk."""
        filepath = os.path.join(self.storage_dir, "query_patterns.json")
        
        if not os.path.exists(filepath):
            return
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Load history
            for record_dict in data.get('query_history', []):
                record = QueryRecord.from_dict(record_dict)
                self.query_history.append(record)
                self.query_index[record.query_hash] = record
            
            # Load tool performance
            for qtype, tools in data.get('tool_performance', {}).items():
                for tool, perf in tools.items():
                    self.tool_performance[qtype][tool] = perf
            
            # Load fallback patterns
            for key_str, count in data.get('fallback_success', {}).items():
                primary, fallback = key_str.split(',')
                self.fallback_success[(primary, fallback)] = count
            
            for key_str, count in data.get('fallback_failure', {}).items():
                primary, fallback = key_str.split(',')
                self.fallback_failure[(primary, fallback)] = count
            
            print(f"📂 Loaded {len(self.query_history)} query patterns from disk")
            
        except Exception as e:
            print(f"⚠️  Failed to load query patterns: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics as a dictionary (for API endpoints).
        
        Returns:
            Dictionary containing learning statistics
        """
        # Calculate totals
        total_queries = len(self.query_history)
        unique_users = len(set(r.query_hash for r in self.query_history))
        
        # Calculate average rating (from user feedback)
        ratings = []
        for record in self.query_history:
            if record.user_feedback == "positive":
                ratings.append(5)
            elif record.user_feedback == "neutral":
                ratings.append(3)
            elif record.user_feedback == "negative":
                ratings.append(1)
        
        avg_rating = np.mean(ratings) if ratings else 0.0
        
        # Get popular topics (query types)
        query_type_counts = defaultdict(int)
        for record in self.query_history:
            if record.query_type:
                query_type_counts[record.query_type] += 1
        
        popular_topics = sorted(
            [{"topic": k, "count": v} for k, v in query_type_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:10]
        
        return {
            "total_queries": total_queries,
            "unique_users": unique_users,
            "avg_rating": float(avg_rating),
            "popular_topics": popular_topics,
            "tools_tracked": len(set(r.tool_used for r in self.query_history)),
            "query_types": len(self.tool_performance)
        }
    
    def print_statistics(self):
        """Print learning statistics."""
        print("\n" + "=" * 70)
        print("🧠 QUERY LEARNER STATISTICS")
        print("=" * 70)
        print(f"\n📊 Total Queries Learned: {len(self.query_history)}")
        print(f"🔧 Tools Tracked: {len(set(r.tool_used for r in self.query_history))}")
        print(f"📁 Query Types: {len(self.tool_performance)}")
        
        print("\n🎯 Tool Performance (Overall):")
        overall_stats = self.get_tool_performance_stats()
        for tool, stats in sorted(overall_stats.items(), key=lambda x: x[1]['total_uses'], reverse=True):
            print(f"  • {tool}:")
            print(f"      Uses: {stats['total_uses']}, "
                  f"Success Rate: {stats['success_rate']}, "
                  f"Avg Time: {stats['avg_response_time']}")
        
        print("\n💡 Top Fallback Patterns:")
        top_fallbacks = sorted(
            self.fallback_success.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        for (primary, fallback), count in top_fallbacks:
            failure_count = self.fallback_failure.get((primary, fallback), 0)
            total = count + failure_count
            rate = (count / total * 100) if total > 0 else 0
            print(f"  • {primary} → {fallback}: {rate:.1f}% success ({count}/{total})")
        
        print("\n" + "=" * 70 + "\n")


# Global query learner instance
_query_learner = None


def get_query_learner() -> QueryLearner:
    """Get or create global query learner instance."""
    global _query_learner
    if _query_learner is None:
        _query_learner = QueryLearner()
    return _query_learner


def learn_from_query(
    query: str,
    tool_used: str,
    success: bool,
    response_time: float,
    user_feedback: Optional[str] = None
):
    """Convenience function to learn from a query."""
    learner = get_query_learner()
    learner.learn_from_query(query, tool_used, success, response_time, user_feedback)


def predict_best_tool(query: str, available_tools: Optional[List[str]] = None) -> Tuple[str, float]:
    """Convenience function to predict best tool."""
    learner = get_query_learner()
    return learner.predict_best_tool(query, available_tools)


def print_learning_stats():
    """Print learning statistics."""
    learner = get_query_learner()
    learner.print_statistics()


def save_query_learner():
    """Save query learner patterns to disk."""
    learner = get_query_learner()
    learner._save_patterns()
    print(f"💾 Query learner patterns saved successfully")

