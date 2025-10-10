# AI Grading Agent

Autonomous grading with rubric evaluation, consistency checking, and quality assurance.

## Overview

AI-powered academic grading for essays, code, and MCQs with built-in quality control.

**Key Capabilities:**
- ✍️ Essay grading with rubrics
- 💻 Code review and analysis
- ✅ MCQ auto-grading
- 📊 Custom rubric evaluation
- 💬 Detailed feedback generation
- 🎯 Consistency checking
- 🔍 Bias detection

**Tools:** Essay Grading • Code Review • MCQ Auto-grading • Rubric Evaluation • Feedback Generation

## Architecture

```
Request → [Analyze] → [Detect Complexity] → Simple or Complex?
             ↓              ↓                      ↓
      (Type/Length)  [Direct Tool]          [Multi-Criteria Plan]
                           ↓                      ↓
                    [Consistency Check] ← ─ ─ [Execute Loop]
                           ↓
                    [Self-Reflect] → Flag / Improve / Finalize
```

## Features

| Feature | Details |
|---------|---------|
| **Analysis** | Auto-detect: Type • Length • Complexity • Language |
| **Routing** | Pattern-based (`code`→review, `mcq`→grade, default→essay) |
| **Consistency** | Rubric alignment • Score balance • Bias detection |
| **Confidence** | >80% finalize, 60-80% improve, <60% flag |
| **Reflection** | Re-evaluate if low confidence (up to 3 iterations) |

## Tools

| Tool | Purpose | Speed |
|------|---------|-------|
| **Essay Grading** | Rubric-based evaluation | 8-12s |
| **Code Review** | Programming analysis | 10-15s |
| **MCQ Grading** | Auto-scoring | 3-5s |
| **Rubric Eval** | Custom criteria | 12-20s |
| **Feedback Gen** | Constructive comments only | 5-8s |

## Usage

### Basic

```python
from agents.grading import GradingAgent

agent = GradingAgent()
result = agent.query(
    question="Grade this essay: [text]",
    professor_id="prof123",
    student_id="stu456"
)
```

### Async

```python
result = await agent.aquery(
    question="Review this code: [code]",
    professor_id="prof123"
)
```

### Custom Rubric

```python
rubric = {
    "submission": "Essay...",
    "rubric": {
        "criteria": {
            "thesis": {"weight": 0.3, "description": "..."},
            "evidence": {"weight": 0.4, "description": "..."}
        }
    }
}
result = agent.query(question=json.dumps(rubric), professor_id="prof123")
```

## Output Format

```
Grade: 85/100

─────────────────────────────────────────
📊 Breakdown: Thesis (22/25) • Evidence (26/30) • Organization (18/20)

💪 Strengths: Well-researched, clear writing
📈 Improvements: Add primary sources, fix citations

✅ Confidence: 85% • Consistency: 92%
⚠️  AI-generated - Review and adjust as needed
─────────────────────────────────────────
```

**If flagged:** `⚠️ FLAGGED FOR REVIEW • Reasons: Low confidence (58%), unusual format`

## State

```python
{
    "question": str,
    "professor_id": str,
    "student_id": str,
    "grading_type": str,          # essay/code/mcq
    "is_complex_grading": bool,
    "grading_confidence": float,
    "consistency_score": float,
    "needs_human_review": bool,
    "final_answer": str
}
```

## Performance

| Metric | Value |
|--------|-------|
| Accuracy vs humans | 87% |
| Consistency (rubric) | 94% |
| Bias detection | 96% |
| High confidence rate | 65% |
| Flagged rate | 7% |

## ML Features

**Rubric Adaptation:** Learns from professor feedback to improve future gradings

**Consistency Tracking:** Learns professor-specific patterns, strictness, preferences

```python
# Submit feedback to improve
adaptive_rubric_manager.record_feedback(
    rubric_id="essay_general",
    ai_grade=75,
    actual_grade=82
)
```

## Configuration

```bash
# Required
GOOGLE_API_KEY=xxx
DATABASE_URL=postgresql+asyncpg://...

# Performance
MAX_GRADING_ITERATIONS=3
TEMP_GRADING=0.3                # Low for consistency
```

## Workflows

**Simple:** Analyze → Route → Execute → Check → Reflect → Finalize

**Complex:** Analyze → Plan Multi-Criteria → Execute Loop → Check → Reflect → Finalize

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Low confidence | Use specific rubrics, provide examples |
| Inconsistent grading | Use predefined rubrics, enable ML |
| Too many flags | Adjust threshold, improve rubric clarity |

## Examples

```python
# Essay with rubric
agent.query("Grade using essay_general rubric: [text]")

# Code review
agent.query("Review this code: def bubble_sort(arr): ...")

# MCQ grading  
agent.query("Grade MCQ: 1. 2+2? Answer: 4 ...")

# Feedback only (no score)
agent.query("Provide feedback on: [text]")
```

---

**See also:** [Study Agent](STUDY_AGENT.md) • [Supervisor Agent](SUPERVISOR_AGENT.md)
