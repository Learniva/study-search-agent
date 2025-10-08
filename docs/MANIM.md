# Manim Animation System

Educational mathematical and conceptual animations using [Manim](https://www.manim.community/) (3Blue1Brown's engine).

## Overview

**Purpose:** Generate animated educational videos from study materials  
**Engine:** Manim Community Edition  
**Pipeline:** 4-stage multi-agent workflow for quality output

## Installation

```bash
# Manim
pip install manim

# LaTeX (optional, for math rendering)
brew install mactex-no-gui-doc        # macOS
sudo apt-get install texlive-full     # Linux

# FFmpeg (required)
brew install ffmpeg                   # macOS
sudo apt-get install ffmpeg           # Linux

# Verify
manim --version
```

## Usage

### Basic Commands

```bash
# Generate and render
"animate the Pythagorean theorem"
"create animation for bubble sort"
"visualize derivatives"

# Code only (no rendering)
"generate code only for animate binary search"

# With documents
"animate the main concept from my notes"
```

### Command Patterns

| Pattern | Behavior |
|---------|----------|
| `animate [topic]` | Generate & render |
| `create animation for [topic]` | Generate & render |
| `visualize [concept]` | Generate & render |
| `generate code only [topic]` | Code only (no render) |

### Quality Settings

```bash
manim -ql file.py ConceptAnimation  # Low (480p, fast)
manim -qm file.py ConceptAnimation  # Medium (720p, default)
manim -qh file.py ConceptAnimation  # High (1080p)
manim -qp file.py ConceptAnimation  # Production (1440p)
```

## Architecture

### Multi-Stage Pipeline

```
User Request → RAG → Planning → Code Gen → Execution → Video
```

**Stages:**

**Stage 0: RAG Context**  
Extract relevant material from documents
- Input: Topic ("Pythagorean theorem")
- Output: Text chunks from docs
- Duration: <1s

**Stage 1: Planning**  
Create structured animation plan (Scene Designer persona)
- Input: RAG context + topic
- Output: JSON plan (scenes, steps, text)
- Duration: 5-10s

**Stage 2: Code Generation**  
Convert plan to Manim code (Manim Python Coder persona)
- Input: Structured JSON plan
- Output: Executable Python script
- Duration: 5-10s

**Stage 3: Execution**  
Render video with optional voiceover
- Input: Python script
- Output: MP4 video file
- Duration: 30-60s

### Example Flow

```json
// Stage 1 Output (Planning)
{
  "main_object": "Right triangle with sides a, b, c",
  "key_steps": [
    "Draw right triangle",
    "Label sides a, b, c",
    "Display formula a² + b² = c²",
    "Show visual squares on sides",
    "Animate proof"
  ],
  "text_to_display": ["Pythagorean Theorem", "a² + b² = c²"]
}
```

```python
# Stage 2 Output (Code Generation)
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        triangle = Polygon([0,0,0], [3,0,0], [3,4,0])
        self.play(Create(triangle))
        label_a = MathTex("a").next_to(triangle, DOWN)
        self.play(Write(label_a))
        # ... rest of animation
```

```json
// Stage 3 Output (Execution)
{
  "content": "Animation successfully rendered",
  "artifact": "/path/to/pythagorean_theorem.mp4"
}
```

### Benefits

| Benefit | Description |
|---------|-------------|
| **Better Reasoning** | Focused task per stage with clear persona |
| **Less Ambiguity** | Structured JSON eliminates vague descriptions |
| **Easy Debugging** | Inspect plan before code, pinpoint issues |
| **Higher Quality** | Focused LLM attention = consistent output |
| **Extensible** | Add validation, swap LLMs, human review |

### Console Output

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

## Examples

### Mathematics
- "animate the unit circle"
- "visualize Taylor series"
- "show quadratic formula derivation"

### Algorithms
- "animate bubble sort with 5 elements"
- "visualize binary search tree"
- "show quicksort partitioning"

### Physics
- "animate projectile motion"
- "visualize wave interference"
- "show simple harmonic motion"

### ML/AI
- "animate gradient descent"
- "visualize neural network layers"
- "show backpropagation"

## Advanced Usage

### Programmatic Access

```python
from tools.manim_animation import get_manim_tool

tool = get_manim_tool()
result = tool.func("animate factorial recursion")
```

### Custom Workflow

```bash
# 1. Generate code only
"generate code only for animate graph traversal"

# 2. Edit generated code

# 3. Render manually
manim -qh my_animation.py ConceptAnimation
```

### Batch Generation

```python
from agent import StudySearchAgent

agent = StudySearchAgent()
topics = ["quadratic formula", "dijkstra's algorithm"]

for topic in topics:
    agent.query(f"animate {topic}")
```

### Integration

```bash
# With Document Q&A
"Generate 5 MCQs about neural networks and animate backpropagation"

# With Web Search
"What is gradient descent? Then animate it."
```

## File Structure

```
animations/
├── videos/    # Rendered MP4 files
├── images/    # Intermediate images
└── Tex/       # LaTeX temporary files
```

**Output:** `animations/videos/[quality]/[name]_animation.mp4`

## Configuration

### Voice-over

```bash
# .env
ELEVEN_API_KEY=xxx  # High-quality TTS (optional)
```

**Fallback:** gTTS (free) if no API key

### Rendering

Default: 720p medium quality  
Configurable via command patterns or manual rendering

## Performance

| Quality | Resolution | Time | Size |
|---------|-----------|------|------|
| Low | 480p | 10-20s | ~1 MB |
| Medium | 720p | 20-40s | ~3 MB |
| High | 1080p | 40-80s | ~10 MB |
| Production | 1440p | 2-5min | ~30 MB |

*For ~15 second animation*

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Manim not found" | `pip install manim` |
| Rendering timeout | Use "code only" first, or simplify |
| LaTeX errors | Install LaTeX or avoid math |
| Slow rendering | Use `-ql` for testing, `-qh` for final |

## Tips

1. **Be specific:** "animate bubble sort with 5 elements" > "animate sorting"
2. **Start simple:** Test with "animate a circle" first
3. **Iterate:** Use "code only" → review → render
4. **Use documents:** Better accuracy with loaded docs
5. **Combine tools:** MCQs + animations = complete study materials

## Resources

- [Manim Community Docs](https://docs.manim.community/)
- [Tutorial](https://docs.manim.community/en/stable/tutorials.html)
- [Example Gallery](https://docs.manim.community/en/stable/examples.html)
- [3Blue1Brown Videos](https://www.youtube.com/c/3blue1brown)

---

**Multi-stage pipeline for high-quality educational animations.**

