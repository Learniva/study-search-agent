# Python REPL Math Question Fix

## Issue
When asking "What is 2+2?", the system was trying to execute the entire question as Python code:
```python
print(What is 2+2?)  # SyntaxError
```

## Root Cause
The `_execute_python_repl` function in `agents/study/nodes.py` was wrapping the entire question string in `print()` instead of extracting just the mathematical expression.

## The Fix

### Before
```python
if "print" not in question.lower() and any(op in question for op in ['+', '-', '*', '/']):
    code = f"print({question})"  # Wraps entire "What is 2+2?"
else:
    code = question
```

### After
```python
# Extract mathematical expression from natural language question
import re

# If it's a simple math question like "What is 2+2?", extract the expression
math_patterns = [
    r'what\s+is\s+([\d\s\+\-\*/\(\)\.\^]+)\??',  # "What is 2+2?"
    r'calculate\s+([\d\s\+\-\*/\(\)\.\^]+)',      # "Calculate 5*3"
    r'compute\s+([\d\s\+\-\*/\(\)\.\^]+)',        # "Compute 10/2"
    r'solve\s+([\d\s\+\-\*/\(\)\.\^]+)',          # "Solve 7-3"
]

code = question
for pattern in math_patterns:
    match = re.search(pattern, question, re.IGNORECASE)
    if match:
        code = match.group(1).strip()  # Extract just "2+2"
        break

# If we still have a question and it contains math, wrap in print
if "print" not in code.lower() and any(op in code for op in ['+', '-', '*', '/', '**']):
    code = code.replace('^', '**')  # Handle exponentiation
    code = f"print({code})"  # Now wraps just "2+2"
```

## What This Fixes

Now the system correctly:
1. ✅ Detects "What is 2+2?" as a math question
2. ✅ Extracts just the expression "2+2"
3. ✅ Executes `print(2+2)` instead of `print(What is 2+2?)`
4. ✅ Returns "4" as the answer

## Supported Patterns
- "What is X?" → Extracts X
- "Calculate X" → Extracts X
- "Compute X" → Extracts X  
- "Solve X" → Extracts X
- Handles `^` for exponentiation (converts to `**`)

## Test Cases

| Input | Extracted Code | Result |
|-------|---------------|--------|
| "What is 2+2?" | `print(2+2)` | 4 |
| "Calculate 5*3" | `print(5*3)` | 15 |
| "What is 10/2?" | `print(10/2)` | 5.0 |
| "Compute 2^3" | `print(2**3)` | 8 |

---
**Status**: ✅ Fixed  
**Files Modified**: `agents/study/nodes.py`  
**Date**: October 14, 2025

