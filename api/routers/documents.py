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
    Upload a document.
    
    Supported formats: PDF, DOCX, TXT, MD
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
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Document uploaded: {file.filename}")
        
        # Index document in L2 Vector Store (pgvector) in background
        if background_tasks:
            def index_document():
                try:
                    processor = get_document_processor()
                    db = next(get_db())  # get_db() is a generator
                    try:
                        result = processor.process_and_index_document_sync(
                            db=db,
                            file_path=file_path,
                            document_name=file.filename,
                            user_id=None,  # TODO: Extract from auth context
                            course_id=None  # TODO: Extract from request
                        )
                        if result['success']:
                            logger.info(f"✅ Indexed: {file.filename} - {result['vectors_stored']} vectors")
                        else:
                            logger.error(f"❌ Indexing failed: {result.get('error')}")
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Background indexing error: {e}")
            
            background_tasks.add_task(index_document)
            message = f"File '{file.filename}' uploaded successfully. Indexing in progress..."
        else:
            message = f"File '{file.filename}' uploaded successfully. Use background_tasks for indexing."
        
        return UploadResponse(
            filename=file.filename,
            message=message,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_document(filename: str, background_tasks: BackgroundTasks):
    """Delete a document."""
    file_path = os.path.join(DOCUMENTS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        os.remove(file_path)
        logger.info(f"Document deleted: {filename}")
        
        # Remove document from L2 Vector Store (pgvector) in background
        def remove_from_vector_store():
            try:
                db = next(get_db())  # get_db() is a generator
                try:
                    success = remove_document_from_vector_store(db, filename)
                    if success:
                        logger.info(f"✅ Removed from vector store: {filename}")
                    else:
                        logger.warning(f"⚠️  Vector store removal had issues: {filename}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Background vector removal error: {e}")
        
        background_tasks.add_task(remove_from_vector_store)
        
        return {"message": f"File '{filename}' deleted successfully. Removing from vector store..."}
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

