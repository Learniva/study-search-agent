# Streaming Test Guide

A comprehensive guide for testing the sophisticated streaming implementation in the Study Search Agent.

---

## 🎯 Overview

The system implements **true token-by-token streaming** with visual indicators showing the workflow progress in real-time. This guide helps you test and verify all streaming features.

---

## 🌊 Streaming Architecture Components

### 1. Streaming Indicators
The system uses 8 distinct indicators to show workflow stages:

| Indicator | Symbol | When It Appears | Meaning |
|-----------|--------|-----------------|---------|
| `THINKING` | 🧠 | Task analysis | Analyzing the query complexity |
| `ANALYZING` | 🧠 | Processing data | Analyzing search results or data |
| `PLANNING` | 📋 | Complex tasks | Creating multi-step execution plan |
| `SEARCHING` | 🔍 | Web search | Searching the internet for information |
| `EXECUTING` | ⚙️ | Tool execution | Running tools (REPL, Manim, etc.) |
| `SYNTHESIZING` | ✍️ | Multi-step | Combining results from multiple steps |
| `GENERATING` | 📝 | Content creation | Generating final response |
| `COMPLETE` | ✅ | End of stream | Stream finished successfully |

### 2. Streaming Modes

**Simple Mode** (Fast queries):
```
SEARCHING → ANALYZING → GENERATING → COMPLETE
```

**Complex Mode** (Multi-step queries):
```
THINKING → PLANNING → SEARCHING → EXECUTING → SYNTHESIZING → GENERATING → COMPLETE
```

---

## 🧪 Testing Streaming Features

### Test 1: Basic Streaming (Simple Query)

**Query**:
```
What is artificial intelligence?
```

**Expected Console Output**:
```
⚡ Pattern-based routing: STUDY (no LLM call)
⚡ Pattern-based intent: STUDY (no LLM call)
⚡ Pattern-based routing: Web_Search (no LLM call)
🔍 Searching with Google Custom Search (Primary)...
🔍 Falling back to Tavily Search...
✅ Tavily search successful (fallback)
```

**Expected Streaming Behavior**:
- Text appears **progressively** (not all at once)
- Response builds token-by-token
- Smooth, continuous flow
- Sources appear at the end

**Expected Streaming Indicators**:
1. 🔍 `SEARCHING` - Web search initiated
2. 🧠 `ANALYZING` - Processing results
3. 📝 `GENERATING` - Creating response
4. ✅ `COMPLETE` - Stream finished

**Verification**:
- [ ] Response appeared gradually
- [ ] Saw streaming indicators in console
- [ ] Sources included at bottom
- [ ] No errors or interruptions

---

### Test 2: Code Generation Streaming

**Query**:
```
How do I implement a simple neural network in Python? Provide a basic code example.
```

**Expected Streaming Behavior**:
- Explanation streams first
- Code blocks appear progressively
- Comments added in real-time
- Code formatted with syntax highlighting
- Sources appear last

**Expected Streaming Indicators**:
1. 🔍 `SEARCHING` - Finding tutorials/resources
2. 🧠 `ANALYZING` - Understanding requirements
3. 💻 `GENERATING` - Generating code
4. ✅ `COMPLETE` - Stream finished

**What to Watch For**:
- Code appears inside the stream (not delayed)
- Proper ```python code blocks
- Comments in the code
- Complete, runnable implementation

**Verification**:
- [ ] Code generated (not just described)
- [ ] Code appeared progressively
- [ ] Proper markdown formatting
- [ ] Sources cited

---

### Test 3: Multi-Step Complex Query

**Query**:
```
Explain the difference between supervised, unsupervised, and reinforcement learning. Provide 2 examples for each and explain when to use each approach.
```

**Expected Streaming Behavior**:
- Long-form progressive delivery
- Multiple sections appearing gradually
- Examples streaming as they're generated
- Structured organization
- Multiple source citations

**Expected Streaming Indicators**:
1. 🧠 `THINKING` - Analyzing task complexity
2. 📋 `PLANNING` - Creating multi-step plan
3. 🔍 `SEARCHING` - Web search (may appear multiple times)
4. 🧠 `ANALYZING` - Processing each search
5. ⚙️ `EXECUTING` - Running plan steps
6. ✍️ `SYNTHESIZING` - Combining all results
7. 📝 `GENERATING` - Final answer generation
8. ✅ `COMPLETE` - Stream finished

**What to Watch For**:
- Multiple workflow stages visible
- Plan steps executed in order
- Synthesis of multiple searches
- Coherent final answer

**Verification**:
- [ ] Multiple streaming indicators appeared
- [ ] Response built section-by-section
- [ ] All 3 types explained
- [ ] 6 total examples (2 each)
- [ ] Use cases explained
- [ ] Multiple sources cited

---

### Test 4: Educational Content Streaming

**Query**:
```
Create a lesson plan on Linear Regression with 15 flashcards
```

**Expected Streaming Behavior**:
- Lesson plan structure appears first
- Objectives stream progressively
- Lesson outline builds section-by-section
- Flashcards appear one-by-one
- References at the end

**Expected Streaming Indicators**:
1. 🔍 `SEARCHING` - Finding educational resources
2. 🔍 `SEARCHING` - Additional searches for comprehensive content
3. 🧠 `ANALYZING` - Processing educational materials
4. ✍️ `SYNTHESIZING` - Combining multiple sources
5. 📝 `GENERATING` - Creating lesson plan
6. ✅ `COMPLETE` - Stream finished

**Verification**:
- [ ] Lesson plan fully structured
- [ ] 15 flashcards present
- [ ] Progressive appearance
- [ ] References section included
- [ ] Educational quality sources

---

### Test 5: Maximum Complexity Streaming

**Query**:
```
Create a comprehensive guide on building a neural network from scratch: explain the mathematical foundations, provide complete Python implementation with comments, describe how to visualize the training process, and include 5 challenging practice exercises with solutions
```

**Expected Streaming Behavior**:
- **Longest stream** - multiple minutes
- Multiple distinct sections
- Math formulas appear
- Code blocks stream progressively
- Visualization descriptions
- Exercise generation
- Solutions appear last
- Extensive source citations

**Expected Streaming Indicators**:
1. 🧠 `THINKING` - Complex task analysis
2. 📋 `PLANNING` - Multi-part plan creation
3. 🔍 `SEARCHING` - Multiple web searches
4. 🔍 `SEARCHING` - Additional research
5. 🧠 `ANALYZING` - Processing all results
6. ⚙️ `EXECUTING` - Plan execution
7. 💻 `GENERATING` - Code generation
8. ✍️ `SYNTHESIZING` - Combining everything
9. 📝 `GENERATING` - Final assembly
10. ✅ `COMPLETE` - Stream finished

**What to Watch For**:
- Very long progressive stream
- Multiple workflow stages
- Complex content organization
- Code, math, exercises all present
- High-quality synthesis

**Verification**:
- [ ] All parts requested are present
- [ ] Math explained clearly
- [ ] Complete code implementation
- [ ] Visualization methods described
- [ ] 5 exercises with solutions
- [ ] Multiple authoritative sources
- [ ] Streaming was smooth throughout

---

## 🔍 Console Monitoring

### What to Look For in Console

**Good Streaming Output**:
```
⚡ Pattern-based routing: STUDY (no LLM call)
🔍 Searching with Google Custom Search (Primary)...
🔍 Falling back to Tavily Search...
✅ Tavily search successful (fallback)
🔵 [THINKING] Analyzing query complexity...
🔵 [SEARCHING] Finding relevant resources...
🔵 [ANALYZING] Processing search results...
🔵 [GENERATING] Creating comprehensive answer...
✅ Stream complete
```

**Indicators of Issues**:
```
❌ No streaming indicators
❌ All text appears at once
❌ [ERROR] markers
❌ No Sources section
❌ Incomplete responses
```

---

## 📊 Streaming Performance Metrics

### Response Time Expectations

| Query Type | First Token | Full Response | Indicators |
|------------|-------------|---------------|------------|
| Simple (Math) | < 1 sec | 1-2 sec | 1-2 |
| Simple Search | 1-2 sec | 3-5 sec | 2-3 |
| Code Generation | 2-3 sec | 5-10 sec | 3-4 |
| Educational Content | 2-4 sec | 10-20 sec | 4-5 |
| Complex Multi-Step | 3-5 sec | 20-60 sec | 6-8 |

### Quality Metrics

**Excellent Streaming**:
- ✅ Smooth, continuous flow
- ✅ No buffering or pauses
- ✅ All indicators appear
- ✅ Sources included
- ✅ Complete answers

**Needs Improvement**:
- ⚠️ Choppy delivery
- ⚠️ Missing indicators
- ⚠️ No sources
- ⚠️ Incomplete responses

---

## 🎮 Interactive Testing Script

### CLI Testing
```bash
cd /Users/maniko/study-search-agent
source study_agent/bin/activate
python main.py --role professor
```

Then run queries from simplest to most complex:

**Level 1: Warm-up**
```
What is 2+2?
```

**Level 2: Basic Streaming**
```
What is machine learning?
```

**Level 3: Code Streaming**
```
How to implement binary search in Python?
```

**Level 4: Complex Content**
```
Create a lesson plan on neural networks with 10 flashcards
```

**Level 5: Maximum Complexity**
```
Explain deep learning, provide code examples, and create practice exercises
```

### API Testing (Streaming Endpoint)

```bash
# Test streaming via API
curl -X POST "http://localhost:8000/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is quantum computing?", "user_role": "student"}' \
  --no-buffer
```

**Expected**: Server-Sent Events stream with progressive response

---

## ✅ Comprehensive Streaming Checklist

### Before Testing
- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] Database running (if using persistence)
- [ ] Environment variables set

### During Testing
- [ ] Console visible for indicators
- [ ] Network connection stable
- [ ] Sufficient API quota (Tavily)

### For Each Query
- [ ] Query submitted successfully
- [ ] Streaming indicators appear in console
- [ ] Response builds progressively
- [ ] No errors in stream
- [ ] Stream completes with COMPLETE indicator
- [ ] Sources included (for web search queries)
- [ ] Code generated (for code queries)
- [ ] All requested parts present

### After Testing
- [ ] All test queries passed
- [ ] No crashes or errors
- [ ] Streaming performance acceptable
- [ ] Source quality high
- [ ] Code examples work

---

## 🐛 Troubleshooting

### Issue: No Streaming (All Text at Once)

**Possible Causes**:
- Streaming not enabled in LLM
- Using `query()` instead of `aquery_stream()`
- Buffering in terminal/client

**Solution**:
- Verify `streaming=True` in LLM initialization
- Use `aquery_stream()` method
- Check client buffering settings

### Issue: Missing Streaming Indicators

**Possible Causes**:
- Console output not captured
- Indicators filtered out
- Error in streaming wrapper

**Solution**:
- Check console output
- Verify StreamingState implementation
- Review streaming wrapper code

### Issue: Incomplete Responses

**Possible Causes**:
- Stream interrupted
- Error in synthesis
- Timeout

**Solution**:
- Check error logs
- Verify network stability
- Increase timeout settings

### Issue: No Sources in Response

**Possible Causes**:
- Web search not triggered
- Synthesis prompt not including sources
- Source extraction failed

**Solution**:
- Verify web search was called
- Check synthesis prompt includes source instruction
- Review search result formatting

---

## 📈 Advanced Testing

### Stress Testing
Run 10 complex queries in succession:
```
for i in {1..10}; do
  echo "Test $i: Complex query"
  # Run query
done
```

### Concurrent Streaming (API)
Test multiple simultaneous streams:
```bash
# Terminal 1
curl -X POST "http://localhost:8000/query/stream" ...

# Terminal 2
curl -X POST "http://localhost:8000/query/stream" ...

# Terminal 3
curl -X POST "http://localhost:8000/query/stream" ...
```

### Long-Running Streams
Test with extremely complex queries:
```
Create a complete 10-week curriculum for learning machine learning from scratch, including weekly lesson plans, 100 flashcards, code exercises, and project ideas
```

---

## 📚 Reference

### Streaming Flow Diagram
```
User Query
    ↓
Supervisor Agent (aquery_stream)
    ↓
Study Agent (aquery_stream)
    ↓
[THINKING] → Complexity analysis
    ↓
[PLANNING] → Multi-step plan (if complex)
    ↓
[SEARCHING] → Web search tool
    ↓
[ANALYZING] → Process results
    ↓
[SYNTHESIZING] → Combine multiple steps
    ↓
[GENERATING] → Token-by-token final answer
    ↓
[COMPLETE] → Stream ends
```

### Key Files
- `utils/patterns/base_agent.py` - Core streaming implementation
- `utils/patterns/streaming.py` - StreamingState, StreamingStateGraph
- `agents/study/core.py` - Study agent with streaming
- `agents/supervisor/core.py` - Supervisor routing to streaming
- `api/routers/query.py` - API streaming endpoint

---

**Last Updated**: October 14, 2025  
**Version**: 2.0 - Sophisticated Streaming Implementation
