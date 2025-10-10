# Study & Search Agent

AI-powered study assistant with intelligent tool routing, multi-step planning and autonomous execution.

## Overview

Autonomous learning companion for research, Q&A, code execution, and educational content creation.

**Tools:** Document Q&A • Web Search • Python REPL • Manim Animation

## Architecture

```
Query → [Complexity Detection] → Simple or Complex?
           ↓                         ↓
    [Direct Routing]          [Multi-Step Planning]
           ↓                         ↓
    [Execute Tool]            [Execute Plan (Loop)]
           ↓                         ↓
    [Self-Reflect] ← ─ ─ ─ ─ [Synthesize Results]
           ↓
    Retry / Clarify / Finish
```

## Features

### Tool Routing

**Pattern-based (80% of queries, <50ms):**
```python
"document/uploaded" → Document_QA
"calculate/code"    → Python_REPL
"animation/visual"  → Manim
default             → Web_Search
```

**LLM-based:** Fallback for ambiguous queries

### Complexity Detection

| Type | Triggers | Handling |
|------|----------|----------|
| Simple | Single question, one domain | Direct tool execution |
| Complex | Multi-part, multiple domains | Multi-step planning |

### Fallback Chain

```
Document QA → [Not Found] → Web Search → [Success]
```

### Self-Reflection

Post-execution quality check:
- Completeness, accuracy, clarity
- **<70% quality** → Retry
- **Needs info** → Clarify
- **>70% quality** → Finish

## Tools

| Tool | Purpose | Use Case | Speed |
|------|---------|----------|-------|
| **Document QA** | RAG on uploads | "Summarize chapter 5" | 1-3s |
| **Web Search** | Internet research | "Latest on AI" | 2-5s |
| **Python REPL** | Code execution | "Calculate 15% of 250" | 0.5-2s |
| **Manim** | Educational videos | "Animate sorting" | 10-30s |

## Usage

### Basic

```python
from agents.study import StudySearchAgent

agent = StudySearchAgent()
result = agent.query("Explain photosynthesis", thread_id="s1")
```

### With Context

```python
agent.query("Explain neural networks", thread_id="study")
agent.query("Generate 10 MCQs", thread_id="study")  # Remembers context
```

### Async

```python
result = await agent.aquery("Research quantum computing")
```

## Workflows

### Simple Path
```
Route → Execute Tool → Check → Retry (if needed) → Format → Reflect → Done
```

### Complex Path
```
Detect → Plan Task → Execute Loop → Synthesize → Reflect → Done
```

**Example Complex:**
```
"Explain X, generate MCQs, create study guide"
→ Plan: [Search, Generate, Create]
→ Execute each step
→ Combine results
```

## State

```python
{
    "question": str,
    "is_complex_task": bool,
    "task_plan": List,           # Multi-step plan
    "tool_used": str,
    "tool_result": str,
    "document_qa_failed": bool,  # Triggers fallback
    "response_confidence": float,
    "needs_retry": bool,
    "final_answer": str
}
```

## Performance

| Metric | Value |
|--------|-------|
| Routing (pattern) | <50ms (80% queries) |
| Routing (LLM) | 1-2s (20% queries) |
| Answer accuracy | 92% (with reflection) |
| Fallback success | 95% |
| Complex completion | 88% |

## Configuration

```bash
# Required
GOOGLE_API_KEY=xxx

# Search
TAVILY_API_KEY=xxx              # Optional
SEARCH_MAX_RESULTS=5

# Documents
DOCUMENTS_DIR=documents
CHUNK_SIZE=1000

# Performance
MAX_AGENT_ITERATIONS=5
TEMP_STUDY=0.7
```

## Advanced Features

**Memory:** Thread-based conversation context (PostgreSQL checkpointing)

**Caching:** Results cached for 300s (configurable)

**Follow-ups:** Auto-suggested next questions

## Examples

```python
# MCQ Generation
agent.query("Generate 10 MCQs about neural networks")

# Study Guide
agent.query("Create study guide for photosynthesis with diagrams")

# Code Execution
agent.query("Calculate compound interest: $1000 at 5% for 10 years")

# Animation
agent.query("Create animation showing bubble sort")
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Document not found | Check DOCUMENTS_DIR, format (PDF/DOCX), auto-fallback to web |
| Code execution fails | Verify syntax, check sandboxing, simplify code |
| Slow responses | Enable caching, reduce MAX_ITERATIONS, use simpler queries |

---

**See also:** [Grading Agent](GRADING_AGENT.md) • [Supervisor Agent](SUPERVISOR_AGENT.md)
