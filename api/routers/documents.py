"""Documents Router - Document management endpoints."""

import os
import shutil
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from typing import List

from api.models import UploadResponse, DocumentInfo, DocumentsListResponse
from utils.monitoring import get_logger
from config import settings

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
        
        # Reinitialize document QA in background
        if background_tasks:
            def reload_docs():
                try:
                    from tools.study import initialize_document_qa
                    initialize_document_qa(DOCUMENTS_DIR)
                except Exception as e:
                    logger.error(f"Failed to reload documents: {e}")
            
            background_tasks.add_task(reload_docs)
        
        return UploadResponse(
            filename=file.filename,
            message=f"File '{file.filename}' uploaded successfully",
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
        
        # Reinitialize document QA in background
        def reload_docs():
            try:
                from tools.study import initialize_document_qa
                initialize_document_qa(DOCUMENTS_DIR)
            except Exception as e:
                logger.error(f"Failed to reload documents: {e}")
        
        background_tasks.add_task(reload_docs)
        
        return {"message": f"File '{filename}' deleted successfully"}
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

