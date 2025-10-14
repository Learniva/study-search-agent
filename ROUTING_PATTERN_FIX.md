# Routing Pattern Fix - Python REPL vs Web Search

## Issue
Tutorial/how-to questions like "How do I implement a simple neural network in Python?" were being incorrectly routed to Python REPL, causing SyntaxErrors.

## Root Cause
The pattern `r'\b(python|execute|run|eval)\b.*\bcode\b'` was too broad. It matched:
- ❌ "How do I implement in **Python**? Provide **code** example" (should go to Web Search)
- ✅ "Execute this **code**" (should go to Python REPL)

The pattern didn't distinguish between:
- **Asking HOW to code** → Web Search needed
- **Executing existing code** → Python REPL needed

## The Fix

### Before (Too Broad)
```python
'Python_REPL': [
    r'\b(calculate|compute|solve)\b.*\d',
    r'\d+\s*[\+\-\*/\^]\s*\d+',
    r'\b(python|execute|run|eval)\b.*\bcode\b',  # ❌ Too broad!
    r'\b(fibonacci|factorial|prime)\b',
],
```

### After (More Specific)
```python
'Python_REPL': [
    # Only match when user wants to EXECUTE code, not when asking HOW to code
    r'\b(calculate|compute|solve)\b.*\d',  # "Calculate 5+3"
    r'\d+\s*[\+\-\*/\^]\s*\d+',            # "2+2" or "5*3"
    r'\b(execute|run|eval)\b.*\b(this|the|following)\b.*\bcode\b',  # "Execute this code"
    r'```python.*```',                     # Code blocks to execute
    r'\b(fibonacci|factorial|prime)\b.*\b(for|of)\b.*\d+',  # "Fibonacci of 10"
],
```

## What Changed

1. **Removed "python" from execute pattern** - Too ambiguous
2. **Added context requirements** - "execute **this/the/following** code" 
3. **Added code block detection** - Actual code in ``` blocks
4. **Made math patterns more specific** - "fibonacci **of** 10" vs generic "fibonacci"

## Routing Decision Table

| Query | Old Route | New Route | Correct? |
|-------|-----------|-----------|----------|
| "What is 2+2?" | Python REPL | Python REPL | ✅ |
| "Calculate 5*3" | Python REPL | Python REPL | ✅ |
| "Execute this code: print(5)" | Python REPL | Python REPL | ✅ |
| "How do I implement X in Python?" | ❌ Python REPL | ✅ Web Search | ✅ |
| "Provide a code example for X" | ❌ Python REPL | ✅ Web Search | ✅ |
| "What is machine learning?" | Web Search | Web Search | ✅ |
| "Fibonacci of 10" | Python REPL | Python REPL | ✅ |

## Test Cases

### ✅ Should Route to Python REPL
- "What is 2+2?"
- "Calculate 15*7"
- "Compute 100/5"
- "Solve 2^8"
- "Execute this code: print('hello')"
- "Run the following code: x=5"
- "Fibonacci of 10"
- "Factorial of 5"

### ✅ Should Route to Web Search
- "How do I implement a neural network in Python?"
- "Provide a code example for sorting"
- "What is the Python syntax for loops?"
- "How to create a function in Python?"
- "Python tutorial for beginners"
- "Explain object-oriented programming"

## Files Modified
- `utils/routing/routing.py` - Updated `STUDY_AGENT_PATTERNS['Python_REPL']`

---
**Status**: ✅ Fixed  
**Date**: October 14, 2025

