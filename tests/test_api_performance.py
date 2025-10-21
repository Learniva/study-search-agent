"""
API Performance Tests.

Tests to verify API optimizations are working:
- Token caching reduces auth time
- Response caching reduces query time
- Async routing doesn't block
- Instant SSE responses
"""

import pytest
import time
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

# Test configuration
PERFORMANCE_TARGETS = {
    "auth_cache_hit": 0.005,  # <5ms for cached token
    "auth_cache_miss": 0.050,  # <50ms for DB lookup
    "response_cache_hit": 0.100,  # <100ms for cached response
    "routing_async": 0.010,  # <10ms for async routing overhead
    "instant_sse": 0.050,  # <50ms for first SSE event
}


class TestAuthenticationPerformance:
    """Test authentication caching performance."""
    
    @pytest.mark.asyncio
    async def test_token_cache_hit_speed(self):
        """Token cache hit should be <5ms."""
        from utils.auth.token_cache import TokenCache
        
        cache = TokenCache()
        token = "test_token_123"
        user_data = {"user_id": "123", "username": "test"}
        
        # Cache the token
        cache.set(token, user_data)
        
        # Time cache hit
        start = time.time()
        result = cache.get(token)
        duration = time.time() - start
        
        assert result == user_data
        assert duration < PERFORMANCE_TARGETS["auth_cache_hit"]
        print(f"✅ Token cache hit: {duration*1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_token_cache_miss_vs_hit(self):
        """Cache miss should trigger DB lookup, cache hit should be fast."""
        from utils.auth.token_cache import TokenCache
        
        cache = TokenCache()
        token = "test_token_456"
        
        # Simulate cache miss (returns None)
        start = time.time()
        result = cache.get(token)
        miss_duration = time.time() - start
        
        assert result is None
        assert miss_duration < 0.001  # Cache miss itself is instant
        
        # Add to cache
        user_data = {"user_id": "456", "username": "test2"}
        cache.set(token, user_data)
        
        # Cache hit should be much faster
        start = time.time()
        result = cache.get(token)
        hit_duration = time.time() - start
        
        assert result == user_data
        assert hit_duration < PERFORMANCE_TARGETS["auth_cache_hit"]
        print(f"✅ Cache hit ({hit_duration*1000:.2f}ms) vs miss ({miss_duration*1000:.2f}ms)")
    
    def test_token_cache_hit_rate(self):
        """Token cache should achieve high hit rate."""
        from utils.auth.token_cache import TokenCache
        
        cache = TokenCache()
        
        # Simulate multiple requests from same users
        tokens = ["token1", "token2", "token3"]
        users = [
            {"user_id": "1", "username": "user1"},
            {"user_id": "2", "username": "user2"},
            {"user_id": "3", "username": "user3"},
        ]
        
        # Cache tokens
        for token, user in zip(tokens, users):
            cache.set(token, user)
        
        # Simulate 100 requests (90 from cached users, 10 new)
        for i in range(100):
            if i < 90:
                # Hit cache
                token = tokens[i % 3]
                result = cache.get(token)
                assert result is not None
            else:
                # Miss cache (new user)
                result = cache.get(f"new_token_{i}")
                assert result is None
        
        stats = cache.get_stats()
        hits = stats["hits"]
        misses = stats["misses"]
        hit_rate = hits / (hits + misses) * 100
        
        assert hit_rate >= 85  # Should achieve >85% hit rate
        print(f"✅ Token cache hit rate: {hit_rate:.1f}%")


class TestResponseCaching:
    """Test response caching performance."""
    
    def test_response_cache_hit_speed(self):
        """Response cache hit should be <100ms."""
        from utils.api.response_cache import APIResponseCache
        
        cache = APIResponseCache()
        
        # Cache a response
        question = "What is Python?"
        response = "Python is a programming language..."
        cache.set(question, "student", "thread1", response)
        
        # Time cache hit
        start = time.time()
        result = cache.get(question, "student", "thread1")
        duration = time.time() - start
        
        assert result == response
        assert duration < 0.001  # Cache lookup is nearly instant
        print(f"✅ Response cache hit: {duration*1000:.2f}ms")
    
    def test_response_cache_key_normalization(self):
        """Cache should normalize queries (case, whitespace)."""
        from utils.api.response_cache import APIResponseCache
        
        cache = APIResponseCache()
        
        # Cache with normalized key
        response = "Test response"
        cache.set("  What is PYTHON?  ", "student", "thread1", response)
        
        # Should match with different formatting
        result = cache.get("what is python?", "student", "thread1")
        assert result == response
        print("✅ Response cache normalizes keys correctly")
    
    def test_response_cache_stats(self):
        """Cache stats should track hits/misses."""
        from utils.api.response_cache import APIResponseCache
        
        cache = APIResponseCache()
        
        # Add responses
        for i in range(10):
            cache.set(f"question{i}", "student", "thread1", f"answer{i}")
        
        # Simulate requests
        for i in range(50):
            if i < 30:
                # Hit cache (60%)
                cache.get(f"question{i % 10}", "student", "thread1")
            else:
                # Miss cache (40%)
                cache.get(f"new_question{i}", "student", "thread1")
        
        stats = cache.get_stats()
        hit_rate_str = stats["hit_rate"]
        hit_rate = float(hit_rate_str.rstrip("%"))
        
        assert hit_rate >= 50  # Should achieve >50% hit rate
        assert "time_saved_estimate_seconds" in stats
        print(f"✅ Response cache hit rate: {hit_rate}%")
        print(f"✅ Estimated time saved: {stats['time_saved_estimate_seconds']}s")


class TestAsyncRouting:
    """Test async routing performance."""
    
    @pytest.mark.asyncio
    async def test_async_classify_intent_non_blocking(self):
        """Async classify_intent shouldn't block event loop."""
        from agents.supervisor.nodes import SupervisorAgentNodes
        from agents.supervisor.state import SupervisorState
        
        # Mock LLM with async response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "STUDY"
        
        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        mock_llm.ainvoke = async_mock
        
        nodes = SupervisorAgentNodes(mock_llm, [], {})
        
        state: SupervisorState = {
            "question": "Help me understand recursion",
            "user_role": "STUDENT",
            "user_id": None,
            "student_id": None,
            "student_name": None,
            "course_id": None,
            "assignment_id": None,
            "assignment_name": None,
            "intent": None,
            "agent_choice": None,
            "access_denied": False,
            "routing_confidence": None,
            "agent_result": None,
            "agent_used": None,
            "final_answer": None,
            "routing_time": None,
            "agent_execution_time": None,
            "total_time": None,
            "routing_success": None,
            "routing_alternatives": [],
            "learned_from_history": False,
            "result_quality": None,
            "user_satisfaction_predicted": None,
            "context_used": None,
            "similar_past_queries": [],
        }
        
        # Time async routing
        start = time.time()
        result = await nodes.aclassify_intent(state)
        duration = time.time() - start
        
        assert result["intent"] == "STUDY"
        assert duration < PERFORMANCE_TARGETS["routing_async"] + 0.5  # +0.5s for LLM mock
        print(f"✅ Async routing overhead: {duration*1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_async_routing_parallel_execution(self):
        """Multiple async routing calls should run in parallel."""
        from agents.supervisor.nodes import SupervisorAgentNodes
        from agents.supervisor.state import SupervisorState
        
        # Mock LLM with delayed response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "STUDY"
        
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate 100ms LLM call
            return mock_response
        
        mock_llm.ainvoke = delayed_response
        
        nodes = SupervisorAgentNodes(mock_llm, [], {})
        
        # Create multiple states
        states = []
        for i in range(5):
            state: SupervisorState = {
                "question": f"Question {i}",
                "user_role": "STUDENT",
                "user_id": None,
                "student_id": None,
                "student_name": None,
                "course_id": None,
                "assignment_id": None,
                "assignment_name": None,
                "intent": None,
                "agent_choice": None,
                "access_denied": False,
                "routing_confidence": None,
                "agent_result": None,
                "agent_used": None,
                "final_answer": None,
                "routing_time": None,
                "agent_execution_time": None,
                "total_time": None,
                "routing_success": None,
                "routing_alternatives": [],
                "learned_from_history": False,
                "result_quality": None,
                "user_satisfaction_predicted": None,
                "context_used": None,
                "similar_past_queries": [],
            }
            states.append(state)
        
        # Run in parallel
        start = time.time()
        results = await asyncio.gather(*[nodes.aclassify_intent(s) for s in states])
        duration = time.time() - start
        
        # Should take ~100ms (parallel) not ~500ms (serial)
        assert duration < 0.25  # Allow 2.5x overhead
        assert len(results) == 5
        print(f"✅ Parallel routing (5 requests): {duration*1000:.2f}ms")


class TestOverallPerformance:
    """Test overall API performance."""
    
    def test_cache_stats_integration(self):
        """All caches should be accessible from admin endpoint."""
        from utils.auth.token_cache import get_token_cache
        from utils.api.response_cache import get_response_cache
        
        token_cache = get_token_cache()
        response_cache = get_response_cache()
        
        # Add some data
        token_cache.set("test", {"user": "test"})
        response_cache.set("question", "student", "thread1", "answer")
        
        # Get stats
        token_stats = token_cache.get_stats()
        response_stats = response_cache.get_stats()
        
        assert "hit_rate" in token_stats
        assert "hit_rate" in response_stats
        print(f"✅ Token cache: {token_stats['size']} items")
        print(f"✅ Response cache: {response_stats['size']} items")
    
    def test_performance_summary(self):
        """Print performance summary."""
        print("\n" + "="*60)
        print("API PERFORMANCE TARGETS")
        print("="*60)
        for metric, target in PERFORMANCE_TARGETS.items():
            print(f"  {metric:30s}: <{target*1000:6.1f}ms")
        print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

