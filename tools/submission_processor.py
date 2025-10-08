"""
Submission File Processor for AI Grading Agent.

This tool receives and parses student submissions (text, code, or document content)
from the LangGraph state.

AI Fundamentals Applied:
- LangChain Document Loaders/Parsing: Handle various file formats
- Text extraction and normalization
- Structured parsing for different submission types

Supported formats:
- Plain text (essays, answers)
- Code (Python, Java, C++, JavaScript, etc.)
- Document content (extracted from PDFs, DOCX)
- Structured data (JSON, CSV)
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from langchain.tools import tool
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    CSVLoader,
    JSONLoader
)


class SubmissionProcessor:
    """Process and parse student submissions."""
    
    @staticmethod
    def detect_submission_type(content: str) -> str:
        """
        Detect the type of submission from content.
        
        Returns: essay, code, mcq, structured, or unknown
        """
        # Check for code patterns
        code_patterns = [
            r'def\s+\w+\s*\(',  # Python function
            r'function\s+\w+\s*\(',  # JavaScript function
            r'public\s+(static\s+)?void\s+main',  # Java main
            r'#include\s*<',  # C/C++ include
            r'import\s+\w+',  # Python/Java import
            r'from\s+\w+\s+import',  # Python import
            r'class\s+\w+',  # Class definition
        ]
        
        for pattern in code_patterns:
            if re.search(pattern, content):
                return "code"
        
        # Check for MCQ patterns
        if re.search(r'(Answer|Question)\s*\d+\s*:\s*[A-E]', content, re.IGNORECASE):
            return "mcq"
        
        if re.search(r'Student\s*:\s*[A-E,\s]+', content, re.IGNORECASE):
            return "mcq"
        
        # Check for structured data (JSON/CSV)
        try:
            json.loads(content)
            return "structured"
        except:
            pass
        
        # Check for essay/text (paragraphs)
        paragraphs = content.strip().split('\n\n')
        if len(paragraphs) >= 2 and len(content) > 200:
            return "essay"
        
        # Default to text
        return "text"
    
    @staticmethod
    def extract_code_metadata(code: str) -> Dict[str, Any]:
        """
        Extract metadata from code submission.
        
        Returns: Dictionary with language, functions, classes, imports, etc.
        """
        metadata = {
            "language": "unknown",
            "functions": [],
            "classes": [],
            "imports": [],
            "line_count": len(code.split('\n')),
            "char_count": len(code),
            "has_comments": False,
            "has_docstrings": False
        }
        
        # Detect language
        if re.search(r'def\s+\w+', code):
            metadata["language"] = "python"
        elif re.search(r'public\s+class', code):
            metadata["language"] = "java"
        elif re.search(r'#include', code):
            metadata["language"] = "c/c++"
        elif re.search(r'function\s+\w+|const\s+\w+\s*=', code):
            metadata["language"] = "javascript"
        
        # Extract functions (Python)
        functions = re.findall(r'def\s+(\w+)\s*\(', code)
        metadata["functions"] = functions
        
        # Extract classes
        classes = re.findall(r'class\s+(\w+)', code)
        metadata["classes"] = classes
        
        # Extract imports (Python)
        imports = re.findall(r'(?:import|from)\s+([\w\.]+)', code)
        metadata["imports"] = imports
        
        # Check for comments
        if re.search(r'#|//|/\*|\*/', code):
            metadata["has_comments"] = True
        
        # Check for docstrings (Python)
        if re.search(r'""".*?"""', code, re.DOTALL):
            metadata["has_docstrings"] = True
        
        return metadata
    
    @staticmethod
    def extract_essay_metadata(text: str) -> Dict[str, Any]:
        """
        Extract metadata from essay submission.
        
        Returns: Dictionary with word count, paragraphs, sentences, etc.
        """
        paragraphs = text.strip().split('\n\n')
        sentences = re.split(r'[.!?]+', text)
        words = text.split()
        
        metadata = {
            "word_count": len(words),
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "avg_words_per_sentence": len(words) / len([s for s in sentences if s.strip()]) if sentences else 0,
            "char_count": len(text),
            "has_citations": bool(re.search(r'\(\w+,?\s*\d{4}\)|\[\d+\]', text)),
            "has_quotes": '"' in text or '"' in text or '"' in text
        }
        
        return metadata
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text by removing extra whitespace and formatting.
        """
        # Remove multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Trim
        text = text.strip()
        
        return text


@tool
def process_submission(submission_data: str) -> str:
    """
    Process and parse a student submission from LangGraph state.
    
    This tool receives student work and extracts relevant information for grading.
    It handles various formats: text, code, documents, structured data.
    
    Input format (JSON string):
    {
        "content": "Student's submission content...",
        "file_type": "text|code|pdf|docx|json",
        "metadata": {
            "student_id": "...",
            "assignment": "..."
        }
    }
    
    Or simple format:
    "Student submission text here..."
    
    Returns: JSON with parsed submission, detected type, and metadata
    
    AI Fundamentals: LangChain Document Loaders/Parsing
    """
    processor = SubmissionProcessor()
    
    try:
        # Try to parse as JSON first
        try:
            data = json.loads(submission_data)
            content = data.get("content", "")
            file_type = data.get("file_type", "text")
            input_metadata = data.get("metadata", {})
        except json.JSONDecodeError:
            # Fallback: treat as plain text
            content = submission_data
            file_type = "text"
            input_metadata = {}
        
        if not content:
            return json.dumps({
                "error": "No content provided in submission"
            })
        
        # Normalize content
        normalized_content = processor.normalize_text(content)
        
        # Detect submission type
        detected_type = processor.detect_submission_type(normalized_content)
        
        # Extract type-specific metadata
        type_metadata = {}
        if detected_type == "code":
            type_metadata = processor.extract_code_metadata(normalized_content)
        elif detected_type == "essay" or detected_type == "text":
            type_metadata = processor.extract_essay_metadata(normalized_content)
        
        # Build result
        result = {
            "success": True,
            "submission": {
                "content": normalized_content,
                "detected_type": detected_type,
                "file_type": file_type,
                "metadata": type_metadata
            },
            "input_metadata": input_metadata,
            "processing": {
                "normalized": True,
                "timestamp": "processed"
            }
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Error processing submission: {str(e)}",
            "raw_input": submission_data[:200]
        })


@tool
def load_file_submission(file_path: str) -> str:
    """
    Load a student submission from a file (PDF, DOCX, TXT, etc.).
    
    Uses LangChain document loaders to extract content from various file formats.
    
    Input: File path (string)
    Output: JSON with file content and metadata
    
    AI Fundamentals: LangChain Document Loaders
    """
    processor = SubmissionProcessor()
    
    try:
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return json.dumps({
                "error": f"File not found: {file_path}"
            })
        
        # Determine loader based on file extension
        extension = file_path_obj.suffix.lower()
        
        content = ""
        metadata = {"file": str(file_path), "extension": extension}
        
        if extension == ".pdf":
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            content = "\n\n".join([doc.page_content for doc in documents])
            metadata["pages"] = len(documents)
            
        elif extension in [".docx", ".doc"]:
            loader = Docx2txtLoader(file_path)
            documents = loader.load()
            content = "\n\n".join([doc.page_content for doc in documents])
            
        elif extension == ".txt":
            loader = TextLoader(file_path)
            documents = loader.load()
            content = documents[0].page_content if documents else ""
            
        elif extension == ".csv":
            loader = CSVLoader(file_path)
            documents = loader.load()
            content = "\n".join([doc.page_content for doc in documents])
            
        elif extension == ".json":
            with open(file_path, 'r') as f:
                content = f.read()
            
        else:
            return json.dumps({
                "error": f"Unsupported file type: {extension}"
            })
        
        # Normalize and detect type
        normalized_content = processor.normalize_text(content)
        detected_type = processor.detect_submission_type(normalized_content)
        
        # Extract type-specific metadata
        if detected_type == "code":
            type_metadata = processor.extract_code_metadata(normalized_content)
        elif detected_type == "essay":
            type_metadata = processor.extract_essay_metadata(normalized_content)
        else:
            type_metadata = {}
        
        result = {
            "success": True,
            "submission": {
                "content": normalized_content,
                "detected_type": detected_type,
                "file_metadata": metadata,
                "type_metadata": type_metadata
            }
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Error loading file: {str(e)}"
        })


@tool
def extract_submission_from_state(state_json: str) -> str:
    """
    Extract submission content from LangGraph state.
    
    This tool is designed to work with the grading agent's state,
    extracting the relevant submission data for processing.
    
    Input: JSON string of the LangGraph state
    Output: Extracted submission content
    """
    try:
        state = json.loads(state_json)
        
        # Try to extract submission from various possible keys
        submission = None
        
        if "submission_data" in state:
            submission = state["submission_data"]
        elif "question" in state:
            submission = state["question"]
        elif "content" in state:
            submission = state["content"]
        
        if submission:
            return process_submission(json.dumps(submission) if isinstance(submission, dict) else submission)
        else:
            return json.dumps({
                "error": "No submission found in state",
                "available_keys": list(state.keys())
            })
            
    except json.JSONDecodeError:
        # Not JSON, treat as direct content
        return process_submission(state_json)
    except Exception as e:
        return json.dumps({
            "error": f"Error extracting from state: {str(e)}"
        })


def get_submission_processing_tools():
    """Return all submission processing tools."""
    return [
        process_submission,
        load_file_submission,
        extract_submission_from_state
    ]

