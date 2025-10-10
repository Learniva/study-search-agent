"""
Python REPL tool for code execution and mathematical calculations.
"""

from langchain.tools import Tool
from langchain_experimental.utilities import PythonREPL


def get_python_repl_tool() -> Tool:
    """
    Create and return the Python REPL tool.
    
    This tool executes Python code and is useful for:
    - Mathematical calculations
    - Code execution
    - Data processing
    - Algorithm testing
    
    Returns:
        Tool object configured for Python REPL
    """
    python_repl = PythonREPL()
    
    return Tool(
        name="Python_REPL",
        func=python_repl.run,
        description="""Use this tool when you need to:
- Perform mathematical calculations (simple or complex)
- Execute Python code
- Solve computational problems
- Generate data, charts, or perform data analysis
- Test algorithms or code snippets

Input should be valid Python code. Be sure to print() the results you want to see.
Example: print(2 + 2)"""
    )

