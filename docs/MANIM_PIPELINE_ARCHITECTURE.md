# Manim Animation - Multi-Stage Pipeline

Educational animation generation using a 4-stage pipeline for better LLM reasoning and output quality.

## Pipeline Overview

```
User Request → RAG Context → Planning → Code Generation → Execution → Video
```

## Architecture

```
Stage 0: RAG Context
   ↓ Source material from documents
Stage 1: Planning Agent (Scene Designer)
   ↓ Structured JSON plan
Stage 2: Code Generation (Manim Python Coder)
   ↓ Executable Python code
Stage 3: Execution (render_manim_video)
   ↓ MP4 video file
```

## Stage Details

### Stage 0: RAG Context

**Purpose:** Extract relevant source material from documents

**Input:** Topic ("Pythagorean theorem")  
**Output:** Text chunks from documents  
**Example:**
```
[ml_notes.pdf - Page 5]
The Pythagorean theorem states a² + b² = c²...
```

### Stage 1: Planning Agent

**Persona:** "Scene Designer"  
**Purpose:** Convert text to structured animation plan

**Input:** RAG context + topic  
**Output:** JSON plan

```json
{
  "main_object": "Right triangle with sides a, b, c",
  "key_steps": [
    "Step 1: Draw right triangle",
    "Step 2: Label sides a, b, c",
    "Step 3: Display formula a² + b² = c²",
    "Step 4: Show visual squares on sides",
    "Step 5: Animate proof"
  ],
  "text_to_display": [
    "Pythagorean Theorem",
    "a² + b² = c²"
  ]
}
```

### Stage 2: Code Generation

**Persona:** "Manim Python Coder"  
**Purpose:** Convert plan to executable code

**Input:** Structured JSON plan  
**Output:** Python Manim script

```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Step 1: Draw right triangle
        triangle = Polygon([0,0,0], [3,0,0], [3,4,0])
        self.play(Create(triangle))
        
        # Step 2: Label sides
        label_a = MathTex("a").next_to(triangle, DOWN)
        self.play(Write(label_a))
        
        # ... Steps 3-5
```

### Stage 3: Execution

**Tool:** `render_manim_video`  
**Purpose:** Execute code and produce video

**Process:**
1. Write code to temp `.py` file
2. Run `subprocess.run(['manim', '-qm', file, 'ConceptAnimation'])`
3. Capture output/errors
4. Locate generated `.mp4`

**Output (Tool Artifact):**
```json
{
  "content": "Animation successfully rendered",
  "artifact": "/path/to/pythagorean_theorem.mp4"
}
```

**Duration:** 30-60 seconds

## Benefits

| Benefit | Description |
|---------|-------------|
| **Better Reasoning** | Each stage has focused task with clear persona |
| **Less Ambiguity** | Structured JSON plan eliminates vague descriptions |
| **Easy Debugging** | Inspect plan before code generation, pinpoint issues |
| **Higher Quality** | Focused LLM attention per stage = consistent results |
| **Extensible** | Add validation, swap LLMs, human review between stages |

## Single-Stage vs Multi-Stage

**Single-Stage (Old):**
```
User → LLM("Create Manim code") → Code → Execute
```
- LLM handles everything at once
- Inconsistent output
- Hard to debug

**Multi-Stage (New):**
```
User → RAG → Planning → Code Gen → Execute
```
- One job per stage
- Structured intermediate format
- Clear personas guide behavior

## Implementation

```python
# User calls the tool
agent.query("animate the Pythagorean theorem")

# Internal pipeline:
context = rag_context("Pythagorean theorem")
plan = planning_agent(topic, context)
code = code_gen_agent(plan)
result = execute_manim(code)
# → {"content": "...", "artifact": "/path/to/video.mp4"}
```

## Console Output

```
============================================================
🎬 Multi-Stage Animation Pipeline: 'Pythagorean theorem'
============================================================

📚 STAGE 0: RAG - Retrieving source material...
✓ Retrieved context (456 chars)

📋 STAGE 1: Planning - Creating structured plan...
✓ Plan: 5 steps, 3 text elements

🐍 STAGE 2: Code Gen - Converting to Python...
✓ Generated 1847 chars of code

============================================================
✅ Pipeline Complete!
============================================================

🎥 Executing Manim (30-60s)...
✓ Video: /path/to/pythagorean_theorem.mp4
```

## Future Enhancements

- **Plan validation** between Stage 1 and 2
- **Code review** with static analysis before execution
- **Human-in-the-loop** plan review/editing
- **Plan library** caching for common topics
- **Specialized LLMs** per stage (code-optimized for Stage 2)

---

**Multi-stage architecture ensures high-quality, precise animations every time.**
