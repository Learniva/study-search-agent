"""
Rubric Retrieval Tool using RAG/ML (ChromaDB).

This tool implements a RAG system for fetching grading rubrics from a vector database.
Rubrics are stored in ChromaDB and retrieved based on semantic similarity to the assignment.

AI Fundamentals Applied:
- RAG/ML: Ensures grading is consistent and verifiable against predefined standards
- Vector embeddings: Semantic search for relevant rubrics
- ChromaDB: Persistent vector store for rubric templates
"""

import os
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

from langchain.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

# Global rubric store
_rubric_vectorstore: Optional[Chroma] = None
_rubric_embeddings: Optional[GoogleGenerativeAIEmbeddings] = None


def initialize_rubric_store(rubrics_dir: str = "rubrics") -> bool:
    """
    Initialize the rubric vector store with ChromaDB.
    
    This loads rubric templates from JSON files and indexes them for semantic search.
    
    Args:
        rubrics_dir: Directory containing rubric JSON files
        
    Returns:
        bool: True if initialization successful
    """
    global _rubric_vectorstore, _rubric_embeddings
    
    try:
        # Check if rubrics directory exists
        rubrics_path = Path(rubrics_dir)
        if not rubrics_path.exists():
            print(f"Rubrics directory not found: {rubrics_dir}")
            print("Creating default rubrics directory...")
            rubrics_path.mkdir(parents=True, exist_ok=True)
            create_default_rubrics(rubrics_dir)
        
        # Load rubric files
        rubric_documents = []
        rubric_files = list(rubrics_path.glob("*.json"))
        
        if not rubric_files:
            print("No rubric files found. Creating default rubrics...")
            create_default_rubrics(rubrics_dir)
            rubric_files = list(rubrics_path.glob("*.json"))
        
        print(f"Loading {len(rubric_files)} rubric templates...")
        
        for rubric_file in rubric_files:
            try:
                with open(rubric_file, 'r') as f:
                    rubric_data = json.load(f)
                
                # Create searchable text from rubric
                rubric_text = f"""
Rubric Name: {rubric_data.get('name', 'Unknown')}
Type: {rubric_data.get('type', 'general')}
Description: {rubric_data.get('description', '')}
Max Score: {rubric_data.get('max_score', 100)}
Criteria: {', '.join([c.get('name', '') for c in rubric_data.get('criteria', [])])}
Full Details: {json.dumps(rubric_data, indent=2)}
"""
                
                # Create document with metadata
                doc = Document(
                    page_content=rubric_text,
                    metadata={
                        "rubric_id": rubric_data.get("id", rubric_file.stem),
                        "name": rubric_data.get("name", "Unknown"),
                        "type": rubric_data.get("type", "general"),
                        "file": str(rubric_file),
                        "source": "local_rubric_store"
                    }
                )
                rubric_documents.append(doc)
                
            except Exception as e:
                print(f"Error loading rubric {rubric_file}: {e}")
        
        if not rubric_documents:
            print("No rubrics loaded. Rubric retrieval will not be available.")
            return False
        
        # Initialize embeddings
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key or google_api_key == "test-key-placeholder":
            print("Valid GOOGLE_API_KEY not found. Cannot initialize rubric embeddings.")
            return False
        
        print("Creating embeddings for rubrics...")
        _rubric_embeddings = GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            google_api_key=google_api_key
        )
        
        # Create vector store
        print("Storing rubrics in ChromaDB...")
        _rubric_vectorstore = Chroma.from_documents(
            documents=rubric_documents,
            embedding=_rubric_embeddings,
            persist_directory=".chroma_rubrics",
            collection_name="grading_rubrics"
        )
        
        print(f"Rubric store initialized with {len(rubric_documents)} templates")
        return True
        
    except Exception as e:
        print(f"Error initializing rubric store: {e}")
        return False


def create_default_rubrics(rubrics_dir: str):
    """Create default rubric templates."""
    rubrics_path = Path(rubrics_dir)
    rubrics_path.mkdir(parents=True, exist_ok=True)
    
    default_rubrics = [
        {
            "id": "essay_general",
            "name": "General Essay Rubric",
            "type": "essay",
            "description": "Standard rubric for essay grading",
            "max_score": 100,
            "criteria": [
                {
                    "name": "Thesis Statement",
                    "weight": 0.20,
                    "description": "Clear, arguable thesis that guides the essay",
                    "levels": {
                        "Excellent (90-100)": "Compelling, sophisticated thesis that shows deep understanding",
                        "Good (80-89)": "Clear thesis that is arguable and appropriate",
                        "Satisfactory (70-79)": "Thesis present but could be stronger or clearer",
                        "Needs Improvement (60-69)": "Weak or unclear thesis",
                        "Unsatisfactory (<60)": "No clear thesis statement"
                    }
                },
                {
                    "name": "Evidence & Support",
                    "weight": 0.30,
                    "description": "Use of relevant evidence to support arguments",
                    "levels": {
                        "Excellent (90-100)": "Exceptional use of relevant, well-integrated evidence",
                        "Good (80-89)": "Strong evidence that supports main points",
                        "Satisfactory (70-79)": "Adequate evidence, but could be stronger",
                        "Needs Improvement (60-69)": "Insufficient or poorly integrated evidence",
                        "Unsatisfactory (<60)": "Little to no relevant evidence"
                    }
                },
                {
                    "name": "Organization",
                    "weight": 0.25,
                    "description": "Logical structure and flow of ideas",
                    "levels": {
                        "Excellent (90-100)": "Exceptional organization with smooth transitions",
                        "Good (80-89)": "Clear organization with logical progression",
                        "Satisfactory (70-79)": "Basic organization, some awkward transitions",
                        "Needs Improvement (60-69)": "Poor organization, hard to follow",
                        "Unsatisfactory (<60)": "No clear organization"
                    }
                },
                {
                    "name": "Grammar & Style",
                    "weight": 0.25,
                    "description": "Writing mechanics and style",
                    "levels": {
                        "Excellent (90-100)": "Virtually error-free, sophisticated style",
                        "Good (80-89)": "Few errors, appropriate style",
                        "Satisfactory (70-79)": "Some errors, basic style",
                        "Needs Improvement (60-69)": "Many errors that distract from content",
                        "Unsatisfactory (<60)": "Pervasive errors"
                    }
                }
            ]
        },
        {
            "id": "code_review_general",
            "name": "General Code Review Rubric",
            "type": "code",
            "description": "Standard rubric for code evaluation",
            "max_score": 100,
            "criteria": [
                {
                    "name": "Correctness",
                    "weight": 0.40,
                    "description": "Code produces correct output for all test cases",
                    "levels": {
                        "Excellent (90-100)": "Correct for all cases including edge cases",
                        "Good (80-89)": "Correct for most cases, minor edge case issues",
                        "Satisfactory (70-79)": "Mostly correct, some logical errors",
                        "Needs Improvement (60-69)": "Significant correctness issues",
                        "Unsatisfactory (<60)": "Does not work correctly"
                    }
                },
                {
                    "name": "Code Quality",
                    "weight": 0.30,
                    "description": "Style, readability, and best practices",
                    "levels": {
                        "Excellent (90-100)": "Exceptional style, highly readable",
                        "Good (80-89)": "Good style, follows best practices",
                        "Satisfactory (70-79)": "Acceptable style, some issues",
                        "Needs Improvement (60-69)": "Poor style, hard to read",
                        "Unsatisfactory (<60)": "Very poor code quality"
                    }
                },
                {
                    "name": "Efficiency",
                    "weight": 0.20,
                    "description": "Algorithm efficiency and optimization",
                    "levels": {
                        "Excellent (90-100)": "Optimal algorithm, well-optimized",
                        "Good (80-89)": "Efficient approach",
                        "Satisfactory (70-79)": "Acceptable efficiency",
                        "Needs Improvement (60-69)": "Inefficient approach",
                        "Unsatisfactory (<60)": "Very inefficient"
                    }
                },
                {
                    "name": "Documentation",
                    "weight": 0.10,
                    "description": "Comments and documentation",
                    "levels": {
                        "Excellent (90-100)": "Excellent documentation",
                        "Good (80-89)": "Good comments",
                        "Satisfactory (70-79)": "Basic comments",
                        "Needs Improvement (60-69)": "Insufficient comments",
                        "Unsatisfactory (<60)": "No documentation"
                    }
                }
            ]
        }
    ]
    
    for rubric in default_rubrics:
        filename = f"{rubric['id']}.json"
        filepath = rubrics_path / filename
        with open(filepath, 'w') as f:
            json.dump(rubric, f, indent=2)
        print(f"  Created: {filename}")


@tool
def retrieve_rubric(assignment_description: str) -> str:
    """
    Retrieve a relevant grading rubric from the vector database using RAG.
    
    This tool performs semantic search to find the most appropriate rubric
    for the given assignment type.
    
    Input: Description of the assignment (e.g., "essay about democracy", "fibonacci code")
    Output: JSON rubric with criteria, weights, and performance levels
    
    AI Fundamentals: RAG/ML for consistent grading against predefined standards
    """
    global _rubric_vectorstore
    
    if _rubric_vectorstore is None:
        # Try to initialize
        if not initialize_rubric_store():
            return json.dumps({
                "error": "Rubric store not initialized",
                "fallback": "Use general grading criteria"
            })
    
    try:
        # Perform semantic search for relevant rubric
        results = _rubric_vectorstore.similarity_search(
            assignment_description,
            k=1  # Get top match
        )
        
        if not results:
            return json.dumps({
                "error": "No matching rubric found",
                "fallback": "Use general grading criteria"
            })
        
        # Extract rubric from document content
        doc = results[0]
        
        # Parse the full details JSON from the document
        content = doc.page_content
        if "Full Details:" in content:
            json_str = content.split("Full Details:")[1].strip()
            rubric_data = json.loads(json_str)
            
            return json.dumps({
                "success": True,
                "rubric": rubric_data,
                "metadata": {
                    "source": doc.metadata.get("source", "unknown"),
                    "file": doc.metadata.get("file", "unknown"),
                    "confidence": "high"
                }
            }, indent=2)
        
        return json.dumps({
            "error": "Could not parse rubric",
            "raw_content": content[:500]
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Error retrieving rubric: {str(e)}",
            "fallback": "Use general grading criteria"
        })


@tool
def list_available_rubrics() -> str:
    """
    List all available rubrics in the vector store.
    
    Returns: JSON list of rubric names and types
    """
    global _rubric_vectorstore
    
    if _rubric_vectorstore is None:
        if not initialize_rubric_store():
            return json.dumps({"error": "Rubric store not initialized"})
    
    try:
        # Get all documents from collection
        all_docs = _rubric_vectorstore.get()
        
        rubrics = []
        for metadata in all_docs.get('metadatas', []):
            rubrics.append({
                "id": metadata.get("rubric_id"),
                "name": metadata.get("name"),
                "type": metadata.get("type")
            })
        
        return json.dumps({
            "rubrics": rubrics,
            "count": len(rubrics)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error listing rubrics: {str(e)}"})


def get_rubric_retrieval_tools():
    """Return rubric retrieval tools."""
    return [retrieve_rubric, list_available_rubrics]

