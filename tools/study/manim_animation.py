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
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
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

⚠️  CRITICAL - CLASS NAME REQUIREMENT:
- The class MUST be named EXACTLY "ConceptAnimation" - NO OTHER NAME!
- Do NOT use custom names like "NeuralNetworkAnimation", "CircleAnimation", etc.
- The system validates for "class ConceptAnimation" - any other name will fail!

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
import numpy as np  # ⚠️ REQUIRED for point comparisons!
import random  # ⚠️ REQUIRED if using random.choice(), random.uniform(), etc.!

class ConceptAnimation(VoiceoverScene):  # ⚠️ MUST BE "ConceptAnimation" - DO NOT CHANGE!
    def construct(self):
        # Set up gTTS voice service (fast, reliable, 100+ languages)
        self.set_speech_service(GTTSService(lang="en", tld="com"))
        
        # YOUR CODE GOES HERE
        # Use self.voiceover(text="...") as vo: to add narration
        # For point comparisons: np.allclose(point1, point2) NOT point1.allclose(point2)!
        # If using randomization: import random (already done above)
        # Animations inside the context will sync with speech
```

VOICEOVER USAGE (adds professional narration):
- Wrap animations with voiceover context: with self.voiceover(text="Narration") as vo:
- Animations inside the context sync automatically with speech
- Speech timing stored in vo.duration - use for wait times
- Example: with self.voiceover(text="Let's explore") as vo: self.play(Create(circle))
- Use natural, educational language - avoid technical jargon
- Keep narration concise: 1-2 sentences per voiceover block
- gTTS provides clear, fast narration (much faster than ElevenLabs!)

CRITICAL CONSTRAINTS:
0. EMPTY ANIMATION LISTS (CRITICAL ERROR - ALWAYS CHECK!):
   - NEVER call self.play() with an empty list of animations!
   - This causes: ValueError: Called Scene.play with no animations
   - ALWAYS check if list is non-empty before unpacking with *
   
   ❌ WRONG - Will crash if boxes is empty:
   ```python
   self.play(*[box.animate.set_color(GREEN) for box in boxes])
   ```
   
   ✅ CORRECT - Check before playing:
   ```python
   animations = [box.animate.set_color(GREEN) for box in boxes]
   if animations:  # Check if list is not empty
       self.play(*animations)
   ```
   
   ✅ CORRECT - Alternative with conditional:
   ```python
   if boxes:  # Check if boxes list has items
       self.play(*[box.animate.set_color(GREEN) for box in boxes])
   ```
   
   COMMON SCENARIOS WHERE THIS HAPPENS:
   - At end of algorithms when all elements are processed
   - After removing/fading out all objects
   - When filtering lists that might become empty
   - In loops where objects are consumed/removed
   
   BEST PRACTICE:
   - Always validate lists before using * unpacking in self.play()
   - Check both the container (boxes) and the animations list
   - Add safety checks at the end of algorithms

0.1. COLOR COMPARISON (CRITICAL ERROR - DO NOT USE np.allclose FOR COLORS!):
   - Manim colors can be ManimColor objects, hex strings, or RGB arrays
   - NEVER use np.allclose() to compare colors - causes DTypePromotionError!
   - Colors returned by .get_color() are strings like "#00FF00"
   - np.allclose() expects numeric arrays, NOT strings
   
   ❌ WRONG - Will crash with DTypePromotionError:
   ```python
   if not np.allclose(box.get_color(), COLOR_SORTED):  # CRASHES!
       # This tries to compare strings with np.allclose()
   ```
   
   ✅ CORRECT - Use direct equality or convert to arrays:
   ```python
   # Method 1: Track state instead of comparing colors
   sorted_indices = set()  # Track which boxes are sorted
   sorted_indices.add(i)  # Mark box i as sorted
   
   if i not in sorted_indices:
       box.animate.set_color(ACTIVE_COLOR)
   ```
   
   ✅ CORRECT - Alternative with ManimColor:
   ```python
   # Method 2: Convert to RGB arrays for comparison
   from manim.utils.color import ManimColor
   current_rgb = ManimColor(box.get_color()).to_rgb()
   target_rgb = ManimColor(SORTED_COLOR).to_rgb()
   
   if not np.allclose(current_rgb, target_rgb):
       box.animate.set_color(SORTED_COLOR)
   ```
   
   ✅ CORRECT - Best practice for algorithms:
   ```python
   # Method 3: Use boolean flags/sets to track state
   # Instead of checking colors, track algorithm state explicitly
   is_sorted = [False] * n
   
   # When element is sorted:
   is_sorted[i] = True
   box.animate.set_color(SORTED_COLOR)
   
   # Later check:
   if not is_sorted[i]:
       # Do something with unsorted element
   ```
   
   WHY THIS MATTERS:
   - .get_color() returns hex string like "#00FF00" (StrDType)
   - np.allclose(string, string) fails with DTypePromotionError
   - Color constants (RED, GREEN, etc.) are ManimColor objects
   - Comparing strings with floats causes type promotion error
   
   BEST PRACTICE FOR ALGORITHMS:
   - Track state with boolean lists/sets, NOT by comparing colors
   - Use color changes for visualization, not for logic
   - If you MUST compare colors, convert to RGB arrays first
   - Avoid np.allclose() for color comparison entirely

0.5. ANIMATION SYNTAX (MOST COMMON ERROR - CHECK FIRST!):
   - Modern Manim uses .animate property for transformations
   - NEVER use ApplyMethod with .animate - this causes ValueError!
     * CORRECT: self.play(obj.animate.move_to(point))
     * WRONG: ApplyMethod(obj.animate.move_to(point)) ❌ ValueError!
   - If you want ApplyMethod, pass method reference WITHOUT .animate:
     * CORRECT: self.play(ApplyMethod(obj.move_to, point))
     * WRONG: self.play(ApplyMethod(obj.animate.move_to, point)) ❌
   - For particles/dots moving: Use .animate directly
     * CORRECT: self.play(dot.animate.move_to(target))
     * CORRECT: self.play(LaggedStart(*[d.animate.move_to(p) for d, p in zip(dots, positions)]))
   - BEST PRACTICE: Use .animate syntax (simpler and modern)

1. TEXT STYLING PARAMETERS (CRITICAL ERROR - PREVENT TypeError!):
   
   ⚠️  CRITICAL: t2c, t2s, t2w ONLY work with Text() objects, NEVER with MathTex()! ⚠️
   
   FOR Text() OBJECTS ONLY:
   - t2c (text-to-color): Color parts of text with COLOR values
     * CORRECT: Text("Hello World", t2c={{"Hello": BLUE}}) ✅
     * ONLY for Text(), NOT MathTex()!
   
   - t2s (text-to-style): Maps substring to STYLE DICTIONARIES (not colors!)
     * CORRECT: Text("Hi", t2s={{"Hi": {{"color": BLUE, "font": "Arial"}}}}) ✅
     * WRONG: Text("Hi", t2s={{"Hi": BLUE}}) ❌ AttributeError!
     * ONLY for Text(), NOT MathTex()!
   
   - t2w (text-to-weight): Maps substring to font weights
     * CORRECT: Text("Bold", t2w={{"Bold": BOLD}}) ✅
     * ONLY for Text(), NOT MathTex()!
   
   FOR MathTex() OBJECTS:
   - MathTex does NOT support t2c, t2s, or t2w parameters!
   - NEVER use: MathTex("x^2", t2c={{"x": RED}}) ❌ TypeError!
   - NEVER use: MathTex("y", t2s={{...}}) ❌ TypeError!
   - To color MathTex, use set_color_by_tex() AFTER creation:
     * CORRECT: 
       tex = MathTex("x", "+", "y")
       tex.set_color_by_tex("x", BLUE)
       tex.set_color_by_tex("y", RED)
   - Or just set a single color for entire MathTex:
     * CORRECT: MathTex("x^2 + y^2", color=WHITE) ✅
   
   SUMMARY - AVOID TypeError:
   - Text() objects: Can use t2c, t2s, t2w ✅
   - MathTex() objects: NEVER use t2c, t2s, t2w ❌ Will cause TypeError!
   - If you need colored math: Use set_color_by_tex() after creation

2. OPACITY PARAMETERS (PREVENT ERRORS - VERY IMPORTANT!):
   - NEVER EVER use 'opacity' parameter in ANY Manim constructor! ❌
   - The parameter 'opacity' does NOT exist in Manim v0.19.0!
   
   For Lines (including arrows, vectors):
     * CORRECT: Line(p1, p2, color=WHITE, stroke_opacity=0.5) ✅
     * WRONG: Line(p1, p2, opacity=0.5) ❌ TypeError!
   
   For Circles/Shapes (Circle, Square, Rectangle, Polygon, etc.):
     * CORRECT: Circle(color=BLUE, fill_opacity=0.2, stroke_opacity=1.0) ✅  
     * WRONG: Circle(opacity=0.5) ❌ TypeError!
   
   For Dots (CRITICAL - COMMON ERROR!):
     * CORRECT: Dot(point, radius=0.08, color=BLUE, fill_opacity=0.8) ✅
     * CORRECT: Dot(point, radius=0.08, color=RED, stroke_opacity=0) ✅ (no border)
     * WRONG: Dot(point, radius=0.08, color=BLUE, opacity=0.8) ❌ TypeError!
     * Dot is a shape, so it uses fill_opacity and stroke_opacity
   
   For ALL Manim objects:
     * Use fill_opacity for the interior/fill color transparency
     * Use stroke_opacity for the border/outline transparency
     * NEVER use 'opacity' - it will cause TypeError!

3. POSITIONING & ROTATION METHODS (PREVENT TypeError & AttributeError!):
   
   POSITIONING METHODS:
   - CORRECT centering methods:
     * .move_to(ORIGIN) - Move object to origin (center of screen) ✅
     * .center() - Center the object ✅
     * .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5) - Move to screen edge ✅
     * .shift(direction * distance) - Move by offset ✅
     * .next_to(other, direction, buff=1.0) - Position relative to another object ✅
   
   - ALIGNMENT (CRITICAL - COMMON ERROR!):
     * .align_to(other, direction) - Align with another object ✅
     * NEVER use 'about_edge' parameter - IT DOESN'T EXIST! ❌
     * CORRECT: obj.align_to(other, UP) ✅
     * WRONG: obj.align_to(other, UP, about_edge=ORIGIN) ❌ TypeError!
     * The about_edge parameter was removed in modern Manim versions!
   
   - WRONG methods (will cause AttributeError):
     * .to_center() - Does NOT exist! ❌ AttributeError!
     * .center_on_screen() - Does NOT exist! ❌ AttributeError!
     * Use .move_to(ORIGIN) instead ✅
   
   ROTATION (CRITICAL - PREVENT TypeError!):
   - Text() and other Manim objects do NOT accept 'rotation' parameter in constructor!
   - Use .rotate() METHOD after creation instead:
   
   ```python
   # ✅ CORRECT - Rotate after creation
   label = Text("Y-axis", font_size=24, color=GRAY)
   label.rotate(90 * DEGREES)  # Rotate 90 degrees
   label.next_to(axes.y_axis, LEFT)
   
   # ✅ CORRECT - Alternative with PI
   text = Text("Hello")
   text.rotate(PI / 2)  # Rotate 90 degrees (π/2 radians)
   
   # ❌ WRONG - 'rotation' parameter doesn't exist!
   label = Text("Y-axis", font_size=24, color=GRAY, rotation=90)  # TypeError!
   
   # ❌ WRONG - 'angle' parameter doesn't exist!
   label = Text("Y-axis", angle=90)  # TypeError!
   ```
   
   CORRECT positioning examples:
   ```python
   # ✅ CORRECT - Center at origin
   axes = Axes(...)
   axes.move_to(ORIGIN)  # Works!
   
   # ✅ CORRECT - Alternative centering
   circle = Circle()
   circle.center()  # Also works!
   
   # ✅ CORRECT - Shift down from center
   axes.move_to(ORIGIN).shift(DOWN * 0.5)
   
   # ✅ CORRECT - Rotate text for axis labels
   y_label = Text("Y-axis", font_size=28)
   y_label.rotate(90 * DEGREES)
   y_label.next_to(axes.y_axis, LEFT, buff=0.5)
   
   # ❌ WRONG - Method doesn't exist
   axes.to_center()  # AttributeError!
   ```

4. ALGORITHMIC CORRECTNESS (HIGHEST PRIORITY - MOST IMPORTANT!):
   - For algorithms: SHOW EVERY SINGLE STEP - do NOT skip any iterations!
   - Bubble Sort: Show ALL passes until array is fully sorted
   - Example: If array needs 3 passes to sort, animate ALL 3 passes
   - NEVER say "this repeats" without showing it - SHOW the actual repetitions!
   - Math/Science: Verify formulas are correct before animating
   - Physics: Ensure equations and relationships are accurate
   - ACCURACY > BREVITY - completeness is essential for education
   - If algorithm takes 10 steps, show all 10 steps (not just 1-2 examples)

5. SPATIAL AWARENESS - FIT SCREEN & CENTER PERFECTLY (CRITICAL!):
   
   FRAME DIMENSIONS & SAFE ZONES:
   - Frame size: 14.2 units wide × 8 units tall (centered at ORIGIN)
   - SAFE ZONE: Keep content within ±6 units horizontal, ±3.5 units vertical
   - DANGER ZONE: Never place objects beyond ±7 units horizontal, ±4 units vertical
   - ALWAYS leave MINIMUM 1.0 unit of space between objects
   
   MODERN CENTERING STRATEGIES (MOST IMPORTANT!):
   - DEFAULT POSITION: Always start with .move_to(ORIGIN) for centered layouts
   - For single objects: Use .move_to(ORIGIN) or .center()
   - For groups: Use VGroup, then .move_to(ORIGIN) to center everything
   - Title exception: Only titles use .to_edge(UP, buff=0.5)
   - Everything else: Center vertically and horizontally around ORIGIN
   
   ⚠️  NEVER use .to_center() - it doesn't exist! Use .move_to(ORIGIN) instead!
   
   Example of perfect centering:
   ```
   # Single object - centered
   circle = Circle(radius=2)
   circle.move_to(ORIGIN)  # Perfectly centered!
   
   # Multiple objects - group and center
   diagram = VGroup(obj1, obj2, obj3)
   diagram.arrange(RIGHT, buff=1.0)
   diagram.move_to(ORIGIN)  # All objects centered as a group!
   
   # Title + centered content (modern layout)
   title = Text("Title").to_edge(UP, buff=0.5)
   content = VGroup(...)
   content.move_to(ORIGIN)  # Content stays centered below title
   ```
   
   AUTOMATIC SCALING TO FIT FRAME (PREVENT OVERLAPPING!):
   - Check total width: If VGroup width > 11 units, scale it down!
   - Check total height: If VGroup height > 6 units, scale it down!
   - Use .scale_to_fit_width(10) to ensure horizontal fit
   - Use .scale_to_fit_height(5) to ensure vertical fit
   - After scaling, ALWAYS re-center: .move_to(ORIGIN)
   
   Example automatic fitting:
   ```
   # Create large diagram
   network = VGroup(layer1, layer2, layer3)
   network.arrange(RIGHT, buff=2.0)
   
   # Check and scale to fit
   if network.width > 11:
       network.scale_to_fit_width(10)  # Fit to safe zone
   
   network.move_to(ORIGIN)  # Re-center after scaling
   ```
   
   TEXT POSITIONING - PREVENT OVERLAPPING TEXT:
   - Title at TOP: .to_edge(UP, buff=0.5) - ONLY for main titles!
   - Subtitle/labels: Use .next_to() with proper buff (1.0 minimum)
   - Long text: Use .scale_to_fit_width(11) to prevent going off-screen
   - NEVER place multiple text at same vertical position!
   - When adding new text, ALWAYS FadeOut old text first
   
   Perfect text layout:
   ```
   title = Text("Main Title", font_size=48)
   title.to_edge(UP, buff=0.5)
   
   # Content centered below
   diagram = Circle(radius=2).move_to(ORIGIN)
   
   # Label below diagram (not at top!)
   label = Text("Label", font_size=32)
   label.next_to(diagram, DOWN, buff=1.0)
   
   # Everything fits and is centered!
   ```
   
   FOR HORIZONTAL LAYOUTS (Arrays, Lists):
   - NEVER exceed 10 units total width!
   - Use VGroup.arrange(RIGHT, buff=X) for spacing
   - Always center: .move_to(ORIGIN) after arranging
   - If too wide: Use .scale_to_fit_width(10)
   
   Perfect horizontal layout:
   ```
   boxes = VGroup(*[Square(side_length=1.2) for _ in range(5)])
   boxes.arrange(RIGHT, buff=0.5)
   
   # Ensure it fits
   if boxes.width > 10:
       boxes.scale_to_fit_width(10)
   
   boxes.move_to(ORIGIN)  # Perfectly centered!
   ```
   
   FOR MULTI-LAYER DIAGRAMS (Neural Networks, Flowcharts):
   - Calculate total width: n_layers * spacing (spacing = 3-4 units)
   - If total width > 10 units: Reduce spacing or scale down
   - ALWAYS center the entire network: network.move_to(ORIGIN)
   - Vertical spacing between nodes: 1.2-1.5 units (tight but clear)
   - Place labels BELOW layers with .next_to(layer, DOWN, buff=0.6)
   
   Perfect neural network layout:
   ```
   # 3 layers with proper spacing
   input_layer = VGroup(*[Circle(radius=0.3) for _ in range(3)])
   input_layer.arrange(DOWN, buff=1.2)
   
   hidden_layer = VGroup(*[Circle(radius=0.3) for _ in range(4)])
   hidden_layer.arrange(DOWN, buff=1.2)
   
   output_layer = VGroup(*[Circle(radius=0.3) for _ in range(2)])
   output_layer.arrange(DOWN, buff=1.2)
   
   # Position layers (3 units apart horizontally)
   input_layer.shift(LEFT * 3)
   hidden_layer.move_to(ORIGIN)
   output_layer.shift(RIGHT * 3)
   
   # Group everything and center
   network = VGroup(input_layer, hidden_layer, output_layer)
   
   # Check width and scale if needed
   if network.width > 11:
       network.scale_to_fit_width(10)
   
   network.move_to(ORIGIN)  # Final centering!
   
   # Labels below (not at top!)
   input_label = Text("Input", font_size=28)
   input_label.next_to(input_layer, DOWN, buff=0.6)
   ```
   
   MODERN LAYOUT RULES:
   - Everything centered around ORIGIN (except titles at top)
   - Use VGroup to group related objects, then center the group
   - Always check dimensions before finalizing positions
   - Scale down if needed, then re-center
   - Leave generous margins (0.5-1.0 buff minimum)

6. TIMING & VOICEOVER - SMOOTH PACING (VERY IMPORTANT!):
   - DO NOT use self.wait() inside voiceover blocks - it's automatic!
   - Voiceover blocks handle their own timing based on speech duration
   
   CORRECT voiceover usage:
   ```
   with self.voiceover(text="Short explanation") as vo:
       self.play(Create(obj))
       # NO self.wait() here! Voiceover handles timing automatically
   ```
   
   WRONG voiceover usage:
   ```
   with self.voiceover(text="Explanation") as vo:
       self.play(Create(obj))
       self.wait(2)  # ❌ WRONG! This creates awkward long pauses!
   ```
   
   TIMING RULES:
   - Inside voiceover block: NO self.wait() calls (automatic timing)
   - Outside voiceover block: Use self.wait(0.5) for quick transitions
   - Between major sections: Use self.wait(1) for natural pauses
   - For important concepts: Use self.wait(1.5) if NO voiceover
   - Keep voiceover text concise (1-2 sentences max) for natural pacing
   
   BEST PRACTICE:
   - Use voiceover for explanations (automatic smooth timing)
   - Use self.wait() only between voiceover blocks for transitions
   - Shorter voiceover text = faster, more engaging animations
   
7. CODE STRUCTURE: Follow the plan steps exactly in order

8. ULTRA-MODERN PROFESSIONAL AESTHETICS - USE VARIETY!:
   - MINIMALISTIC, clean design with plenty of negative space
   - USE MULTIPLE COLORS for visual interest and beauty!
   - Different objects should have different colors
   
   CRITICAL - COLOR AND OPACITY METHODS (PREVENT TypeError!):
   - .set_color() ONLY accepts color value, NO opacity parameters! ❌
   - NEVER use: obj.set_color(RED, fill_opacity=0.5) ❌ TypeError!
   - NEVER use: obj.set_color(BLUE, stroke_opacity=0.8) ❌ TypeError!
   
   CORRECT ways to set color AND opacity:
   ```python
   # ✅ Option 1: Set separately
   obj.set_color(RED)
   obj.set_fill(RED, opacity=0.5)
   obj.set_stroke(RED, opacity=0.8)
   
   # ✅ Option 2: Use animate property
   obj.animate.set_color(BLUE)  # Just color, no opacity
   obj.animate.set_fill(BLUE, opacity=0.3)
   
   # ✅ Option 3: Set during creation (BEST)
   circle = Circle(color=RED, fill_opacity=0.5, stroke_opacity=1.0)
   ```
   
   WHEN CHANGING COLORS IN ANIMATIONS:
   - If you need to change BOTH color and opacity:
     * CORRECT: obj.set_fill(color, opacity=value) ✅
     * CORRECT: obj.set_stroke(color, opacity=value) ✅
     * WRONG: obj.set_color(color, fill_opacity=value) ❌
   
   BEAUTIFUL COLOR PALETTE (Use variety - mix and match!):
   IMPORTANT: Use HEX CODES or valid Manim color constants only!
   
  Valid Manim constants: BLUE, RED, GREEN, YELLOW, ORANGE, PURPLE, PINK, TEAL, GOLD, WHITE, GRAY, BLACK
  
  Recommended colors (use hex codes for exact shades):
  * Electric Cyan: "#58C4DD" or BLUE - Great for primary elements, titles
  * Bright Cyan: "#00D9FF" - Perfect for highlights, data flow, particles
  * Mint/Aqua: "#64FFDA" or TEAL - Use for success states, growth, results (NO MINT_GREEN constant!)
   * Vibrant Green: "#4CAF50" or GREEN - Use for positive outcomes, checkmarks
   * Sky Blue: "#2196F3" - Beautiful for backgrounds, layers, containers
   * Soft Purple: "#9C27B0" or PURPLE - Great for contrast, special elements
   * Coral: "#FF6B6B" or RED - Warm accent for important points (NO LIGHT_RED!)
   * Gold: "#FFC107" or GOLD - Use for highlights, special emphasis
   * Orange: "#FF9800" or ORANGE - Warm, energetic accent
   * Pink: "#E91E63" or PINK - Soft, friendly accent
  * Pure White: WHITE - Always good for text, key shapes
  * Soft Gray: "#E0E0E0" or GRAY - Use for subtle elements, connections
  
 ⚠️  CRITICAL - FRAME_WIDTH / FRAME_HEIGHT DO NOT EXIST! (PREVENT NameError!):
 - Manim does NOT have FRAME_WIDTH or FRAME_HEIGHT constants! ❌
 - These variables DO NOT EXIST and will cause NameError!
 - NEVER EVER use:
   * obj.scale_to_fit_width(FRAME_WIDTH - 2) ❌ NameError!
   * obj.set_width(FRAME_WIDTH * 0.8) ❌ NameError!
   * obj.move_to([FRAME_WIDTH/2, 0, 0]) ❌ NameError!
   * ANY reference to FRAME_WIDTH or FRAME_HEIGHT ❌
 - ALWAYS use NUMERIC VALUES instead:
   * obj.scale_to_fit_width(12) ✅ (frame is ~14 units wide)
   * obj.set_width(10) ✅
   * obj.move_to([6, 0, 0]) ✅ (right side of frame)
 - Frame dimensions: ~14 units wide × 8 units tall
 - Common widths: 12 (wide text), 10 (medium), 6 (half screen)
 - REMEMBER: No FRAME_WIDTH, no FRAME_HEIGHT - use numbers ONLY!
 
 ⚠️  CRITICAL - INVALID COLOR NAMES (WILL CAUSE NameError!):
  - NEVER use: LIGHT_RED, DARK_BLUE, LIGHT_BLUE, MINT_GREEN, LIGHT_GREEN, etc. (these don't exist!)
  - ONLY these constants are valid: BLUE, RED, GREEN, YELLOW, ORANGE, PURPLE, PINK, TEAL, GOLD, WHITE, GRAY, BLACK ✅
  - If unsure, ALWAYS use HEX CODES: color="#FF6B6B" (always works) ✅
  - For mint/aqua color: Use "#64FFDA" or TEAL (NOT MINT_GREEN!) ✅
   
   COLOR USAGE STRATEGY (IMPORTANT FOR BEAUTY!):
   - Use 3-5 different colors per animation for visual richness
   - Assign colors by function:
     * Input layer: Bright cyan (#00D9FF)
     * Hidden layer: Purple or Teal
     * Output layer: Mint green (#64FFDA)
     * Connections: Soft gray with low opacity
     * Data particles: Mix of cyan, green, gold
   - Vary colors between similar objects for differentiation
   - Use color gradients conceptually (cool to warm, blue to green)
   
   WHAT TO EMBRACE:
   ✅ Multiple colors (3-5 colors make beautiful animations!)
   ✅ Color variety between layers/sections
   ✅ Soft, semi-transparent fills (fill_opacity=0.1-0.2)
   ✅ Vibrant strokes with moderate opacity
   
   MODERN DESIGN PRINCIPLES:
   - Flat design with subtle depth (use fill_opacity, not gradients)
   - Consistent stroke width: 2-4 (thicker = more modern)
   - Rounded corners where possible: corner_radius=0.2
   - Generous whitespace: buff=0.5-1.0 minimum
   - Hierarchy: Larger = more important (font_size: 48 title, 36 body, 28 labels)
   - Smooth, dynamic transitions: FadeIn, FadeOut, Create, Transform, GrowFromCenter
   - Use LaggedStart for sequential reveals (very beautiful!)
   
   BEAUTIFUL EXAMPLES (Notice the color variety and valid color usage!):
   * Vibrant circle: Circle(radius=1.5, color="#00D9FF", stroke_width=3, fill_opacity=0.15)  # Hex code ✅
   * Elegant shape: Circle(radius=1.2, color=PURPLE, stroke_width=3, fill_opacity=0.2)  # Valid constant ✅
   * Golden accent: Circle(radius=0.8, color=GOLD, stroke_width=4, fill_opacity=0.25)  # Valid constant ✅
   * Coral shape: Circle(radius=0.7, color="#FF6B6B", stroke_width=3, fill_opacity=0.2)  # Use hex, not LIGHT_RED ✅
   * Clean title: Text("Neural Networks", font_size=48, color=WHITE, weight=BOLD)  # Valid constant ✅
   * Colorful label: Text("Input Layer", font_size=32, color="#00D9FF")  # Hex code ✅
   * Beautiful box: RoundedRectangle(width=3, height=2, corner_radius=0.2, color=TEAL, fill_opacity=0.15, stroke_width=3)  # Valid ✅
   * Soft connection: Line(p1, p2, color=GRAY, stroke_width=2, stroke_opacity=0.3)  # Valid constant ✅
   * Colorful dot: Dot(point, radius=0.1, color="#64FFDA", fill_opacity=1.0, stroke_opacity=0)  # Hex code ✅
   
  WRONG COLOR EXAMPLES (Will cause NameError!):
  * Circle(color=LIGHT_RED)  # ❌ LIGHT_RED doesn't exist! Use "#FF6B6B" or RED instead
  * Square(color=DARK_BLUE)  # ❌ DARK_BLUE doesn't exist! Use "#0D47A1" or BLUE instead
  * Line(color=LIGHT_GRAY)  # ❌ LIGHT_GRAY doesn't exist! Use "#E0E0E0" or GRAY instead
  * Dot(color=MINT_GREEN)  # ❌ MINT_GREEN doesn't exist! Use "#64FFDA" or TEAL instead
  * Text(color=LIGHT_GREEN)  # ❌ LIGHT_GREEN doesn't exist! Use "#4CAF50" or GREEN instead
   
   ANIMATION VARIETY FOR BEAUTY:
   - Use different animations: Create(), Write(), FadeIn(), GrowFromCenter()
   - Use LaggedStart() for staggered reveals: LaggedStart(*[Create(obj) for obj in group])
   - Vary animation speeds: run_time=0.5 (fast), run_time=1.5 (smooth emphasis)
   - Mix animation types in same scene for visual interest

9. OBJECTS: Use appropriate Manim primitives
   - Text: Text("string", font_size=36, color=WHITE, weight=BOLD)
     * CRITICAL: 'weight' parameter ONLY works with Text(), NOT MathTex()!
     * weight=BOLD or weight=NORMAL (only for Text objects)
     
     ⚠️  ACCESSING TEXT CONTENT - NEVER use .get_string() (DEPRECATED!):
     * Text objects use .text attribute, NOT .get_string() method! ⚠️
     * .get_string() is DEPRECATED and will cause AttributeError in modern Manim!
     * CORRECT: text_mobj.text  # Returns the string content ✅
     * WRONG: text_mobj.get_string()  # ❌ AttributeError or DeprecationWarning!
     * Example usage:
       - CORRECT: value = int(num_mobj.text) ✅
       - WRONG: value = int(num_mobj.get_string()) ❌
     * When tracking array values: use text_mobj.text to read the number
     
     ⚠️  ROTATION - NEVER use 'rotation' or 'angle' parameters (they don't exist!):
     * Text() does NOT accept 'rotation' or 'angle' in constructor
     * Use .rotate() METHOD after creation:
       - CORRECT: text = Text("Label"); text.rotate(90 * DEGREES) ✅
       - WRONG: Text("Label", rotation=90) ❌ TypeError!
       - WRONG: Text("Label", angle=90) ❌ TypeError!
     * For axis labels: Create text first, then rotate:
       y_label = Text("Y-axis")
       y_label.rotate(90 * DEGREES)
       y_label.next_to(axes.y_axis, LEFT)
     
     TEXT STYLING PARAMETERS - VERY IMPORTANT:
     * t2c (text-to-color): Maps substring to COLOR values
       - CORRECT: Text("Hello World", t2c={{"Hello": BLUE, "World": RED}}) ✅
       - Maps specific words to specific colors
     * t2s (text-to-style): Maps substring to STYLE DICTIONARIES (not colors!)
       - CORRECT: Text("Hello", t2s={{"Hello": {{"color": BLUE, "font": "Arial"}}}}) ✅
       - WRONG: Text("Hello", t2s={{"Hello": BLUE}}) ❌ AttributeError!
       - WRONG: Text("Hello", t2s={{"Hello": "#64FFDA"}}) ❌ AttributeError!
       - If you want to color text, use t2c NOT t2s!
     * t2w (text-to-weight): Maps substring to font weights
       - CORRECT: Text("Bold text", t2w={{"Bold": BOLD}}) ✅
     * BEST PRACTICE: Use t2c for coloring parts of text, avoid t2s unless you need complex styling
   
   - Math: MathTex("x^2 + y^2 = r^2", font_size=48, color=WHITE)
     
     CRITICAL - MathTex RESTRICTIONS:
     * MathTex does NOT accept 'weight' parameter!
       - NEVER use: MathTex(..., weight=BOLD) ❌ TypeError!
     
     * MathTex does NOT accept t2c, t2s, or t2w parameters!
       - NEVER use: MathTex("x^2", t2c={{"x": RED}}) ❌ TypeError!
       - NEVER use: MathTex("y", t2s={{...}}) ❌ TypeError!
       - NEVER use: MathTex("a", t2w={{...}}) ❌ TypeError!
       - These parameters ONLY work with Text(), NOT MathTex()!
     
     * To color parts of MathTex, use set_color_by_tex() AFTER creation:
       - CORRECT:
         tex = MathTex("x", "+", "y")
         tex.set_color_by_tex("x", BLUE)
         tex.set_color_by_tex("y", RED)
     
     * Or use single color for entire MathTex:
       - CORRECT: MathTex("x^2 + y^2", color=WHITE, font_size=48) ✅
     
     * MathTex accepts: font_size, color (single color only)
     * Use font_size only: MathTex("x^2", font_size=48, color=WHITE) ✅
   
   - IMPORTANT: If LaTeX is not available, use Text() instead of MathTex()
   - For simple variables, Text("a") works as well as MathTex("a")
   - Shapes: Circle(), Square(), Polygon(p1, p2, p3, ...)
   - Lines: Line(start_point, end_point, color=WHITE, stroke_width=2, stroke_opacity=0.5)
     * CRITICAL: Use 'stroke_opacity' NOT 'opacity' for lines!
     * Example: Line(p1, p2, color=WHITE, stroke_opacity=0.5) ✅
     * NEVER use: Line(p1, p2, opacity=0.5) ❌ TypeError!
   
   CRITICAL - SIZING OBJECTS:
   - NEVER use FRAME_WIDTH or FRAME_HEIGHT (these don't exist!) ❌
   - Use numeric values: obj.set_width(10) or obj.scale(0.8) ✅
   - Frame is ~14 units wide × 8 units tall
   - To fit text: text.set_width(12) or text.scale_to_fit_width(12) ✅
  - DASHED Lines: DashedLine(start_point, end_point, color=GRAY, stroke_width=2)
    * CRITICAL: Use DashedLine class, NOT dash_length parameter!
    * Example: DashedLine(point1, point2, color=GRAY)
    * NEVER use: Line(..., dash_length=0.2) ❌ This will cause errors!
  
  CRITICAL - NUMPY/POINT COMPARISONS (PREVENT AttributeError!):
  - Points returned by .get_start(), .get_end(), .get_center() are numpy arrays
  - Numpy arrays DO NOT have .allclose() as a method! ❌
  - To compare points, use np.allclose() FUNCTION:
    * CORRECT: if np.allclose(line.get_start(), point): ✅
    * WRONG: if line.get_start().allclose(point): ❌ AttributeError!
  - You MUST import numpy at the top: import numpy as np
  - Other numpy functions: np.array(), np.dot(), np.linalg.norm()
  - NEVER call numpy functions as methods on arrays!
  
  CRITICAL - RANDOM MODULE (PREVENT NameError!):
  - If you use random.choice(), random.uniform(), random.randint(), etc., you MUST import random!
  - You MUST import at the top: import random
  - Common use cases:
    * random.choice([color1, color2, color3]) - Pick random color for variety
    * random.uniform(0.5, 1.5) - Random float for animation timing
    * random.randint(1, 10) - Random integer for data values
  - ALWAYS import random if you use ANY random.* functions! ⚠️
  
  CRITICAL - CODE DISPLAY (PREVENT TypeError!):
  - NEVER use Code() class to display code snippets! ❌
  - The Code class in modern Manim has a completely different API than expected!
  - Code(code="...") will cause TypeError: Code.__init__() got an unexpected keyword argument 'code'
  
  If you need to show code in an animation:
  - ❌ WRONG: Code(code=code_string, ...) - Will crash!
  - ✅ CORRECT: Use Text() with monospace font instead:
    ```python
    code_text = Text(
        'circle = Circle()\\nself.play(Create(circle))',
        font="Courier New",  # Monospace font for code
        font_size=24,
        color=WHITE
    )
    ```
  - ✅ ALTERNATIVE: Use Paragraph() for multi-line code:
    ```python
    from manim import Paragraph
    code_lines = [
        'def bubble_sort(arr):',
        '    for i in range(len(arr)):',
        '        for j in range(len(arr)-1):',
        '            if arr[j] > arr[j+1]:',
        '                arr[j], arr[j+1] = arr[j+1], arr[j]'
    ]
    code_display = Paragraph(
        *code_lines,
        font="Courier New",
        font_size=20,
        color=GREEN,
        line_spacing=0.8
    )
    ```
  - BEST PRACTICE: If showing code is essential, use simple Text objects
  - Focus on visual explanations instead of showing code
  
  - Axes: Axes(x_range=[-5, 5], y_range=[-5, 5], color=WHITE)
   - Graphs: axes.plot(lambda x: x**2, color=BLUE)
   - Groups: VGroup(obj1, obj2, ...)
   - Right Angle: RightAngle(line1, line2, length=0.3) - REQUIRES TWO LINE OBJECTS, NOT POINTS
   - Dots: Dot(point, radius=0.05, color=BLUE)  # Use professional colors!
     * CRITICAL: Dots use 'fill_opacity' and 'stroke_opacity', NOT 'opacity'!
     * CORRECT: Dot(point, radius=0.08, color=BLUE, fill_opacity=0.8) ✅
     * WRONG: Dot(point, radius=0.08, color=BLUE, opacity=0.8) ❌ TypeError!
     * Example: Dot(ORIGIN, radius=0.1, color="#00D9FF", fill_opacity=1.0, stroke_opacity=0)

10. ANIMATIONS: Use smooth, clear animations
   - Create(object) - draw shapes
   - Write(text) - write text
   - FadeIn(object) - fade in
   - FadeOut(object) - fade out
   - Transform(obj1, obj2) - morph one into another
   - ReplacementTransform(obj1, obj2) - replace one object with another
   - GrowFromCenter(object) - grow from center
   - GrowFromPoint(object, point) - grow from specific point
   
   CRITICAL - INVALID TRANSFORMATION METHODS (PREVENT NameError!):
   - TransformFrom() DOES NOT EXIST! ❌
   - TransformTo() DOES NOT EXIST! ❌
   - NEVER use these! They will cause NameError!
   
   CORRECT transformation methods:
   - Transform(source, target) ✅ - morphs source into target
   - ReplacementTransform(source, target) ✅ - replaces source with target
   - FadeTransform(source, target) ✅ - fades while transforming
   - self.play(source.animate.move_to(position)) ✅ - moves object
   
   Example - animating text appearing at position:
   ```python
   # ❌ WRONG (TransformFrom doesn't exist!):
   self.play(TransformFrom(text, position))  # NameError!
   
   # ✅ CORRECT options:
   # Option 1: Create text at position then fade in
   text.move_to(position)
   self.play(FadeIn(text))
   
   # Option 2: Create text elsewhere, then move
   self.play(text.animate.move_to(position))
   
   # Option 3: Use GrowFromPoint
   self.play(GrowFromPoint(text, position))
   ```
   
   CRITICAL - NEVER MIX .animate WITH ANIMATION CLASSES! (PREVENT TypeError!):
   - You CANNOT use .animate inside Write(), Create(), FadeIn(), etc.! ❌
   - This causes: TypeError: object of type '_AnimationBuilder' has no len()
   
   WRONG examples (will crash):
   ```python
   self.play(Write(obj.animate.move_to(point)))      # ❌ TypeError!
   self.play(Create(obj.animate.scale(2)))           # ❌ TypeError!
   self.play(FadeIn(obj.animate.shift(UP)))          # ❌ TypeError!
   ```
   
   CORRECT alternatives:
   ```python
   # Option 1: Create/Write first, THEN animate
   self.play(Write(obj))
   self.play(obj.animate.move_to(point))             # ✅ Correct!
   
   # Option 2: Just use .animate (no Write/Create)
   self.play(obj.animate.move_to(point))             # ✅ Correct!
   
   # Option 3: Create at position first
   obj.move_to(point)
   self.play(Write(obj))                             # ✅ Correct!
   ```
   
   CRITICAL - ANIMATION SYNTAX (Common Error!):
   - Modern Manim uses .animate property for transformations
   - CORRECT: self.play(obj.animate.move_to(point))
   - WRONG: ApplyMethod(obj.animate.move_to(point)) ❌ ValueError!
   - If using ApplyMethod, pass method reference (not .animate):
     * CORRECT: ApplyMethod(obj.move_to, point)
     * WRONG: ApplyMethod(obj.animate.move_to(point)) ❌
   - For multiple animations: self.play(obj1.animate.move_to(p1), obj2.animate.scale(2))
   - For moving particles/dots:
     * CORRECT: self.play(LaggedStart(*[dot.animate.move_to(pos) for dot, pos in zip(dots, positions)]))
     * WRONG: self.play(LaggedStart(*[ApplyMethod(dot.animate.move_to, pos) ...]))  ❌
   - DON'T MIX .animate with ApplyMethod - use one or the other!
   - PREFER .animate syntax (simpler, more modern)

FEW-SHOT EXAMPLES:

Example 1: Simple Formula Display
Plan: {{"main_object": "Quadratic formula", "key_steps": ["Show formula", "Highlight parts"], "text_to_display": ["Quadratic Formula"]}}

Code:
```python
from manim import *
import numpy as np
import random

class ConceptAnimation(Scene):  # ⚠️ ALWAYS use "ConceptAnimation" as class name!
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
import numpy as np
import random

class ConceptAnimation(VoiceoverScene):  # ⚠️ ALWAYS "ConceptAnimation" - NO custom names!
    def construct(self):
        # Set up gTTS voice service (fast and reliable!)
        self.set_speech_service(GTTSService(lang="en", tld="com"))
        
        # Title with narration
        title = Text("Circle", font_size=48)
        title.to_edge(UP)
        
        with self.voiceover(text="Let's explore the circle, one of the most fundamental shapes in geometry.") as vo:
            self.play(Write(title))
        
        self.play(FadeOut(title))
        
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
        
        # Document retrieval is now handled via RAG tools (L2 Vector Store)
        # Animations are generated without direct document context
        self.doc_retriever = None
        print("ℹ️  Manim animations are generated from query context only")
    
    def _check_manim_installation(self) -> bool:
        """
        Check if Manim is properly installed.
        
        Returns:
            True if Manim is available, False otherwise
        """
        try:
            # Use full path from virtual environment
            import sys
            venv_manim = str(Path(sys.executable).parent / 'manim')
            manim_cmd = venv_manim if Path(venv_manim).exists() else 'manim'
            
            result = subprocess.run(
                [manim_cmd, '--version'],
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
                
            # Validate code before rendering
            validation_error = self._validate_animation_code(code)
            if validation_error:
                print(f"⚠️  Code validation failed: {validation_error}")
                
                # Create error log
                error_log = os.path.join(self.output_dir, "validation_error.txt")
                try:
                    with open(error_log, 'w') as f:
                        f.write(f"Validation error for topic: {topic}\n")
                        f.write(f"Error: {validation_error}\n")
                        f.write(f"Code:\n{code}\n")
                        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                except Exception as log_error:
                    print(f"Could not write error log: {log_error}")
                
                return {
                    "status": "error",
                    "error": f"Code validation failed: {validation_error}",
                    "code": code,
                    "video_path": None,
                    "validation_error": validation_error,
                    "error_log": error_log if 'error_log' in locals() else None
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
                
                # Run Manim command (use full path from virtual environment)
                import sys
                venv_manim = str(Path(sys.executable).parent / 'manim')
                cmd = [
                    venv_manim if Path(venv_manim).exists() else 'manim',
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
                    
                    # Parse error for more helpful message
                    parsed_error = self._parse_manim_error(error_msg)
                    
                    # Create error log
                    error_log = os.path.join(self.output_dir, f"manim_error_{safe_topic}.txt")
                    try:
                        with open(error_log, 'w') as f:
                            f.write(f"Manim error for topic: {topic}\n")
                            f.write(f"Parsed error: {parsed_error}\n")
                            f.write(f"Command: {' '.join(cmd)}\n")
                            f.write(f"Return code: {result.returncode}\n")
                            f.write(f"Full error message:\n{error_msg}\n")
                            f.write(f"Code:\n{code}\n")
                            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                    except Exception as log_error:
                        print(f"Could not write error log: {log_error}")
                    
                    return {
                        "status": "error",
                        "error": parsed_error,
                        "full_error": error_msg[:500] + ("..." if len(error_msg) > 500 else ""),
                        "code": code,
                        "video_path": None,
                        "error_type": "manim_error",
                        "error_log": error_log if 'error_log' in locals() else None
                    }
                
                # Find the generated video file
                video_files = list(self.output_dir.rglob(f"{output_file}.mp4"))
                
                if not video_files:
                    error_msg = "Video file not found after rendering"
                    print(f"❌ {error_msg}")
                    
                    # Create error log
                    error_log = os.path.join(self.output_dir, f"missing_video_{safe_topic}.txt")
                    try:
                        with open(error_log, 'w') as f:
                            f.write(f"Missing video error for topic: {topic}\n")
                            f.write(f"Error: {error_msg}\n")
                            f.write(f"Expected file pattern: {output_file}.mp4\n")
                            f.write(f"Output directory: {self.output_dir}\n")
                            f.write(f"Directory contents: {os.listdir(self.output_dir)}\n")
                            f.write(f"Manim output directory: {os.path.join(self.output_dir, 'videos')}\n")
                            if os.path.exists(os.path.join(self.output_dir, 'videos')):
                                f.write(f"Manim videos directory contents: {os.listdir(os.path.join(self.output_dir, 'videos'))}\n")
                            f.write(f"Command: {' '.join(cmd)}\n")
                            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                    except Exception as log_error:
                        print(f"Could not write error log: {log_error}")
                    
                    return {
                        "status": "error",
                        "error": error_msg,
                        "code": code,
                        "video_path": None,
                        "error_type": "missing_video",
                        "error_log": error_log if 'error_log' in locals() else None
                    }
                
                video_path = str(video_files[0])
                
                # Also copy to a cleaner downloads directory for easy access
                downloads_dir = Path("downloads/animations")
                downloads_dir.mkdir(parents=True, exist_ok=True)
                
                # Create a clean filename
                import shutil
                # datetime is already imported at the top of the file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                clean_filename = f"{output_file}_{timestamp}.mp4"
                download_path = downloads_dir / clean_filename
                
                try:
                    shutil.copy2(video_path, download_path)
                    print(f"✅ Animation created successfully!")
                    print(f"📁 Saved to: {video_path}")
                    print(f"📥 Also copied to: {download_path} (easier to find!)")
                except Exception as e:
                    print(f"⚠️  Could not copy to downloads: {e}")
                    download_path = video_path
                
                return {
                    "status": "success",
                    "video_path": str(download_path),  # Return the easier-to-access path
                    "original_path": video_path,
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
            error_msg = "Animation rendering timed out (exceeded 5 minutes). Script may be too complex."
            print(f"❌ {error_msg}")
            
            # Create error log
            error_log = os.path.join(self.output_dir, f"timeout_error_{int(datetime.now().timestamp())}.txt")
            try:
                with open(error_log, 'w') as f:
                    f.write(f"Timeout error for topic: {topic}\n")
                    f.write(f"Error: {error_msg}\n")
                    f.write(f"Topic: {topic}\n")
                    if 'code' in locals():
                        f.write(f"Code:\n{code}\n")
                    if 'cmd' in locals():
                        f.write(f"Command: {' '.join(cmd)}\n")
                    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            except Exception as log_error:
                print(f"Could not write error log: {log_error}")
            
            return {
                "status": "error",
                "error": error_msg,
                "code": code if 'code' in locals() else None,
                "video_path": None,
                "error_type": "timeout",
                "error_log": error_log if 'error_log' in locals() else None
            }
        except Exception as e:
            error_msg = f"Error creating animation: {str(e)}"
            print(f"❌ {error_msg}")
            traceback_str = traceback.format_exc()
            print(traceback_str)
            
            # Create error log
            error_log = os.path.join(self.output_dir, f"exception_{int(datetime.now().timestamp())}.txt")
            try:
                with open(error_log, 'w') as f:
                    f.write(f"Exception for topic: {topic}\n")
                    f.write(f"Error: {error_msg}\n")
                    f.write(f"Topic: {topic}\n")
                    f.write(f"Traceback:\n{traceback_str}\n")
                    if 'code' in locals():
                        f.write(f"Code:\n{code}\n")
                    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            except Exception as log_error:
                print(f"Could not write error log: {log_error}")
            
            return {
                "status": "error",
                "error": error_msg,
                "traceback": traceback_str,
                "code": code if 'code' in locals() else None,
                "video_path": None,
                "error_type": "exception",
                "error_log": error_log if 'error_log' in locals() else None
            }
    
    def _validate_animation_code(self, code: str) -> Optional[str]:
        """
        Pre-validate animation code for common errors.
        
        Args:
            code: Manim Python code
            
        Returns:
            Error message if validation fails, None otherwise
        """
        # Check for required imports
        if "from manim import" not in code:
            return "Missing required import: 'from manim import *'"
        
        # Check for required class
        if "class ConceptAnimation" not in code:
            return "Missing required class: 'class ConceptAnimation'"
        
        # Check for construct method
        if "def construct(self)" not in code:
            return "Missing required method: 'def construct(self)'"
        
        # Check for common syntax errors
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            return f"Syntax error: {e}"
        
        # Check for common Manim errors
        common_errors = [
            # Wrong method names
            {"pattern": r"\.to_center\(", "message": "Method .to_center() doesn't exist, use .move_to(ORIGIN) instead"},
            {"pattern": r"\.center_on_screen\(", "message": "Method .center_on_screen() doesn't exist, use .move_to(ORIGIN) instead"},
            
            # Constructor parameter errors
            {"pattern": r"Text\([^)]*rotation\s*=", "message": "Text() doesn't accept 'rotation' parameter, use .rotate() method after creation"},
            {"pattern": r"Text\([^)]*angle\s*=", "message": "Text() doesn't accept 'angle' parameter, use .rotate() method after creation"},
            
            # Missing parentheses
            {"pattern": r"self\.play\s+[A-Za-z]", "message": "Missing parentheses in self.play call"},
            
            # Incorrect animation names
            {"pattern": r"self\.play\(Show\(", "message": "Animation 'Show' doesn't exist, use 'Write', 'Create', or 'FadeIn' instead"},
            {"pattern": r"self\.play\(Hide\(", "message": "Animation 'Hide' doesn't exist, use 'FadeOut' instead"},
            
            # Incorrect color format
            {"pattern": r"color\s*=\s*['\"]#[^'\"]{1,5}['\"]", "message": "Invalid hex color format, should be #RRGGBB"},
        ]
        
        for error in common_errors:
            if re.search(error["pattern"], code):
                return error["message"]
        
        return None
    
    def _parse_manim_error(self, error_message: str) -> str:
        """
        Parse Manim error message to provide more helpful feedback.
        
        Args:
            error_message: Raw error message from Manim
            
        Returns:
            User-friendly error message
        """
        # Common error patterns and friendly messages
        error_patterns = [
            # AttributeError patterns
            {
                "pattern": r"AttributeError: 'Text' object has no attribute 'to_center'",
                "message": "Error: The Text object doesn't have a 'to_center' method. Use .move_to(ORIGIN) instead."
            },
            {
                "pattern": r"AttributeError: 'Text' object has no attribute 'center_on_screen'",
                "message": "Error: The Text object doesn't have a 'center_on_screen' method. Use .move_to(ORIGIN) instead."
            },
            {
                "pattern": r"AttributeError: module 'manim' has no attribute '(\w+)'",
                "message": "Error: Manim doesn't have an attribute '{}'."
            },
            
            # TypeError patterns
            {
                "pattern": r"TypeError: Text.__init__\(\) got an unexpected keyword argument '(\w+)'",
                "message": "Error: Text() doesn't accept '{}' as a parameter."
            },
            {
                "pattern": r"TypeError: (\w+)\.__init__\(\) got an unexpected keyword argument '(\w+)'",
                "message": "Error: {}() doesn't accept '{}' as a parameter."
            },
            
            # ImportError patterns
            {
                "pattern": r"ImportError: cannot import name '(\w+)' from 'manim'",
                "message": "Error: '{}' is not available in manim."
            },
            
            # NameError patterns
            {
                "pattern": r"NameError: name '(\w+)' is not defined",
                "message": "Error: '{}' is not defined. Check for typos or missing imports."
            }
        ]
        
        # Check each pattern
        for pattern in error_patterns:
            match = re.search(pattern["pattern"], error_message)
            if match:
                # Format the message with captured groups
                if match.groups():
                    return pattern["message"].format(*match.groups())
                else:
                    return pattern["message"]
        
        # If no specific pattern matches, extract the most relevant part
        # Look for the first traceback line with an error
        error_lines = error_message.split('\n')
        for line in error_lines:
            if "Error:" in line:
                return f"Manim error: {line.strip()}"
        
        # If all else fails, return a generic message with the first few lines
        short_error = '\n'.join(error_lines[:5]) if len(error_lines) > 5 else error_message
        return f"Manim rendering failed: {short_error}"
        
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
            
            # Validate code
            validation_error = self._validate_animation_code(code)
            if validation_error:
                print(f"⚠️  Code validation warning: {validation_error}")
                print("   The code may still work, but could have issues.")
        
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
        
        # Use full path from virtual environment
        import sys
        venv_manim = str(Path(sys.executable).parent / 'manim')
        manim_cmd = venv_manim if Path(venv_manim).exists() else 'manim'
        
        cmd = [
            manim_cmd,
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
            
            # Also copy to a cleaner downloads directory for easy access
            downloads_dir = Path("downloads/animations")
            downloads_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a clean filename
            import shutil
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_filename = f"{output_file}_{timestamp}.mp4"
            download_path = downloads_dir / clean_filename
            
            try:
                shutil.copy2(video_path, download_path)
                print(f"✓ Video saved to: {video_path}")
                print(f"📥 Also copied to: {download_path} (easier to find!)")
                final_path = str(download_path)
            except Exception as e:
                print(f"⚠️  Could not copy to downloads: {e}")
                final_path = video_path
            
            # Return Tool Artifact: (content, artifact=video_path)
            # The artifact is the deliverable Video File (.mp4)
            # In the future, UI can use this path to display/download the video
            return json.dumps({
                "content": f"Animation successfully rendered and saved to {final_path}",
                "artifact": final_path  # Video File (.mp4) - the deliverable
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

