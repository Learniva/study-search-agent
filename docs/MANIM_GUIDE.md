# Manim Animation Tool Guide

Create educational mathematical and conceptual animations from study materials using [Manim](https://www.manim.community/) (3Blue1Brown's animation engine).

## Installation

```bash
# Install Manim
pip install manim

# Install LaTeX (optional, for full features)
brew install mactex-no-gui-doc        # macOS
sudo apt-get install texlive-full     # Linux

# Install FFmpeg
brew install ffmpeg                   # macOS
sudo apt-get install ffmpeg           # Linux

# Verify
manim --version
```

## Usage

### Basic Patterns

```bash
# Generate and render animation
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
| `generate code only for [topic]` | Code only (no render) |

### Quality Settings

```bash
manim -ql file.py ConceptAnimation  # Low (480p, fast)
manim -qm file.py ConceptAnimation  # Medium (720p, default)
manim -qh file.py ConceptAnimation  # High (1080p)
manim -qp file.py ConceptAnimation  # Production (1440p)
```

## Examples

**Mathematics:**
- "animate the unit circle"
- "visualize Taylor series"
- "show quadratic formula derivation"

**Algorithms:**
- "animate bubble sort with 5 elements"
- "visualize binary search tree"
- "show quicksort partitioning"

**Physics:**
- "animate projectile motion"
- "visualize wave interference"
- "show simple harmonic motion"

**ML/AI:**
- "animate gradient descent"
- "visualize neural network layers"
- "show backpropagation"

## File Structure

```
animations/
├── videos/    # Rendered MP4 files
├── images/    # Intermediate images
└── Tex/       # LaTeX temporary files
```

**Output:** `animations/videos/[quality]/[name]_animation.mp4`

## Multi-Stage Pipeline

```
Stage 1: RAG Context - Extract relevant content from documents (if loaded)
Stage 2: Planning - Create structured animation plan (JSON)
Stage 3: Code Gen - Convert plan to Manim Python code
Stage 4: Execution - Render video with optional voice-over
```

**Voice-over:** Set `ELEVEN_API_KEY` in `.env` for high-quality TTS, or uses gTTS (free)

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

# 2. Save to file, edit as needed

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

## Integration with Other Tools

**With Document Q&A:**
```
"Generate 5 MCQs about neural networks and animate backpropagation"
```

**With Web Search:**
```
"What is gradient descent? Then animate it."
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Manim not found" | `pip install manim` |
| Rendering timeout | Use "code only" first, or simplify request |
| LaTeX errors | Install LaTeX or avoid math expressions |
| Slow rendering | Use `-ql` for testing, `-qh` for final |

## Performance

| Quality | Resolution | Time | Size |
|---------|-----------|------|------|
| Low | 480p | 10-20s | ~1 MB |
| Medium | 720p | 20-40s | ~3 MB |
| High | 1080p | 40-80s | ~10 MB |
| Production | 1440p | 2-5min | ~30 MB |

*For ~15 second animation*

## Tips

1. **Be specific:** "animate bubble sort with 5 elements" > "animate sorting"
2. **Start simple:** Test with "animate a circle" first
3. **Iterate:** Use "code only" → review → render
4. **Use documents:** Better accuracy when relevant docs are loaded
5. **Combine tools:** MCQs + animations = comprehensive study materials

## Resources

- [Manim Community Docs](https://docs.manim.community/)
- [Tutorial](https://docs.manim.community/en/stable/tutorials.html)
- [Example Gallery](https://docs.manim.community/en/stable/examples.html)
- [3Blue1Brown Videos](https://www.youtube.com/c/3blue1brown)

---

**Happy Animating! 🎬** Create beautiful educational visualizations with your Study Search Agent.
