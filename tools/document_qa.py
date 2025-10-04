"""
Document Q&A tool for answering questions from uploaded PDF/DOCX files.
"""

import os
from typing import Optional, List
from pathlib import Path
from langchain.tools import Tool
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings


class DocumentQAManager:
    """
    Manages document loading, indexing, and querying.
    """
    
    def __init__(self, documents_dir: str = "documents"):
        """
        Initialize the DocumentQA manager.
        
        Args:
            documents_dir: Directory containing PDF/DOCX files
        """
        self.documents_dir = documents_dir
        self.vectorstore = None
        self.embeddings = None
        self.loaded_files = []
        
        # Create documents directory if it doesn't exist
        Path(documents_dir).mkdir(exist_ok=True)
    
    def load_documents(self) -> bool:
        """
        Load all PDF and DOCX files from the documents directory.
        
        Returns:
            True if documents were loaded successfully, False otherwise
        """
        try:
            documents = []
            files = list(Path(self.documents_dir).glob("*.pdf")) + \
                   list(Path(self.documents_dir).glob("*.docx"))
            
            if not files:
                print(f"No PDF or DOCX files found in '{self.documents_dir}' directory.")
                return False
            
            print(f"Loading {len(files)} document(s)...")
            
            for file_path in files:
                try:
                    if file_path.suffix.lower() == '.pdf':
                        loader = PyPDFLoader(str(file_path))
                    elif file_path.suffix.lower() == '.docx':
                        loader = Docx2txtLoader(str(file_path))
                    else:
                        continue
                    
                    docs = loader.load()
                    documents.extend(docs)
                    self.loaded_files.append(file_path.name)
                    print(f"  ✓ Loaded: {file_path.name}")
                except Exception as e:
                    print(f"  ✗ Error loading {file_path.name}: {e}")
            
            if not documents:
                print("No documents could be loaded successfully.")
                return False
            
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )
            splits = text_splitter.split_documents(documents)
            print(f"Split into {len(splits)} chunks.")
            
            # Create embeddings
            print("Creating embeddings (this may take a moment)...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            
            # Create vector store
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=self.embeddings,
                persist_directory=".chroma_db"
            )
            
            print(f"✓ Successfully indexed {len(self.loaded_files)} document(s)!")
            return True
            
        except Exception as e:
            print(f"Error loading documents: {e}")
            return False
    
    def query(self, question: str, k: int = 3) -> str:
        """
        Query the document collection.
        
        Args:
            question: The question to answer
            k: Number of relevant chunks to retrieve
            
        Returns:
            Relevant context from the documents
        """
        if not self.vectorstore:
            return "No documents have been loaded. Please add PDF or DOCX files to the 'documents' directory."
        
        try:
            # Perform similarity search
            results = self.vectorstore.similarity_search(question, k=k)
            
            if not results:
                return f"No relevant information found in the loaded documents: {', '.join(self.loaded_files)}"
            
            # Combine results
            context = "\n\n---\n\n".join([
                f"[Source: {doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
                for doc in results
            ])
            
            return f"Relevant information from documents:\n\n{context}"
            
        except Exception as e:
            return f"Error querying documents: {e}"


# Global document manager instance
_doc_manager = None


def initialize_document_qa(documents_dir: str = "documents") -> bool:
    """
    Initialize the document Q&A system by loading documents.
    
    Args:
        documents_dir: Directory containing PDF/DOCX files
        
    Returns:
        True if initialization was successful, False otherwise
    """
    global _doc_manager
    _doc_manager = DocumentQAManager(documents_dir)
    return _doc_manager.load_documents()


def get_document_qa_tool() -> Optional[Tool]:
    """
    Create and return the document Q&A tool.
    
    This tool answers questions based on uploaded PDF/DOCX files.
    
    Returns:
        Tool object configured for document Q&A, or None if not initialized
    """
    global _doc_manager
    
    if _doc_manager is None or _doc_manager.vectorstore is None:
        return None
    
    def query_documents(question: str) -> str:
        """Query the loaded documents."""
        return _doc_manager.query(question)
    
    return Tool(
        name="Document_QA",
        func=query_documents,
        description=f"""Use this tool to answer questions based on content from uploaded documents (PDF/DOCX files).
This tool has access to: {', '.join(_doc_manager.loaded_files)}

Use this when:
- The question is about content from lecture notes, textbooks, or study materials
- You need to reference specific information from the uploaded documents
- The question relates to academic or educational content in the documents

Input should be a clear question about the document content."""
    )

