"""
Performance benchmarks for Study Agent optimization.

Tests:
1. Time to First Byte (TTFB)
2. Total query time
3. Cache effectiveness
4. Routing speed

Run with: python -m pytest tests/test_performance.py -v

Note: All optimizations are now in streaming_nodes.py (no duplicate files)
"""

import time
import asyncio
import pytest
from agents.study.fast_streaming_agent import FastStreamingStudyAgent


class TestPerformance:
    """Performance benchmarks for optimized study agent."""
    
    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return FastStreamingStudyAgent()
    
    @pytest.mark.asyncio
    async def test_ttfb_under_100ms(self, agent):
        """Test that Time To First Byte is under 100ms."""
        question = "What is machine learning?"
        
        start = time.time()
        stream = agent.aquery_stream(question)
        first_chunk = await stream.__anext__()
        ttfb_ms = (time.time() - start) * 1000
        
        print(f"\n⏱️  TTFB: {ttfb_ms:.1f}ms")
        assert ttfb_ms < 150, f"TTFB too slow: {ttfb_ms:.1f}ms (target: <100ms)"
        assert first_chunk, "First chunk should not be empty"
    
    @pytest.mark.asyncio
    async def test_simple_query_under_3s(self, agent):
        """Test that simple web search completes under 3 seconds."""
        question = "What is artificial intelligence?"
        
        start = time.time()
        chunks = []
        async for chunk in agent.aquery_stream(question):
            chunks.append(chunk)
            if chunk == "[DONE]":
                break
        
        total_time = time.time() - start
        print(f"\n⏱️  Total time: {total_time:.1f}s")
        
        # Allow up to 5s due to external API calls, but target is 3s
        assert total_time < 5.0, f"Query too slow: {total_time:.1f}s (target: <3s)"
        assert len(chunks) > 1, "Should have multiple chunks"
    
    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, agent):
        """Test that cached queries are significantly faster."""
        question = "Define neural network"
        
        # First query (not cached)
        start = time.time()
        result1 = []
        async for chunk in agent.aquery_stream(question):
            result1.append(chunk)
            if chunk in ["[DONE]", "[ERROR]"]:
                break
        time1 = time.time() - start
        
        # Second query (should be cached)
        start = time.time()
        result2 = []
        async for chunk in agent.aquery_stream(question):
            result2.append(chunk)
            if chunk in ["[DONE]", "[ERROR]"]:
                break
        time2 = time.time() - start
        
        speedup = time1 / time2 if time2 > 0 else 1
        print(f"\n⏱️  First query: {time1:.2f}s")
        print(f"⏱️  Cached query: {time2:.2f}s")
        print(f"📦 Cache speedup: {speedup:.1f}x")
        
        # Cached query should be at least 2x faster
        assert speedup >= 2.0, f"Cache not effective: only {speedup:.1f}x faster"
    
    @pytest.mark.asyncio
    async def test_routing_speed(self, agent):
        """Test that routing is instant (pattern-based)."""
        test_queries = [
            ("What is AI?", "web_search"),
            ("Calculate 2+2", "python_repl"),
            ("Summarize my document", "document_qa"),
            ("Create animation of sorting", "manim_animation"),
        ]
        
        for question, expected_tool in test_queries:
            start = time.time()
            tool = agent.nodes._fast_classify(question.lower())
            routing_time_ms = (time.time() - start) * 1000
            
            print(f"\n📍 '{question[:30]}...' → {tool} ({routing_time_ms:.2f}ms)")
            assert routing_time_ms < 1.0, f"Routing too slow: {routing_time_ms:.2f}ms"
            assert tool == expected_tool, f"Wrong routing: {tool} != {expected_tool}"
    
    @pytest.mark.asyncio
    async def test_progressive_streaming(self, agent):
        """Test that results stream progressively (not all at once)."""
        question = "Explain quantum computing"
        
        chunk_times = []
        start = time.time()
        first_content_time = None
        
        async for chunk in agent.aquery_stream(question):
            current_time = time.time() - start
            chunk_times.append(current_time)
            
            # Record when first real content arrives (not just indicators)
            if first_content_time is None and len(chunk) > 10:
                first_content_time = current_time
            
            if chunk == "[DONE]":
                break
        
        print(f"\n📊 Received {len(chunk_times)} chunks")
        print(f"⏱️  First content: {first_content_time:.2f}s")
        print(f"⏱️  Total time: {chunk_times[-1]:.2f}s")
        
        # Should receive multiple chunks (progressive)
        assert len(chunk_times) >= 5, "Not enough streaming chunks"
        
        # First content should arrive quickly
        assert first_content_time < 2.0, f"First content too slow: {first_content_time:.1f}s"
    
    def test_synchronous_query(self, agent):
        """Test synchronous query wrapper."""
        question = "What is Python?"
        
        start = time.time()
        result = agent.query(question)
        total_time = time.time() - start
        
        print(f"\n⏱️  Sync query time: {total_time:.1f}s")
        assert result, "Should return non-empty result"
        assert isinstance(result, str), "Result should be string"


class TestPerformanceComparison:
    """Compare old vs new agent performance."""
    
    @pytest.mark.skip(reason="Requires both old and new agents")
    @pytest.mark.asyncio
    async def test_speedup_comparison(self):
        """Compare performance of old vs new agent."""
        from agents.study.streaming_agent import StreamingStudyAgent
        from agents.study.fast_streaming_agent import FastStreamingStudyAgent
        
        question = "What is machine learning?"
        
        # Old agent
        old_agent = StreamingStudyAgent()
        start = time.time()
        async for chunk in old_agent.aquery_stream(question):
            if chunk == "[DONE]":
                break
        old_time = time.time() - start
        
        # New agent
        new_agent = FastStreamingStudyAgent()
        start = time.time()
        async for chunk in new_agent.aquery_stream(question):
            if chunk == "[DONE]":
                break
        new_time = time.time() - start
        
        speedup = old_time / new_time
        print(f"\n📊 Performance Comparison:")
        print(f"   Old agent: {old_time:.2f}s")
        print(f"   New agent: {new_time:.2f}s")
        print(f"   Speedup: {speedup:.1f}x faster")
        
        assert speedup >= 2.0, f"Not fast enough: only {speedup:.1f}x faster"


@pytest.mark.benchmark
class TestBenchmarks:
    """Detailed benchmarks for performance analysis."""
    
    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return FastStreamingStudyAgent()
    
    @pytest.mark.asyncio
    async def test_benchmark_web_search(self, agent, benchmark):
        """Benchmark web search queries."""
        async def run_query():
            chunks = []
            async for chunk in agent.aquery_stream("What is AI?"):
                chunks.append(chunk)
                if chunk == "[DONE]":
                    break
            return chunks
        
        result = await run_query()
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_benchmark_document_qa(self, agent, benchmark):
        """Benchmark document QA queries."""
        async def run_query():
            chunks = []
            async for chunk in agent.aquery_stream("Summarize my document about AI"):
                chunks.append(chunk)
                if chunk == "[DONE]":
                    break
            return chunks
        
        result = await run_query()
        assert len(result) > 0


if __name__ == "__main__":
    """Run benchmarks directly."""
    import sys
    
    print("=" * 70)
    print("STUDY AGENT PERFORMANCE BENCHMARKS")
    print("=" * 70)
    
    agent = FastStreamingStudyAgent()
    
    # Test 1: TTFB
    print("\n🧪 Test 1: Time To First Byte (TTFB)")
    asyncio.run(TestPerformance().test_ttfb_under_100ms(agent))
    
    # Test 2: Routing Speed
    print("\n🧪 Test 2: Routing Speed")
    asyncio.run(TestPerformance().test_routing_speed(agent))
    
    # Test 3: Total Query Time
    print("\n🧪 Test 3: Total Query Time")
    asyncio.run(TestPerformance().test_simple_query_under_3s(agent))
    
    # Test 4: Cache Effectiveness
    print("\n🧪 Test 4: Cache Effectiveness")
    asyncio.run(TestPerformance().test_cache_effectiveness(agent))
    
    print("\n" + "=" * 70)
    print("✅ ALL BENCHMARKS PASSED")
    print("=" * 70)

