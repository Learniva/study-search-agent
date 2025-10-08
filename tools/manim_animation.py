"""
Manim Animation Tool - Multi-Stage Pipeline for generating educational animations.

Pipeline Architecture (4 Stages):
- Stage 0: RAG (Context) - Retrieves source text from documents
- Stage 1: Planning Agent - Creates structured JSON/Markdown plan
- Stage 2: Code Generation Agent - Converts plan to Manim Python code
- Stage 3: Tool Execution - Runs the generated code

This follows a precise multi-stage approach for better LLM reasoning and output quality.
"""

import os
import re
import json
import tempfile
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ============================================================================
# STAGE 1: PLANNING AGENT - "Scene Designer" Persona
# ============================================================================
# Converts RAG output into a structured JSON or Markdown plan

PLANNING_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a "Scene Designer" for educational animations.

Your role is to take source material (formulas, definitions, concepts) and create a 
structured plan for animating it that will be converted to code.

OUTPUT FORMAT: Strict JSON with this structure:
{{{{
  "main_object": "Description of the primary mathematical/conceptual object to animate",
  "key_steps": [
    "Step 1: What to show first (be specific)",
    "Step 2: What transformation/animation to apply",
    "Step 3: Next logical step in the explanation",
    "Step 4: ...",
    "Step 5: Final emphasis or conclusion"
  ],
  "text_to_display": [
    "Main title or heading",
    "Formula or key equation",
    "Labels (like 'a', 'b', 'radius')",
    "Any explanatory text"
  ]
}}}}

PLANNING PRINCIPLES:
0. ⚠️ ALGORITHMIC CORRECTNESS (MOST CRITICAL!):
   - For algorithms: Plan MUST include EVERY SINGLE STEP to completion
   - Bubble Sort: Plan ALL passes needed to fully sort the array (not just 1 example)
   - Example: If array [4,2,3,1] needs 3 passes to sort, plan all 3 passes!
   - NEVER say "this continues" or "repeat until done" - PLAN each iteration explicitly
   - Math/Physics: Verify formulas are correct before planning
   - COMPLETENESS > BREVITY - educational accuracy is paramount!

1. MAIN OBJECT: Identify ONE primary thing to animate
   - Examples: "Right triangle with sides a, b, c"
   - Examples: "Parabola y = x²"
   - Examples: "Array with 4 elements [4,2,3,1] for complete bubble sort"
   - Be specific about what it looks like and initial state

2. KEY STEPS: Break down into as many steps as needed for COMPLETE demonstration
   - Each step should be ONE distinct action
   - For algorithms: Include EVERY comparison, swap, iteration
   - Steps should flow logically (build → iterate → complete → conclude)
   - Use action verbs: "Draw...", "Show...", "Animate...", "Highlight..."
   - Don't skip steps for brevity - education requires completeness!

3. TEXT TO DISPLAY: List all text/labels needed
   - Keep text concise (titles, formulas, labels only)
   - Include mathematical notation in LaTeX format
   - Order them by when they should appear

4. ACCURACY FIRST: The plan must be pedagogically correct and complete

FEW-SHOT EXAMPLES:

Example 1 - Pythagorean Theorem:
Context: "The Pythagorean theorem states a² + b² = c²"
Output:
{{{{
  "main_object": "Right triangle with sides labeled a (bottom), b (right), c (hypotenuse)",
  "key_steps": [
    "Step 1: Draw a right triangle with vertices at origin",
    "Step 2: Label the three sides as a, b, and c",
    "Step 3: Display the formula a² + b² = c² above the triangle",
    "Step 4: Draw squares on each side to show a², b², c²",
    "Step 5: Highlight that the two smaller squares equal the largest square"
  ],
  "text_to_display": [
    "Pythagorean Theorem",
    "a² + b² = c²",
    "a",
    "b", 
    "c"
  ]
}}}}

Example 2 - Bubble Sort Algorithm (COMPLETE - shows ALL passes!):
Context: "Bubble sort compares adjacent elements and swaps them if out of order"
Output:
{{{{
  "main_object": "Array of 4 numbers: [4, 2, 3, 1] (needs 3 passes to fully sort)",
  "key_steps": [
    "Step 1: Show initial array [4, 2, 3, 1]",
    "Step 2: PASS 1 - Compare 4 and 2, swap (now [2,4,3,1])",
    "Step 3: PASS 1 - Compare 4 and 3, swap (now [2,3,4,1])",  
    "Step 4: PASS 1 - Compare 4 and 1, swap (now [2,3,1,4], 4 is in correct position)",
    "Step 5: PASS 2 - Compare 2 and 3, no swap needed",
    "Step 6: PASS 2 - Compare 3 and 1, swap (now [2,1,3,4], 3 is in correct position)",
    "Step 7: PASS 3 - Compare 2 and 1, swap (now [1,2,3,4], FULLY SORTED!)",
    "Step 8: Highlight that array is completely sorted [1,2,3,4]"
  ],
  "text_to_display": [
    "Bubble Sort",
    "Initial: [5, 2, 8, 1, 9]",
    "Sorted: [1, 2, 5, 8, 9]"
  ]
}}}}

Example 3 - Circle Area Formula:
Context: "Area of circle is πr²"
Output:
{{{{
  "main_object": "Circle with visible radius line from center to edge",
  "key_steps": [
    "Step 1: Draw a circle in the center",
    "Step 2: Draw radius line from center to the edge",
    "Step 3: Label the radius as 'r'",
    "Step 4: Display the area formula A = πr²",
    "Step 5: Show shaded area inside the circle to emphasize coverage"
  ],
  "text_to_display": [
    "Circle Area",
    "A = πr²",
    "r"
  ]
}}}}

NOW CREATE A PLAN FOR THIS TOPIC:

Context from source material:
{context}

User request: {topic}

Generate ONLY the JSON plan following the format and examples above:"""),
    ("human", "Plan an animation for: {topic}")
])

# ============================================================================
# STAGE 2: CODE GENERATION AGENT - "Manim Python Coder" Persona
# ============================================================================
# Takes the structured JSON plan and generates exact Python code

CODE_GENERATION_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a "Manim Python Coder."

Your role is to take a STRUCTURED PLAN and convert it into exact, executable Manim Python code.
The plan removes ambiguity, making code generation easier and more precise.

INPUT: A structured JSON plan with:
- main_object: The primary thing to animate
- key_steps: Ordered list of animation steps
- text_to_display: Text elements to show

OUTPUT: Complete, executable Python code using this ESSENTIAL BOILERPLATE:

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class ConceptAnimation(VoiceoverScene):  # Use VoiceoverScene for narration
    def construct(self):
        # Set up gTTS voice service (fast, reliable, 100+ languages)
        self.set_speech_service(GTTSService(lang="en", tld="com"))
        
        # YOUR CODE GOES HERE
        # Use self.voiceover(text="...") as vo: to add narration
        # Animations inside the context will sync with speech
```

VOICEOVER USAGE (OPTIONAL - adds professional narration):
- Wrap animations with voiceover context: with self.voiceover(text="Narration") as vo:
- Animations inside the context sync automatically with speech
- Speech timing stored in vo.duration - use for wait times
- Example: with self.voiceover(text="Let's explore") as vo: self.play(Create(circle))
- Use natural, educational language - avoid technical jargon
- Keep narration concise: 1-2 sentences per voiceover block
- gTTS provides clear, fast narration (much faster than ElevenLabs!)

CRITICAL CONSTRAINTS:
0. ALGORITHMIC CORRECTNESS (HIGHEST PRIORITY - MOST IMPORTANT!):
   - For algorithms: SHOW EVERY SINGLE STEP - do NOT skip any iterations!
   - Bubble Sort: Show ALL passes until array is fully sorted
   - Example: If array needs 3 passes to sort, animate ALL 3 passes
   - NEVER say "this repeats" without showing it - SHOW the actual repetitions!
   - Math/Science: Verify formulas are correct before animating
   - Physics: Ensure equations and relationships are accurate
   - ACCURACY > BREVITY - completeness is essential for education
   - If algorithm takes 10 steps, show all 10 steps (not just 1-2 examples)

1. SPATIAL AWARENESS - PREVENT OVERLAPPING:
   - Frame size: 14.2 units wide × 8 units tall (centered at origin)
   - Safe zone: Keep all content within ±6 units horizontal, ±3.5 units vertical
   - ALWAYS leave MINIMUM 1.5 units of space between objects
   - Use .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5) to position safely
   - Use .shift(direction * distance) for precise positioning
   
   FOR HORIZONTAL ARRAYS (Bubble Sort, Lists, etc.) - CRITICAL:
   - NEVER exceed 10 units total width (to fit in frame!)
   - For 5 elements: Use buff=0.4 between elements (max width ~8 units)
   - For 4 elements: Use buff=0.5 between elements (max width ~7 units)
   - For 6+ elements: Scale down or use buff=0.3
   - ALWAYS use VGroup.arrange(RIGHT, buff=X) for horizontal layouts
   - Center the group: array_group.move_to(ORIGIN) or shift slightly
   - Example for arrays:
     ```
     boxes = VGroup(*[Square(side_length=1.2) for _ in range(5)])
     boxes.arrange(RIGHT, buff=0.5)  # Space them out
     boxes.move_to(ORIGIN)            # Center in frame
     # Result: ~8 units wide, fits perfectly!
     ```
   
   - For multi-layer diagrams (neural networks, etc.):
     * Horizontal spacing between layers: 4-5 units apart
     * Vertical spacing between nodes: 1.5-2 units apart
     * Place labels OUTSIDE shapes with buff=0.3 minimum
   - NEVER place text on top of other text!
   - Check for overlaps: If title is at TOP, place subtitles 1 unit below
   - Example good spacing: 
     * layer1 = VGroup(...).shift(LEFT * 4)  # Far left
     * layer2 = VGroup(...).shift(ORIGIN)    # Center  
     * layer3 = VGroup(...).shift(RIGHT * 4) # Far right

2. TIMING: End each distinct animation step with self.wait(1) for proper pacing
   - self.play(...) → self.wait(1) → next step
   - Use self.wait(0.5) for quick transitions
   - Use self.wait(2) for important concepts that need emphasis

3. CODE STRUCTURE: Follow the plan steps exactly in order

4. ULTRA-MODERN PROFESSIONAL AESTHETICS:
   - MINIMALISTIC, clean design with plenty of negative space
   
   PROFESSIONAL COLOR PALETTE (Tech/SaaS Style):
   * Primary Brand: #58C4DD (electric cyan) or #2196F3 (material blue) - use BLUE
   * Accent 1: #00D9FF (bright cyan) - use for highlights, important elements
   * Accent 2: #64FFDA (mint green) - use TEAL for success, growth
   * Neutral Light: #E0E0E0 (light gray) - use GRAY for backgrounds
   * Pure Contrast: #FFFFFF (pure white) - use WHITE for text, important shapes
   * Subtle Emphasis: #FFC107 (amber) - use YELLOW sparingly for warnings/attention
   * Deep Contrast: #1A1A1A (near black) - background is already dark
   * Keep colors consistent throughout the animation
   * Keep it simple, clean, and professional and more focused on the content
   
   WHAT TO AVOID:
   ❌ RED (too aggressive, use sparingly only for errors)
   ❌ ORANGE (too bright and childish)
   ❌ PURPLE/PINK (unprofessional)
   ❌ Solid fills (use fill_opacity=0.1-0.2 for subtle depth)
   
   MODERN DESIGN PRINCIPLES:
   - Flat design with subtle depth (use fill_opacity, not gradients)
   - Consistent stroke width: 2-4 (thicker = more modern)
   - Rounded corners where possible: corner_radius=0.2
   - Generous whitespace: buff=0.5-1.0 minimum
   - Hierarchy: Larger = more important (font_size: 48 title, 36 body, 28 labels)
   - Smooth transitions: FadeIn, FadeOut, Create, Transform
   
   EXAMPLES:
   * Modern shape: Circle(radius=2, color="#58C4DD", stroke_width=3, fill_opacity=0.15)
   * Clean text: Text("Title", font_size=48, color=WHITE, weight=BOLD)
   * Subtle box: RoundedRectangle(width=3, height=2, corner_radius=0.2, color=BLUE, fill_opacity=0.1, stroke_width=2)

5. OBJECTS: Use appropriate Manim primitives
   - Text: Text("string", font_size=36, color=WHITE, weight=BOLD)
     * CRITICAL: 'weight' parameter ONLY works with Text(), NOT MathTex()!
     * weight=BOLD or weight=NORMAL (only for Text objects)
   - Math: MathTex("x^2 + y^2 = r^2", font_size=48, color=WHITE)
     * CRITICAL: MathTex does NOT accept 'weight' parameter!
     * NEVER use: MathTex(..., weight=BOLD) ❌ TypeError!
     * Use font_size only: MathTex("x^2", font_size=48, color=WHITE) ✅
   - IMPORTANT: If LaTeX is not available, use Text() instead of MathTex()
   - For simple variables, Text("a") works as well as MathTex("a")
   - Shapes: Circle(), Square(), Polygon(p1, p2, p3, ...)
   - Lines: Line(start_point, end_point, color=WHITE, stroke_width=2)
   
   CRITICAL - SIZING OBJECTS:
   - NEVER use FRAME_WIDTH or FRAME_HEIGHT (these don't exist!) ❌
   - Use numeric values: obj.set_width(10) or obj.scale(0.8) ✅
   - Frame is ~14 units wide × 8 units tall
   - To fit text: text.set_width(12) or text.scale_to_fit_width(12) ✅
   - DASHED Lines: DashedLine(start_point, end_point, color=GRAY, stroke_width=2)
     * CRITICAL: Use DashedLine class, NOT dash_length parameter!
     * Example: DashedLine(point1, point2, color=GRAY)
     * NEVER use: Line(..., dash_length=0.2) ❌ This will cause errors!
   - Axes: Axes(x_range=[-5, 5], y_range=[-5, 5], color=WHITE)
   - Graphs: axes.plot(lambda x: x**2, color=BLUE)
   - Groups: VGroup(obj1, obj2, ...)
   - Right Angle: RightAngle(line1, line2, length=0.3) - REQUIRES TWO LINE OBJECTS, NOT POINTS
   - Dots: Dot(point, radius=0.05, color=BLUE)  # Use professional colors!

6. ANIMATIONS: Use smooth, clear animations
   - Create(object) - draw shapes
   - Write(text) - write text
   - FadeIn(object) - fade in
   - FadeOut(object) - fade out
   - Transform(obj1, obj2) - morph one into another

FEW-SHOT EXAMPLES:

Example 1: Simple Formula Display
Plan: {{"main_object": "Quadratic formula", "key_steps": ["Show formula", "Highlight parts"], "text_to_display": ["Quadratic Formula"]}}

Code:
```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Title
        title = Text("Quadratic Formula", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(1)
        
        # Formula
        # Note: Using double escapes to avoid Python 3.13 raw string warning
        formula = MathTex("x", "=", "{{{{-b", "\\pm", "\\sqrt{{{{b^2 - 4ac}}}}", "}}}}", "\\over", "2a")
        formula.scale(1.5)
        self.play(Write(formula))
        self.wait(1)
        
        # Highlight parts
        box = SurroundingRectangle(formula[2:6], color=YELLOW)
        self.play(Create(box))
        self.wait(1)
        
        self.play(FadeOut(box))
        self.wait(2)
```

Example 2: Geometric Shape with Labels (WITH VOICEOVER)
Plan: {{"main_object": "Circle with radius", "key_steps": ["Draw circle", "Add radius line", "Label radius"], "text_to_display": ["Circle", "r"]}}

Code:
```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class ConceptAnimation(VoiceoverScene):
    def construct(self):
        # Set up gTTS voice service (fast and reliable!)
        self.set_speech_service(GTTSService(lang="en", tld="com"))
        
        # Title with narration
        title = Text("Circle", font_size=48)
        title.to_edge(UP)
        
        with self.voiceover(text="Let's explore the circle, one of the most fundamental shapes in geometry.") as vo:
            self.play(Write(title))
        
        self.play(FadeOut(title))
        self.wait(0.5)
        
        # Draw circle with narration
        circle = Circle(radius=2, color="#58C4DD", stroke_width=3, fill_opacity=0.15)
        
        with self.voiceover(text="A circle is defined as all points equidistant from a center point.") as vo:
            self.play(Create(circle), run_time=1.5)
        
        # Add radius line with narration
        radius_line = Line(ORIGIN, circle.point_from_proportion(0), color="#00D9FF", stroke_width=4)
        label = Text("r", font_size=40, color=WHITE, weight=BOLD)
        label.next_to(radius_line, RIGHT, buff=0.3)
        
        with self.voiceover(text="This distance from the center to any point on the circle is called the radius.") as vo:
            self.play(Create(radius_line))
            self.play(FadeIn(label, shift=DOWN*0.2))
        
        self.wait(2)
```

Example 3: Step-by-Step Transformation
Plan: {{"main_object": "Square to circle transformation", "key_steps": ["Show square", "Transform to circle", "Show final result"], "text_to_display": ["Transformation"]}}

Code:
```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Title
        title = Text("Transformation", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(1)
        
        # Show square
        square = Square(side_length=2, color=RED)
        self.play(Create(square))
        self.wait(1)
        
        # Transform to circle
        circle = Circle(radius=1, color=BLUE)
        self.play(Transform(square, circle))
        self.wait(1)
        
        # Emphasize result
        self.play(square.animate.scale(1.2))
        self.wait(1)
        self.play(square.animate.scale(1/1.2))
        self.wait(2)
```

Example 4: Right Triangle (CORRECT RightAngle Usage)
Plan: {{"main_object": "Right triangle with sides labeled", "key_steps": ["Draw triangle", "Mark right angle CORRECTLY", "Label sides a, b, c"], "text_to_display": ["Right Triangle", "a", "b", "c"]}}

Code:
```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Title
        title = Text("Right Triangle", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(1)
        
        # Define vertices for right triangle
        A = np.array([-2, -1, 0])  # Bottom left (right angle here)
        B = np.array([2, -1, 0])   # Bottom right  
        C = np.array([-2, 2, 0])   # Top left
        
        # Draw triangle (modern - electric cyan with subtle fill)
        triangle = Polygon(A, B, C, color="#58C4DD", fill_color="#58C4DD", fill_opacity=0.12, stroke_width=3)
        self.play(Create(triangle))
        self.wait(1)
        
        # CRITICAL: RightAngle needs TWO LINE OBJECTS (not points or polygon!)
        # Create line objects for the two sides forming the right angle
        side_a = Line(A, B, color=WHITE, stroke_width=2)  # Horizontal side
        side_b = Line(A, C, color=WHITE, stroke_width=2)  # Vertical side
        
        # Now mark the right angle using the LINE OBJECTS (BLUE for emphasis)
        angle_mark = RightAngle(side_a, side_b, length=0.3, color=BLUE, stroke_width=3)
        self.play(Create(angle_mark))
        self.wait(1)
        
        # Label the three sides (WHITE text, clean)
        label_a = Text("a", font_size=32, color=WHITE).next_to(Line(A, B).get_center(), DOWN)
        label_b = Text("b", font_size=32, color=WHITE).next_to(Line(A, C).get_center(), LEFT)
        label_c = Text("c", font_size=32, color=BLUE).next_to(Line(B, C).get_center(), UR)  # Hypotenuse in BLUE
        
        self.play(Write(label_a), Write(label_b), Write(label_c))
        self.wait(2)
```

Example 5: Neural Network (CORRECT SPACING - NO OVERLAPS!)
Plan: {{"main_object": "Simple 2-layer neural network diagram", "key_steps": ["Show title", "Draw input layer", "Draw hidden layer", "Draw output layer", "Add connections", "Label layers"], "text_to_display": ["Neural Network", "Input", "Hidden", "Output"]}}

Code:
```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Title at TOP (large, bold, modern)
        title = Text("Neural Network", font_size=48, color=WHITE, weight=BOLD)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title, shift=DOWN*0.3))
        self.wait(1)
        
        # CRITICAL: Proper spacing between layers (4 units apart)
        # Input layer (LEFT side) - Electric cyan with subtle fill
        input_nodes = VGroup(
            Circle(radius=0.35, color="#58C4DD", stroke_width=3, fill_opacity=0.15),
            Circle(radius=0.35, color="#58C4DD", stroke_width=3, fill_opacity=0.15)
        ).arrange(DOWN, buff=1.5)  # 1.5 units vertical spacing
        input_nodes.shift(LEFT * 4.5)  # Far left
        
        # Hidden layer (CENTER) - White with subtle glow effect
        hidden_nodes = VGroup(
            Circle(radius=0.35, color=WHITE, stroke_width=3, fill_opacity=0.1),
            Circle(radius=0.35, color=WHITE, stroke_width=3, fill_opacity=0.1),
            Circle(radius=0.35, color=WHITE, stroke_width=3, fill_opacity=0.1)
        ).arrange(DOWN, buff=1.5)  # 1.5 units vertical spacing
        hidden_nodes.shift(ORIGIN)  # Center
        
        # Output layer (RIGHT side) - Mint green accent
        output_nodes = VGroup(
            Circle(radius=0.35, color="#64FFDA", stroke_width=3, fill_opacity=0.2)
        )
        output_nodes.shift(RIGHT * 4.5)  # Far right
        
        # Draw all layers with elegant timing
        self.play(FadeIn(input_nodes, shift=RIGHT*0.5), run_time=1)
        self.wait(0.3)
        self.play(FadeIn(hidden_nodes, shift=RIGHT*0.5), run_time=1)
        self.wait(0.3)
        self.play(FadeIn(output_nodes, shift=RIGHT*0.5), run_time=1)
        self.wait(1)
        
        # Modern labels BELOW with proper spacing
        input_label = Text("Input", font_size=32, color="#58C4DD", weight=BOLD).next_to(input_nodes, DOWN, buff=0.8)
        hidden_label = Text("Hidden", font_size=32, color=WHITE, weight=BOLD).next_to(hidden_nodes, DOWN, buff=0.8)
        output_label = Text("Output", font_size=32, color="#64FFDA", weight=BOLD).next_to(output_nodes, DOWN, buff=0.8)
        
        self.play(
            FadeIn(input_label, shift=UP*0.2),
            FadeIn(hidden_label, shift=UP*0.2),
            FadeIn(output_label, shift=UP*0.2),
            run_time=1
        )
        self.wait(2)
```

Example 6: Graphing Functions (Derivatives, Calculus)
Plan: {{"main_object": "Graph showing function and tangent line", "key_steps": ["Create axes", "Plot function", "Show point on curve", "Draw tangent line"], "text_to_display": ["Function Graph", "f(x)", "Tangent"]}}

Code:
```python
from manim import *

class ConceptAnimation(Scene):
    def construct(self):
        # Title
        title = Text("Function and Tangent", font_size=48, color=WHITE, weight=BOLD)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title, shift=DOWN*0.3))
        self.wait(1)
        
        # Create axes (modern colors)
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 8, 2],
            x_length=8,
            y_length=6,
            axis_config={{"color": WHITE, "stroke_width": 2}},
            tips=False
        ).scale(0.7)
        axes.shift(DOWN * 0.5)
        
        self.play(Create(axes), run_time=1)
        self.wait(0.5)
        
        # Plot function (electric cyan)
        graph = axes.plot(lambda x: 0.5 * x**2, color="#58C4DD", stroke_width=3)
        graph_label = MathTex("f(x) = x^2", font_size=36, color="#58C4DD").next_to(graph, UP, buff=0.5)
        
        self.play(Create(graph), run_time=1.5)
        self.play(FadeIn(graph_label))
        self.wait(1)
        
        # Point on curve (bright cyan dot)
        x_val = 1.5
        point = Dot(axes.c2p(x_val, 0.5 * x_val**2), color="#00D9FF", radius=0.08)
        
        self.play(FadeIn(point, scale=0.5))
        self.wait(0.5)
        
        # CORRECT: Use DashedLine (not dash_length parameter!)
        vertical_line = DashedLine(
            axes.c2p(x_val, 0),
            axes.c2p(x_val, 0.5 * x_val**2),
            color=GRAY,
            stroke_width=2
        )
        
        self.play(Create(vertical_line))
        self.wait(1)
        
        # Tangent line (mint green)
        slope = x_val  # derivative
        tangent = axes.plot(
            lambda x: slope * (x - x_val) + 0.5 * x_val**2,
            x_range=[x_val - 1, x_val + 1],
            color="#64FFDA",
            stroke_width=3
        )
        
        self.play(Create(tangent), run_time=1)
        self.wait(2)
```

Example 7: COMPLETE Bubble Sort Algorithm (Shows ALL steps - CRITICAL for educational accuracy!)
Plan: {{"main_object": "Array sorting with bubble sort", "key_steps": ["Show initial array [4,2,3,1]", "Pass 1: Compare ALL adjacent pairs, swap if needed", "Pass 2: Continue until sorted", "Show final sorted array"], "text_to_display": ["Bubble Sort", "Pass 1", "Pass 2", "Sorted!"]}}

Code:
```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class ConceptAnimation(VoiceoverScene):
    def construct(self):
        # Set up voice
        self.set_speech_service(GTTSService(lang="en", tld="com"))
        
        # Title
        title = Text("Bubble Sort - Complete Algorithm", font_size=40, color="#58C4DD", weight=BOLD)
        title.to_edge(UP, buff=0.4)
        
        with self.voiceover(text="Let's see bubble sort, showing every single step") as vo:
            self.play(FadeIn(title))
        
        # CRITICAL: Use small array (4 elements) to show COMPLETE sort without taking too long
        values = [4, 2, 3, 1]  # Will need 3 passes to fully sort
        
        # Create boxes with proper spacing
        boxes = VGroup(*[
            RoundedRectangle(width=1.2, height=1.2, corner_radius=0.1,
                           color="#58C4DD", stroke_width=3, fill_opacity=0.1)
            for _ in values
        ])
        boxes.arrange(RIGHT, buff=0.4)
        boxes.move_to(ORIGIN)
        
        # Numbers inside boxes
        nums = VGroup(*[
            Text(str(v), font_size=36, color=WHITE, weight=BOLD)
            for v in values
        ])
        for num, box in zip(nums, boxes):
            num.move_to(box.get_center())
        
        with self.voiceover(text="We start with the array 4, 2, 3, 1") as vo:
            self.play(*[Create(box) for box in boxes], *[Write(num) for num in nums])
        
        # CRITICAL: Perform COMPLETE bubble sort - show ALL passes!
        current_values = values.copy()
        n = len(current_values)
        
        # Pass 1
        pass_label = Text("Pass 1", font_size=32, color=YELLOW).next_to(boxes, DOWN, buff=0.8)
        self.play(Write(pass_label))
        
        with self.voiceover(text="Pass 1: Compare 4 and 2. 4 is greater, so swap them") as vo:
            self.play(boxes[0].animate.set_color(YELLOW), boxes[1].animate.set_color(YELLOW))
            self.play(nums[0].animate.move_to(boxes[1]), nums[1].animate.move_to(boxes[0]))
            nums[0], nums[1] = nums[1], nums[0]  # Track the swap
            current_values[0], current_values[1] = current_values[1], current_values[0]
            self.play(boxes[0].animate.set_color("#58C4DD"), boxes[1].animate.set_color("#58C4DD"))
        
        with self.voiceover(text="Compare 4 and 3. 4 is greater, swap") as vo:
            self.play(boxes[1].animate.set_color(YELLOW), boxes[2].animate.set_color(YELLOW))
            self.play(nums[1].animate.move_to(boxes[2]), nums[2].animate.move_to(boxes[1]))
            nums[1], nums[2] = nums[2], nums[1]
            current_values[1], current_values[2] = current_values[2], current_values[1]
            self.play(boxes[1].animate.set_color("#58C4DD"), boxes[2].animate.set_color("#58C4DD"))
        
        with self.voiceover(text="Compare 4 and 1. 4 is greater, swap. Now 4 is in correct position") as vo:
            self.play(boxes[2].animate.set_color(YELLOW), boxes[3].animate.set_color(YELLOW))
            self.play(nums[2].animate.move_to(boxes[3]), nums[3].animate.move_to(boxes[2]))
            nums[2], nums[3] = nums[3], nums[2]
            current_values[2], current_values[3] = current_values[2], current_values[3]
            self.play(boxes[2].animate.set_color("#58C4DD"), boxes[3].animate.set_color(GREEN))
        
        self.play(FadeOut(pass_label))
        
        # Pass 2
        pass_label = Text("Pass 2", font_size=32, color=YELLOW).next_to(boxes, DOWN, buff=0.8)
        self.play(Write(pass_label))
        
        with self.voiceover(text="Pass 2: Compare 2 and 3. No swap needed") as vo:
            self.play(boxes[0].animate.set_color(YELLOW), boxes[1].animate.set_color(YELLOW))
            self.wait(0.5)
            self.play(boxes[0].animate.set_color("#58C4DD"), boxes[1].animate.set_color("#58C4DD"))
        
        with self.voiceover(text="Compare 3 and 1. 3 is greater, swap. Array is now 2, 1, 3, 4") as vo:
            self.play(boxes[1].animate.set_color(YELLOW), boxes[2].animate.set_color(YELLOW))
            self.play(nums[1].animate.move_to(boxes[2]), nums[2].animate.move_to(boxes[1]))
            nums[1], nums[2] = nums[2], nums[1]
            self.play(boxes[1].animate.set_color("#58C4DD"), boxes[2].animate.set_color(GREEN))
        
        self.play(FadeOut(pass_label))
        
        # Pass 3 (Final pass)
        pass_label = Text("Pass 3", font_size=32, color=YELLOW).next_to(boxes, DOWN, buff=0.8)
        self.play(Write(pass_label))
        
        with self.voiceover(text="Pass 3: Compare 2 and 1. Swap them. Now all elements are sorted!") as vo:
            self.play(boxes[0].animate.set_color(YELLOW), boxes[1].animate.set_color(YELLOW))
            self.play(nums[0].animate.move_to(boxes[1]), nums[1].animate.move_to(boxes[0]))
            nums[0], nums[1] = nums[1], nums[0]
            self.play(boxes[0].animate.set_color(GREEN), boxes[1].animate.set_color(GREEN))
        
        self.play(FadeOut(pass_label))
        
        # Show sorted result
        sorted_label = Text("Sorted!", font_size=40, color=GREEN, weight=BOLD)
        sorted_label.next_to(boxes, DOWN, buff=0.8)
        
        with self.voiceover(text="The array is now completely sorted: 1, 2, 3, 4") as vo:
            self.play(Write(sorted_label))
        
        self.wait(2)
        
        # CRITICAL LESSON: This example shows EVERY comparison and swap
        # Array [4,2,3,1] needs 3 passes with 4 swaps total to become [1,2,3,4]
        # NEVER skip steps in algorithm visualizations!
```

NOW GENERATE CODE FOR THIS PLAN:
Structured Plan:
{plan}

Generate ONLY the Python code following the boilerplate, constraints, and examples above:"""),
    ("human", "Convert this plan to Manim code")
])


def extract_python_code(text: str) -> str:
    """
    Extract Python code from LLM response.
    
    Args:
        text: LLM response that may contain code blocks
        
    Returns:
        Clean Python code
    """
    # Remove markdown code fences if present
    text = re.sub(r'```python\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # If the text starts with "from manim", it's clean code
    if text.strip().startswith('from manim'):
        return text.strip()
    
    # Try to find code that starts with "from manim" or "import"
    lines = text.split('\n')
    code_lines = []
    in_code = False
    
    for line in lines:
        if line.strip().startswith(('from manim', 'import ', 'class ')):
            in_code = True
        if in_code:
            code_lines.append(line)
    
    if code_lines:
        return '\n'.join(code_lines)
    
    return text.strip()


class ManimAnimationManager:
    """
    Manages Manim animation generation from educational content.
    """
    
    def __init__(self, output_dir: str = "animations"):
        """
        Initialize the Manim Animation Manager.
        
        Args:
            output_dir: Directory to save generated animations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize LLM for code generation
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=google_api_key,
            temperature=0.7,  # Slightly creative for diverse animations
            convert_system_message_to_human=True
        )
        
        # Check if Manim is installed
        self._check_manim_installation()
        
        # Try to get document retriever if available
        self.doc_retriever = None
        try:
            from .document_qa import _doc_manager
            if _doc_manager and _doc_manager.retriever:
                self.doc_retriever = _doc_manager.retriever
                print("✓ Document retriever connected for context-aware animations")
        except:
            print("ℹ️  Document retriever not available - will generate animations without document context")
    
    def _check_manim_installation(self) -> bool:
        """
        Check if Manim is properly installed.
        
        Returns:
            True if Manim is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['manim', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✓ Manim is installed: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        print("⚠️  Manim not found. Please install with: pip install manim")
        return False
    
    def _get_document_context(self, topic: str) -> str:
        """
        Retrieve relevant context from documents if available.
        
        Args:
            topic: Topic to search for
            
        Returns:
            Formatted context string or empty string
        """
        if not self.doc_retriever:
            return ""
        
        try:
            docs = self.doc_retriever.invoke(topic)
            context = "\n\n".join([
                f"[{doc.metadata.get('source', 'Unknown')} - Page {doc.metadata.get('page', 'N/A')}]\n{doc.page_content[:500]}"
                for doc in docs[:3]  # Top 3 chunks
            ])
            return context
        except Exception as e:
            print(f"⚠️  Could not retrieve document context: {e}")
            return ""
    
    def generate_animation_code(self, topic: str, custom_context: str = "") -> str:
        """
        Generate Manim Python code using multi-stage pipeline.
        
        Pipeline Stages:
        - Stage 0 (RAG): Retrieve source text from documents
        - Stage 1 (Planning): Create structured JSON plan with "Scene Designer" persona
        - Stage 2 (Code Gen): Convert plan to Python code with "Manim Python Coder" persona
        
        Args:
            topic: The mathematical or conceptual topic to animate
            custom_context: Optional additional context
            
        Returns:
            Python code for Manim animation
        """
        try:
            print(f"\n{'='*60}")
            print(f"🎬 Multi-Stage Animation Pipeline for: '{topic}'")
            print(f"{'='*60}\n")
            
            # ============================================================
            # STAGE 0: RAG (Context) - Retrieve source text
            # ============================================================
            print("📚 STAGE 0: RAG (Context) - Retrieving source material...")
            doc_context = self._get_document_context(topic)
            
            # Combine contexts
            full_context = doc_context
            if custom_context:
                full_context = f"{custom_context}\n\n{full_context}" if full_context else custom_context
            
            if not full_context:
                full_context = "Create an educational animation explaining this concept clearly and visually."
            
            print(f"✓ Retrieved context ({len(full_context)} characters)")
            
            # ============================================================
            # STAGE 1: PLANNING AGENT - "Scene Designer" Persona
            # ============================================================
            print("\n📋 STAGE 1: Planning Agent (Scene Designer)")
            print("   Creating structured JSON plan...")
            
            planning_chain = (
                PLANNING_AGENT_PROMPT
                | self.llm
                | StrOutputParser()
            )
            
            plan_output = planning_chain.invoke({
                "topic": topic,
                "context": full_context
            })
            
            # Try to parse as JSON to validate structure
            try:
                plan_json = json.loads(plan_output)
                print(f"✓ Plan created:")
                print(f"   - Main Object: {plan_json.get('main_object', 'N/A')}")
                print(f"   - Key Steps: {len(plan_json.get('key_steps', []))} steps")
                print(f"   - Text Elements: {len(plan_json.get('text_to_display', []))}")
            except json.JSONDecodeError:
                print("⚠️  Plan generated (not strict JSON, but usable)")
            
            # ============================================================
            # STAGE 2: CODE GENERATION AGENT - "Manim Python Coder" Persona
            # ============================================================
            print("\n🐍 STAGE 2: Code Generation Agent (Manim Python Coder)")
            print("   Converting structured plan to Python code...")
            
            code_gen_chain = (
                CODE_GENERATION_AGENT_PROMPT
                | self.llm
                | StrOutputParser()
            )
            
            code = code_gen_chain.invoke({
                "plan": plan_output
            })
            
            # Extract clean Python code
            clean_code = extract_python_code(code)
            
            print(f"✓ Generated {len(clean_code)} characters of Python code")
            print(f"\n{'='*60}")
            print("✅ Multi-Stage Pipeline Complete!")
            print(f"{'='*60}\n")
            
            return clean_code
            
        except Exception as e:
            return f"Error in animation pipeline: {e}"
    
    def create_animation(self, topic: str, quality: str = "medium_quality", 
                        custom_context: str = "") -> Dict[str, Any]:
        """
        Generate and render a Manim animation.
        
        Args:
            topic: The topic to animate
            quality: Manim quality setting (low_quality, medium_quality, high_quality, production_quality)
            custom_context: Optional additional context for code generation
            
        Returns:
            Dictionary with status, file path, and code
        """
        try:
            print(f"\n{'='*60}")
            print(f"Creating Manim Animation: {topic}")
            print(f"{'='*60}\n")
            
            # Generate animation code
            code = self.generate_animation_code(topic, custom_context)
            
            if code.startswith("Error"):
                return {
                    "status": "error",
                    "error": code,
                    "code": None,
                    "video_path": None
                }
            
            # Create temporary Python file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Sanitize topic for filename
                safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')
                output_file = f"{safe_topic}_animation"
                
                # Render animation with Manim
                print(f"🎥 Rendering animation with Manim ({quality})...")
                print(f"   Output: {self.output_dir}/{output_file}.mp4")
                
                # Run Manim command
                cmd = [
                    'manim',
                    '-ql' if quality == 'low_quality' else 
                    '-qm' if quality == 'medium_quality' else
                    '-qh' if quality == 'high_quality' else '-qp',
                    temp_file,
                    'ConceptAnimation',  # Scene class name
                    '-o', output_file,
                    '--media_dir', str(self.output_dir)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout (gTTS is much faster!)
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr if result.stderr else result.stdout
                    print(f"❌ Manim rendering failed:")
                    print(error_msg)
                    return {
                        "status": "error",
                        "error": f"Manim rendering failed: {error_msg[:500]}",
                        "code": code,
                        "video_path": None
                    }
                
                # Find the generated video file
                video_files = list(self.output_dir.rglob(f"{output_file}.mp4"))
                
                if not video_files:
                    return {
                        "status": "error",
                        "error": "Video file not found after rendering",
                        "code": code,
                        "video_path": None
                    }
                
                video_path = str(video_files[0])
                
                print(f"✅ Animation created successfully!")
                print(f"📁 Saved to: {video_path}")
                
                return {
                    "status": "success",
                    "video_path": video_path,
                    "code": code,
                    "topic": topic
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Animation rendering timed out (exceeded 5 minutes). Script may be too complex.",
                "code": code if 'code' in locals() else None,
                "video_path": None
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Error creating animation: {str(e)}",
                "code": code if 'code' in locals() else None,
                "video_path": None
            }
    
    def generate_code_only(self, topic: str, custom_context: str = "") -> str:
        """
        Generate Manim code without rendering (for preview/editing).
        
        Args:
            topic: The topic to animate
            custom_context: Optional additional context
            
        Returns:
            Generated Manim Python code
        """
        code = self.generate_animation_code(topic, custom_context)
        
        if not code.startswith("Error"):
            print(f"\n{'='*60}")
            print("Generated Manim Code:")
            print(f"{'='*60}\n")
            print(code)
            print(f"\n{'='*60}\n")
        
        return code


# Global manager instance
_manim_manager = None


def initialize_manim_tool(output_dir: str = "animations") -> bool:
    """
    Initialize the Manim animation tool.
    
    Args:
        output_dir: Directory to save generated animations
        
    Returns:
        True if initialization was successful, False otherwise
    """
    global _manim_manager
    try:
        _manim_manager = ManimAnimationManager(output_dir)
        return True
    except Exception as e:
        print(f"⚠️  Could not initialize Manim tool: {e}")
        return False


def generate_manim_animation(manim_code: str) -> str:
    """
    Writes manim_code to a .py file, executes external Manim rendering process,
    and returns a Tool Artifact response.
    
    This is the high-latency step that produces the deliverable MP4 video file.
    
    Args:
        manim_code: Complete, executable Python script containing a Manim Scene class
                   with 'from manim import *' and 'class ConceptAnimation(Scene)'.
    
    Returns:
        Tool Artifact as JSON string with format:
        {
            "content": "Message for LLM to read and formulate user response",
            "artifact": "/path/to/video.mp4" or null
        }
        
        The 'content' field informs the LLM that the action is complete.
        The 'artifact' field contains the deliverable Video File (.mp4) that:
        - Can be used by a UI in the future to display/download the video
        - Could be a public link that the UI uses
        - For now, can be viewed in terminal/CLI
        
        Success example:
        {
            "content": "Animation successfully rendered",
            "artifact": "/Users/.../animations/videos/pythagorean.mp4"
        }
        
        Error example:
        {
            "content": "Error: Animation rendering failed...",
            "artifact": null
        }
    """
    global _manim_manager
    
    if _manim_manager is None:
        return json.dumps({
            "content": "Error: Manim tool not initialized. Please ensure Manim is installed.",
            "artifact": None
        })
    
    # Validate input is a complete script
    if not any(marker in manim_code for marker in ['from manim', 'import manim', 'class ConceptAnimation']):
        return json.dumps({
            "content": f"Error: Invalid input. Expected complete Python script with Manim Scene class, received: {manim_code[:100]}...",
            "artifact": None
        })
    
    print("📝 Writing Manim script to file...")
    
    # Write manim_code to a temporary .py file
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, prefix='manim_') as f:
            f.write(manim_code)
            temp_file = f.name
        
        print(f"✓ Script written to: {temp_file}")
    except Exception as e:
        return json.dumps({
            "content": f"Error: Failed to write script to file: {str(e)}",
            "artifact": None
        })
    
    # Extract title for output filename
    topic = "animation"
    title_match = re.search(r'Text\(["\']([^"\']+)["\']', manim_code)
    if title_match:
        topic = title_match.group(1).replace(' ', '_').lower()
    
    safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')
    output_file = f"{safe_topic}"
    
    try:
        # Execute subprocess.run(["manim", ...]) - HIGH-LATENCY STEP
        print(f"🎥 Executing Manim rendering process (this may take 30-60 seconds)...")
        
        cmd = [
            'manim',
            '-qm',  # Medium quality
            temp_file,
            'ConceptAnimation',
            '-o', output_file,
            '--media_dir', str(_manim_manager.output_dir)
        ]
        
        print(f"Command: {' '.join(cmd)}")
        
        # Execute and capture errors
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5-minute timeout (gTTS is fast!)
        )
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else result.stdout
            print(f"❌ Manim rendering failed with code {result.returncode}")
            
            # Return Tool Artifact with error
            return json.dumps({
                "content": f"Error: Animation rendering failed. {error_msg[:300]}",
                "artifact": None
            })
        
        print("✓ Manim rendering completed successfully")
        
        # Find the generated video file (/media/videos/...mp4)
        video_files = list(_manim_manager.output_dir.rglob(f"{output_file}.mp4"))
        
        if not video_files:
            # Try alternative patterns
            video_files = list(_manim_manager.output_dir.rglob("*.mp4"))
            if video_files:
                # Get most recent
                video_files = sorted(video_files, key=lambda p: p.stat().st_mtime, reverse=True)
        
        if video_files:
            video_path = str(video_files[0])
            print(f"✓ Video saved to: {video_path}")
            
            # Return Tool Artifact: (content, artifact=video_path)
            # The artifact is the deliverable Video File (.mp4)
            # In the future, UI can use this path to display/download the video
            return json.dumps({
                "content": "Animation successfully rendered",
                "artifact": video_path  # Video File (.mp4) - the deliverable
            })
        else:
            return json.dumps({
                "content": f"Error: Rendering completed but video file not found in {_manim_manager.output_dir}/videos/",
                "artifact": None
            })
    
    except subprocess.TimeoutExpired:
        return json.dumps({
            "content": "Error: Animation rendering timed out (exceeded 5 minutes). Script may be too complex or contain issues.",
            "artifact": None
        })
    
    except Exception as e:
        return json.dumps({
            "content": f"Error: Unexpected error during rendering: {str(e)}",
            "artifact": None
        })
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                print(f"✓ Cleaned up temporary file")
        except:
            pass


def create_animation_from_topic(topic: str) -> str:
    """
    Wrapper function that handles the complete animation pipeline from topic to video.
    This is the function exposed to the LLM via the tool.
    
    Args:
        topic: The topic/concept to animate (e.g., "Pythagorean theorem", "bubble sort")
        
    Returns:
        JSON string with Tool Artifact format: {"content": "...", "artifact": "..."}
    """
    global _manim_manager
    
    if _manim_manager is None:
        return json.dumps({
            "content": "Error: Manim tool not initialized. Please ensure Manim is installed.",
            "artifact": None
        })
    
    try:
        # Use the manager's create_animation method which handles the full pipeline
        result = _manim_manager.create_animation(topic, quality="high_quality")
        
        if result["status"] == "success":
            return json.dumps({
                "content": f"✅ Animation successfully rendered for '{topic}'",
                "artifact": result["video_path"]
            })
        else:
            return json.dumps({
                "content": f"Error: {result.get('error', 'Unknown error occurred')}",
                "artifact": None
            })
    
    except Exception as e:
        return json.dumps({
            "content": f"Error: Unexpected error creating animation: {str(e)}",
            "artifact": None
        })


def get_manim_tool() -> Optional[Tool]:
    """
    Create and return the Manim animation tool.
    
    Returns:
        Tool object configured for Manim animations, or None if not initialized
    """
    global _manim_manager
    
    if _manim_manager is None:
        # Try to initialize
        if not initialize_manim_tool():
            return None
    
    return Tool(
        name="render_manim_video",
        func=create_animation_from_topic,
        description="""Use this ONLY when the final goal is to create a video animation.

MULTI-STAGE PIPELINE ARCHITECTURE:
This tool uses a 4-stage approach for precise, high-quality animation generation:

Stage 0: RAG (Context)
- Persona: "The Retrieval system on your PDF"
- Action: Extracts source text (formulas, definitions) the user wants animated
- Uses document retriever to get relevant content

Stage 1: Planning Agent
- Persona: "Scene Designer"
- Action: Takes RAG output and converts it into structured JSON/Markdown plan
- Plan includes: 1) Main Object (Graph/Formula), 2) Key steps (Animate in order), 3) Text to display
- This intermediate format removes ambiguity for the LLM

Stage 2: Code Generation Agent
- Persona: "Manim Python Coder"
- Action: Takes the structured JSON plan and generates exact Python code
- The plan makes code generation easier and more precise
- Outputs complete, executable Manim script

Stage 3: Manim Tool Execution
- Tool: render_manim_video
- Action: Writes code to .py file, executes subprocess.run(["manim", ...])
- This is the HIGH-LATENCY step (30-60 sec)
- Returns deliverable video file (.mp4)

INPUT SCHEMA:
Parameter: topic (str) - The concept/topic to animate (e.g., "Pythagorean theorem", "bubble sort", "quadratic formula")

WORKFLOW FOR LLM:
1. User requests animation (e.g., "animate the Pythagorean theorem")
2. LLM invokes this tool with the topic string
3. Tool internally runs ALL stages:
   - Stage 0: RAG (retrieves document context)
   - Stage 1: Planning Agent (creates structured plan)
   - Stage 2: Code Generation (generates Python code)
   - Stage 3: Manim rendering (creates video)
4. Returns Tool Artifact with video path

IMPORTANT:
- DO NOT generate Python code yourself
- Simply pass the topic/concept name to this tool
- The tool handles all code generation internally

WHAT TO ANIMATE:
- Math: Pythagorean theorem, Taylor series, limits, derivatives
- Algorithms: bubble sort, binary search, Dijkstra's algorithm
- Physics: projectile motion, wave interference, SHM
- Data structures: trees, graphs, stacks, queues
- ML/AI: neural networks, gradient descent

OUTPUT (Tool Artifact as JSON):
Success: {"content": "Animation successfully rendered", "artifact": "/path/to/video.mp4"}
Error: {"content": "Error: [description]", "artifact": null}

The multi-stage approach ensures better LLM reasoning and higher quality animations."""
    )

