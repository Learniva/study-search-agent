"""
Document Processing for L2 Vector Store

Handles document upload, text extraction, chunking, and indexing into pgvector.
Supports PDF, DOCX, TXT, and MD files with intelligent chunking.
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# Document processing imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import docx2txt
    DOCX_AVAILABLE = True
except ImportError:
    try:
        from docx import Document
        DOCX_AVAILABLE = True
    except ImportError:
        DOCX_AVAILABLE = False

# LangChain for text splitting
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Google GenAI SDK for 768D embeddings (direct API)
import google.generativeai as genai

# Database operations
from sqlalchemy.orm import Session
from database.operations.rag import store_document_vectors, delete_document_vectors

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Process documents for L2 Vector Store indexing.
    
    Handles:
    - Text extraction from multiple formats
    - Intelligent chunking with overlap
    - Embedding generation via Google Gemini
    - Storage in PostgreSQL + pgvector
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "models/embedding-001"
    ):
        """
        Initialize document processor with Google Gemini 768D embeddings.
        
        Args:
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks for context continuity
            embedding_model: Google Gemini embedding model (default: models/embedding-001, 768D)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Configure Google GenAI SDK for 768D embeddings
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            
            genai.configure(api_key=api_key)
            
            # Verify model access with test embedding
            test_result = genai.embed_content(
                model=self.embedding_model,
                content="test",
                task_type="retrieval_document"
            )
            embedding_dim = len(test_result['embedding'])
            
            logger.info(f"✅ Google Gemini embeddings initialized: {embedding_model} ({embedding_dim}D)")
            
            if embedding_dim != 768:
                logger.warning(f"⚠️  Expected 768D, got {embedding_dim}D")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Gemini embeddings: {e}")
            raise
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from document based on file type.
        
        Args:
            file_path: Path to document file
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If file type is unsupported
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.pdf':
                return self._extract_pdf(file_path)
            elif extension == '.docx':
                return self._extract_docx(file_path)
            elif extension in ['.txt', '.md']:
                return self._extract_text(file_path)
            else:
                raise ValueError(f"Unsupported file type: {extension}")
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            raise
    
    def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF not available. Install with: pip install pymupdf")
        
        try:
            doc = fitz.open(file_path)
            text_parts = []
            
            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"[Page {page_num}]\n{text}")
            
            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
    
    def _extract_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        if not DOCX_AVAILABLE:
            raise ImportError("DOCX processing not available. Install with: pip install python-docx or docx2txt")
        
        try:
            # Try docx2txt first (more reliable)
            text = docx2txt.process(str(file_path))
            if text and text.strip():
                return text
        except:
            pass
        
        try:
            # Fallback to python-docx
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            raise
    
    def _extract_text(self, file_path: Path) -> str:
        """Extract text from TXT or MD file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata.
        
        Args:
            text: Full text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunks with content and metadata
        """
        chunks = self.text_splitter.split_text(text)
        
        result = []
        for idx, chunk_text in enumerate(chunks):
            chunk = {
                'content': chunk_text,
                'chunk_index': idx,
                'metadata': {
                    **(metadata or {}),
                    'chunk_number': idx + 1,
                    'total_chunks': len(chunks),
                    'char_count': len(chunk_text)
                }
            }
            result.append(chunk)
        
        return result
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate 768D embeddings using Google Gemini.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of 768-dimensional embedding vectors
        """
        try:
            # Google GenAI SDK doesn't have async batch embed, so use sync
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model=self.embedding_model,
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
            
            logger.debug(f"Generated {len(embeddings)} embeddings ({len(embeddings[0])}D each)")
            return embeddings
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def generate_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Generate 768D embeddings synchronously (for background tasks).
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of 768-dimensional embedding vectors
        """
        try:
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model=self.embedding_model,
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
            
            logger.debug(f"Generated {len(embeddings)} embeddings ({len(embeddings[0])}D each)")
            return embeddings
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def process_and_index_document(
        self,
        db: Session,
        file_path: str,
        document_name: str,
        user_id: Optional[str] = None,
        course_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete pipeline: extract, chunk, embed, and index document.
        
        Args:
            db: Database session
            file_path: Path to document file
            document_name: Name of the document
            user_id: Optional user ID for ownership
            course_id: Optional course ID
            
        Returns:
            Dictionary with indexing results
        """
        try:
            # Generate unique document ID
            document_id = str(uuid.uuid4())
            
            # Extract text
            logger.info(f"Extracting text from {document_name}...")
            text = self.extract_text(file_path)
            
            if not text or len(text.strip()) < 10:
                raise ValueError("Document is empty or too short")
            
            # Chunk text
            file_type = Path(file_path).suffix.lstrip('.')
            metadata = {
                'document_name': document_name,
                'document_type': file_type,
                'file_size': os.path.getsize(file_path)
            }
            
            logger.info(f"Chunking text ({len(text)} chars)...")
            chunks = self.chunk_text(text, metadata)
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            chunk_texts = [chunk['content'] for chunk in chunks]
            embeddings = await self.generate_embeddings(chunk_texts)
            
            # Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding
                chunk['type'] = file_type
            
            # Store in database
            logger.info(f"Storing {len(chunks)} vectors in database...")
            vectors_stored = store_document_vectors(
                db=db,
                document_id=document_id,
                document_name=document_name,
                chunks=chunks,
                user_id=user_id,
                course_id=course_id
            )
            
            logger.info(f"✅ Document indexed: {document_name} ({vectors_stored} vectors)")
            
            return {
                'success': True,
                'document_id': document_id,
                'document_name': document_name,
                'chunks_created': len(chunks),
                'vectors_stored': vectors_stored,
                'total_chars': len(text)
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'document_name': document_name
            }
    
    def process_and_index_document_sync(
        self,
        db: Session,
        file_path: str,
        document_name: str,
        user_id: Optional[str] = None,
        course_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronous version of process_and_index_document (for background tasks).
        
        Args:
            db: Database session
            file_path: Path to document file
            document_name: Name of the document
            user_id: Optional user ID for ownership
            course_id: Optional course ID
            
        Returns:
            Dictionary with indexing results
        """
        try:
            # Generate unique document ID
            document_id = str(uuid.uuid4())
            
            # Extract text
            logger.info(f"Extracting text from {document_name}...")
            text = self.extract_text(file_path)
            
            if not text or len(text.strip()) < 10:
                raise ValueError("Document is empty or too short")
            
            # Chunk text
            file_type = Path(file_path).suffix.lstrip('.')
            metadata = {
                'document_name': document_name,
                'document_type': file_type,
                'file_size': os.path.getsize(file_path)
            }
            
            logger.info(f"Chunking text ({len(text)} chars)...")
            chunks = self.chunk_text(text, metadata)
            
            # Generate embeddings (sync)
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            chunk_texts = [chunk['content'] for chunk in chunks]
            embeddings = self.generate_embeddings_sync(chunk_texts)
            
            # Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding
                chunk['type'] = file_type
            
            # Store in database
            logger.info(f"Storing {len(chunks)} vectors in database...")
            vectors_stored = store_document_vectors(
                db=db,
                document_id=document_id,
                document_name=document_name,
                chunks=chunks,
                user_id=user_id,
                course_id=course_id
            )
            
            logger.info(f"✅ Document indexed: {document_name} ({vectors_stored} vectors)")
            
            return {
                'success': True,
                'document_id': document_id,
                'document_name': document_name,
                'chunks_created': len(chunks),
                'vectors_stored': vectors_stored,
                'total_chars': len(text)
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'document_name': document_name
            }


# Global processor instance
_processor = None

def get_document_processor() -> DocumentProcessor:
    """Get or create global document processor instance."""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor


def remove_document_from_vector_store(
    db: Session,
    document_name: str
) -> bool:
    """
    Remove all vectors for a document from the vector store.
    
    Args:
        db: Database session
        document_name: Name of document to remove
        
    Returns:
        True if successful
    """
    try:
        # Find all vectors with this document name
        from database.models import DocumentVector
        vectors = db.query(DocumentVector).filter(
            DocumentVector.document_name == document_name
        ).all()
        
        if not vectors:
            logger.warning(f"No vectors found for document: {document_name}")
            return True
        
        # Delete all vectors
        for vector in vectors:
            db.delete(vector)
        
        db.commit()
        logger.info(f"✅ Removed {len(vectors)} vectors for: {document_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to remove document vectors: {e}")
        db.rollback()
        return False


__all__ = [
    'DocumentProcessor',
    'get_document_processor',
    'remove_document_from_vector_store'
]

