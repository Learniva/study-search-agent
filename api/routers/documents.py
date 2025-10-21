"""Documents Router - Document management endpoints."""

import os
import shutil
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from typing import List

from api.models import UploadResponse, DocumentInfo, DocumentsListResponse
from utils.monitoring import get_logger
from config import settings
from database import get_db
from database.operations.document_processing import get_document_processor, remove_document_from_vector_store

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

# Documents directory
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "documents")


@router.get("/", response_model=DocumentsListResponse)
async def list_documents():
    """
    List all available documents.
    
    Returns list of documents with metadata.
    """
    if not os.path.exists(DOCUMENTS_DIR):
        return DocumentsListResponse(documents=[], total=0)
    
    documents = []
    for filename in os.listdir(DOCUMENTS_DIR):
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            file_type = Path(filename).suffix.lstrip('.')
            
            documents.append(
                DocumentInfo(
                    name=filename,
                    size=size,
                    type=file_type
                )
            )
    
    return DocumentsListResponse(
        documents=documents,
        total=len(documents)
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a document and index it for semantic search.
    
    Supported formats: PDF, DOCX, TXT, MD
    
    **Note:** Indexing happens asynchronously in the background. 
    Large documents may take 10-30 seconds to process. 
    Please wait before querying the document.
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create documents directory if not exists
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    
    # Save file
    file_path = os.path.join(DOCUMENTS_DIR, file.filename)
    
    try:
        # Get file size for estimate
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info(f"Document uploaded: {file.filename} ({file_size} bytes)")
        
        # Estimate indexing time based on file size
        estimated_seconds = max(10, min(60, file_size // 50000))  # ~10-60 seconds
        
        # Index document in L2 Vector Store (pgvector) in background
        # This automatically triggers when a document is uploaded
        if background_tasks:
            def index_document():
                try:
                    logger.info(f"🔄 AUTO-INDEXING STARTED for: {file.filename}")
                    logger.info(f"   File size: {file_size:,} bytes")
                    processor = get_document_processor()
                    
                    with get_db() as db:
                        # Extract user_id and course_id from request context if available
                        # These are optional - documents can be uploaded without user context in development
                        request_user_id = getattr(request.state, 'user_id', None) if hasattr(request, 'state') else None
                        request_course_id = None  # Could be extracted from query params if needed
                        
                        result = processor.process_and_index_document_sync(
                            db=db,
                            file_path=file_path,
                            document_name=file.filename,
                            user_id=request_user_id,  # From request state (set by auth middleware)
                            course_id=request_course_id  # From request params or state
                        )
                        
                        if result['success']:
                            chunks_created = result.get('chunks_created', 0)
                            vectors_stored = result.get('vectors_stored', 0)
                            extraction_method = result.get('extraction_info', {}).get('extraction_method', 'unknown')
                            chunking_method = result.get('extraction_info', {}).get('chunking_method', 'unknown')
                            
                            logger.info(f"✅ AUTO-INDEXING COMPLETE: {file.filename}")
                            logger.info(f"   📊 Chunks created: {chunks_created}")
                            logger.info(f"   💾 Vectors stored: {vectors_stored}")
                            logger.info(f"   🔧 Extraction: {extraction_method}")
                            logger.info(f"   📝 Chunking: {chunking_method}")
                            
                            # Warn if chunk count is low
                            if chunks_created < 40:
                                logger.warning(f"⚠️  Low chunk count ({chunks_created}). Expected 40-70+ for optimal RAG performance.")
                        else:
                            logger.error(f"❌ AUTO-INDEXING FAILED: {file.filename}")
                            logger.error(f"   Error: {result.get('error')}")
                except Exception as e:
                    logger.error(f"❌ Background indexing error for {file.filename}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Immediately trigger background indexing
            background_tasks.add_task(index_document)
            
            message = (
                f"✅ File '{file.filename}' uploaded successfully!\n\n"
                f"⏳ **Auto-indexing in progress** (estimated: ~{estimated_seconds} seconds)\n"
                f"📊 File size: {file_size:,} bytes\n"
                f"📝 Expected chunks: 40-70+ (depending on document size)\n\n"
                f"💡 **Automatic process:**\n"
                f"  1. ✅ File uploaded and saved\n"
                f"  2. 🔄 Extracting text with Docling + HybridChunker\n"
                f"  3. 📝 Creating semantic chunks (tables stay intact)\n"
                f"  4. 🧠 Generating 768D embeddings\n"
                f"  5. 💾 Storing in vector database\n\n"
                f"⏰ Please wait ~{estimated_seconds} seconds, then query your document!"
            )
        else:
            logger.warning(f"⚠️  Background tasks not available - indexing will not be automatic!")
            message = f"File '{file.filename}' uploaded but background tasks not available for auto-indexing."
        
        return UploadResponse(
            filename=file.filename,
            message=message,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{filename}")
async def check_document_status(filename: str):
    """
    Check if a document is fully indexed and ready for querying.
    
    Returns:
    - exists_on_disk: Whether the file exists
    - indexed: Whether it's indexed in the vector store
    - vector_count: Number of vectors stored
    - status: "ready", "indexing", or "not_found"
    """
    file_path = os.path.join(DOCUMENTS_DIR, filename)
    exists_on_disk = os.path.exists(file_path)
    
    if not exists_on_disk:
        return {
            "filename": filename,
            "exists_on_disk": False,
            "indexed": False,
            "vector_count": 0,
            "status": "not_found",
            "message": "Document not found. Please upload it first."
        }
    
    try:
        # Check vector store
        from sqlalchemy import text
        with get_db() as db:
            result = db.execute(
                text("SELECT COUNT(*) as count FROM document_vectors WHERE document_name = :name"),
                {"name": filename}
            )
            vector_count = result.fetchone().count
            
            if vector_count > 0:
                return {
                    "filename": filename,
                    "exists_on_disk": True,
                    "indexed": True,
                    "vector_count": vector_count,
                    "status": "ready",
                    "message": f"✅ Document is fully indexed with {vector_count} vectors. Ready for querying!"
                }
            else:
                # File exists but not indexed yet
                file_size = os.path.getsize(file_path)
                return {
                    "filename": filename,
                    "exists_on_disk": True,
                    "indexed": False,
                    "vector_count": 0,
                    "status": "indexing",
                    "message": f"⏳ Document is being indexed... Please wait (file size: {file_size:,} bytes). Try again in a few seconds."
                }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_document(filename: str, background_tasks: BackgroundTasks):
    """Delete a document and remove it from the vector store."""
    file_path = os.path.join(DOCUMENTS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        os.remove(file_path)
        logger.info(f"Document deleted: {filename}")
        
        # Remove document from L2 Vector Store (pgvector) in background
        def remove_from_vector_store():
            try:
                with get_db() as db:
                    success = remove_document_from_vector_store(db, filename)
                    if success:
                        logger.info(f"✅ Removed from vector store: {filename}")
                    else:
                        logger.warning(f"⚠️  Vector store removal had issues: {filename}")
            except Exception as e:
                logger.error(f"Background vector removal error: {e}")
        
        background_tasks.add_task(remove_from_vector_store)
        
        return {"message": f"File '{filename}' deleted successfully. Removing from vector store..."}
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

