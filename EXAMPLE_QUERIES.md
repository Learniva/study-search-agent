# Example Queries - Study Search Agent

A comprehensive collection of example queries organized by complexity and feature testing. Use these to test and demonstrate the system's capabilities.

---

## 📋 Table of Contents
1. [Simple Queries](#simple-queries)
2. [Web Search Queries](#web-search-queries)
3. [Code Generation Queries](#code-generation-queries)
4. [Multi-Step Complex Queries](#multi-step-complex-queries)
5. [Educational Content Generation](#educational-content-generation)
6. [Streaming Test Queries](#streaming-test-queries)
7. [Edge Cases & Special Scenarios](#edge-cases--special-scenarios)

---

## 🟢 Simple Queries
*Fast, direct responses without web search or complex processing*

### Math & Calculations
```
What is 2+2?
```
**Expected**: Direct answer "4" via Python REPL

```
Calculate 15 * 7
```
**Expected**: Direct calculation result

```
What is 100 divided by 5?
```
**Expected**: Mathematical result

```
Solve 2^8
```
**Expected**: Exponentiation result (256)

### Simple Definitions
```
What is photosynthesis?
```
**Expected**: Quick web search, concise definition with sources

```
Define machine learning
```
**Expected**: Brief explanation with authoritative sources

---

## 🔍 Web Search Queries
*Questions that require internet search with source citations*

### Current Information
```
What are the latest developments in quantum computing in 2024?
```
**Expected**: 
- Web search (Tavily fallback)
- 3-5 authoritative sources
- Recent, relevant information
- References section with URLs

### Comparison Questions
```
What is the difference between machine learning and deep learning? Include examples of each.
```
**Expected**:
- Clear comparison structure
- Multiple examples
- Inline citations [1], [2], [3]
- Sources section at bottom

### Research Topics
```
Explain quantum entanglement and provide 3 real-world applications with examples
```
**Expected**:
- Comprehensive explanation
- 3 specific applications
- Real-world examples
- Multiple sources cited

### Current Events & Impact
```
Explain the impact of artificial intelligence on healthcare in 2024
```
**Expected**:
- Recent developments
- Real-world impact
- Healthcare-specific sources
- Current year context

---

## 💻 Code Generation Queries
*Questions requesting implementation and code examples*

### Simple Implementations
```
How do I implement a simple neural network in Python? Provide a basic code example.
```
**Expected**:
- Conceptual explanation
- **Complete working code** in ```python``` blocks
- Inline comments
- Source citations (e.g., Medium article, RealPython)

```
Provide code example for binary search in Python
```
**Expected**:
- Algorithm explanation
- Working code implementation
- Complexity analysis
- Sources

### Tutorial Requests
```
How to create a REST API in Python using FastAPI?
```
**Expected**:
- Step-by-step guide
- Code examples with imports
- Endpoint definitions
- Best practices
- Documentation links

```
Write a function to calculate Fibonacci sequence
```
**Expected**:
- Multiple approaches (recursive, iterative)
- Code examples
- Explanation of each approach

### Framework-Specific
```
How do I build a simple React component for a todo list?
```
**Expected**:
- React component code
- State management example
- JSX syntax
- Modern React hooks

---

## 🎯 Multi-Step Complex Queries
*Tasks requiring planning, multiple tool uses, and synthesis*

### Multi-Part Requests
```
Explain linear regression, provide the mathematical formula, and show a Python implementation with a real-world example
```
**Expected**:
- **Step 1**: Concept explanation
- **Step 2**: Mathematical formula
- **Step 3**: Python implementation
- **Step 4**: Real-world example
- Synthesis of all parts
- Multiple sources

### Comparative Analysis with Code
```
Compare supervised learning vs unsupervised learning with 3 examples of each and provide code examples for both
```
**Expected**:
- Detailed comparison
- 6 total examples (3 each)
- Code for both paradigms
- Synthesis of concepts
- Educational sources

### End-to-End Tutorials
```
How do I create a machine learning model to predict house prices? Include data preprocessing, model training, and evaluation steps with code.
```
**Expected**:
- Multiple workflow steps
- Code for each phase
- Explanations throughout
- Best practices
- Complete pipeline

---

## 📚 Educational Content Generation
*Lesson plans, flashcards, study materials*

### Lesson Plans
```
Create a lesson plan on Linear Regression with 15 flashcards
```
**Expected**:
- Structured lesson plan
- Learning objectives
- Key concepts
- Activities
- 15 flashcards
- **References section**

```
Create a lesson plan on photosynthesis with 10 flashcards
```
**Expected**:
- Grade-appropriate content
- Lesson structure
- 10 flashcards
- Educational sources

### Study Guides
```
Generate a comprehensive study guide on neural networks including key concepts, examples, and practice questions
```
**Expected**:
- Organized study guide
- Key terminology
- Visual concepts
- Practice problems
- Resources

### MCQ Generation
```
Create 10 multiple choice questions about Python data structures with explanations
```
**Expected**:
- 10 MCQs
- 4 options each
- Correct answer indicated
- Explanation for each

---

## 🌊 Streaming Test Queries
*Specifically designed to test streaming functionality*

### Simple Streaming Test
```
What is artificial intelligence?
```
**Expected Streaming Indicators**:
- 🔍 SEARCHING (web search triggered)
- 🧠 ANALYZING (processing results)
- ✍️ SYNTHESIZING (creating response)
- ✅ COMPLETE

### Complex Streaming Test
```
Explain the difference between supervised, unsupervised, and reinforcement learning. Provide 2 examples for each and explain when to use each approach.
```
**Expected Streaming Indicators**:
- 🧠 THINKING (task analysis)
- 📋 PLANNING (multi-step plan)
- 🔍 SEARCHING (web search - multiple times)
- 🧠 ANALYZING (processing each search)
- ⚙️ EXECUTING (running plan steps)
- ✍️ SYNTHESIZING (combining results)
- 📝 GENERATING (final answer)
- ✅ COMPLETE

**Expected Streaming Behavior**:
- Progressive text appearance
- Real-time updates
- Visible workflow stages
- Token-by-token delivery
- Sources at the end

### Multi-Step Streaming Test
```
Create a comprehensive guide on building a neural network from scratch: explain the math, provide Python code, create visualizations description, and include 5 practice exercises
```
**Expected Streaming Indicators**:
- 🧠 THINKING
- 📋 PLANNING (complex task detected)
- 🔍 SEARCHING (multiple searches)
- ⚙️ EXECUTING (each step)
- 💻 GENERATING (code generation)
- ✍️ SYNTHESIZING (combining all parts)
- ✅ COMPLETE

**Expected Streaming Behavior**:
- Multiple workflow stages
- Long-form progressive delivery
- Code blocks appearing gradually
- Section-by-section construction

### Code Generation Streaming
```
How do I implement gradient descent algorithm in Python? Provide step-by-step code with visualizations.
```
**Expected Streaming Indicators**:
- 🔍 SEARCHING (finding resources)
- 🧠 ANALYZING (understanding requirements)
- 💻 GENERATING (code generation)
- ✍️ SYNTHESIZING (final answer)

**Expected Streaming Behavior**:
- Explanation streams first
- Code blocks appear progressively
- Comments added in real-time
- Sources appear last

---

## 🎨 Edge Cases & Special Scenarios

### Follow-up Questions
```
# First question:
What is quantum computing?

# Follow-up:
Who invented it?
```
**Expected**: System should understand "it" refers to quantum computing from context

### Time-Sensitive Queries
```
What is the current weather in New York?
```
**Expected**: 
- Search results
- **Disclaimer** about real-time information
- Recommendation to check live sources

### Ambiguous Queries
```
Tell me about Python
```
**Expected**: Should clarify or default to programming language (not the snake)

### Multi-Language Code
```
Show me how to implement a stack in Python, JavaScript, and Java
```
**Expected**:
- Three separate code implementations
- Comparison notes
- Language-specific considerations

---

## 📊 Testing Checklist

Use this checklist when testing queries:

### ✅ For All Queries:
- [ ] Response is relevant and accurate
- [ ] Language is clear and educational
- [ ] No errors or exceptions

### ✅ For Web Search Queries:
- [ ] Web search was triggered (see console logs)
- [ ] Fallback to Tavily worked (if Google API expired)
- [ ] **Sources/References section present**
- [ ] URLs are included (not just titles)
- [ ] 3-5 quality sources cited
- [ ] Inline citations [1], [2], [3] in text

### ✅ For Code Queries:
- [ ] **Actual code provided** (not just descriptions)
- [ ] Code is in proper markdown blocks (```python)
- [ ] Code includes comments
- [ ] Code appears complete and runnable
- [ ] Explanation provided before/after code

### ✅ For Streaming Queries:
- [ ] Response appears progressively (not all at once)
- [ ] Streaming indicators visible in console
- [ ] Workflow stages shown (THINKING, SEARCHING, etc.)
- [ ] Token-by-token delivery observed
- [ ] Final COMPLETE indicator shown

### ✅ For Complex Queries:
- [ ] Multi-step plan created (for complex tasks)
- [ ] Each step executed properly
- [ ] Results synthesized coherently
- [ ] All requirements addressed
- [ ] Sources from all steps preserved

---

## 🚀 Quick Test Sequences

### 5-Minute Quick Test
Run these 5 queries to verify core functionality:
1. `What is 2+2?` (Math - Python REPL)
2. `What is machine learning?` (Simple web search)
3. `How to implement bubble sort in Python?` (Code generation)
4. `Create a lesson plan on gravity with 5 flashcards` (Educational content)
5. `Explain quantum entanglement with examples` (Complex with sources)

### 15-Minute Comprehensive Test
Run the Quick Test plus:
6. `Compare Python and JavaScript for web development` (Comparison)
7. `What are the latest AI developments in 2024?` (Current events)
8. `Build a simple web scraper in Python with code` (Tutorial with code)
9. `Explain supervised vs unsupervised learning with 3 examples each` (Multi-part)
10. `Create a neural network tutorial with math, code, and exercises` (Complex multi-step)

### Streaming-Focused Test
Run these to specifically test streaming:
1. `What is AI?` (Simple streaming)
2. `Explain machine learning types with examples` (Medium complexity)
3. `Create comprehensive guide on neural networks with code` (Complex streaming)
4. Watch console for indicators: THINKING, SEARCHING, ANALYZING, SYNTHESIZING, COMPLETE

---

## 💡 Pro Tips

1. **Watch the Console**: Streaming indicators and search fallbacks are logged there
2. **Source Citation**: Every web search query should end with References/Sources
3. **Code Generation**: Questions with "how to", "implement", "example" should produce code
4. **Progressive Delivery**: Longer responses should appear gradually, not all at once
5. **Pattern Routing**: Simple queries use pattern-based routing (faster, no LLM call)

---

## 📝 Notes

- **Google Custom Search API**: Currently expired, system auto-falls back to Tavily
- **Streaming**: Works in both CLI and API (Server-Sent Events)
- **Role-Based**: Some features differ between student and professor roles
- **Source Quality**: System prioritizes .edu, .gov, .org, Wikipedia over blogs

---

**Last Updated**: October 14, 2025  
**Version**: 2.0 - Enhanced with source citations, code generation, and streaming

