"""
Document Loader Utility

Loads and indexes documents from the documents/ folder into L2 Vector Store.
This provides backward compatibility with the old document_qa system.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any

from database.operations.document_processing import get_document_processor
from database import get_db

logger = logging.getLogger(__name__)


def load_documents_from_directory(
    documents_dir: str = "documents",
    force_reindex: bool = False
) -> Dict[str, Any]:
    """
    Load all documents from a directory and index them in the vector store.
    
    Args:
        documents_dir: Path to documents directory
        force_reindex: If True, re-index even if already indexed
        
    Returns:
        Dictionary with indexing results
    """
    if not os.path.exists(documents_dir):
        logger.warning(f"Documents directory not found: {documents_dir}")
        return {
            "success": False,
            "message": "Documents directory not found",
            "documents_processed": 0
        }
    
    # Get list of supported documents
    supported_extensions = {'.pdf', '.docx', '.txt', '.md'}
    documents = []
    
    for filename in os.listdir(documents_dir):
        filepath = os.path.join(documents_dir, filename)
        if os.path.isfile(filepath):
            ext = Path(filename).suffix.lower()
            if ext in supported_extensions:
                documents.append((filename, filepath))
    
    if not documents:
        logger.info("No documents found to index")
        return {
            "success": True,
            "message": "No documents found",
            "documents_processed": 0
        }
    
    # Process documents
    processor = get_document_processor()
    results = []
    success_count = 0
    error_count = 0
    
    logger.info(f"📚 Indexing {len(documents)} documents from {documents_dir}...")
    
    for filename, filepath in documents:
        try:
            # Check if already indexed (by checking vector store)
            if not force_reindex:
                with get_db() as db:
                    from database.models import DocumentVector
                    existing = db.query(DocumentVector).filter(
                        DocumentVector.document_name == filename
                    ).first()
                    
                    if existing:
                        logger.info(f"  ⏭️  Skipping {filename} (already indexed)")
                        results.append({
                            "filename": filename,
                            "status": "skipped",
                            "message": "Already indexed"
                        })
                        continue
            
            # Index the document
            logger.info(f"  📄 Indexing {filename}...")
            with get_db() as db:
                result = processor.process_and_index_document_sync(
                    db=db,
                    file_path=filepath,
                    document_name=filename,
                    user_id="system",  # System-loaded documents
                    course_id=None
                )
                
                if result['success']:
                    success_count += 1
                    logger.info(f"  ✅ {filename}: {result['vectors_stored']} vectors")
                else:
                    error_count += 1
                    logger.error(f"  ❌ {filename}: {result.get('error')}")
                
                results.append(result)
                
        except Exception as e:
            error_count += 1
            logger.error(f"  ❌ Error indexing {filename}: {e}")
            results.append({
                "filename": filename,
                "status": "error",
                "error": str(e)
            })
    
    # Summary
    total = len(documents)
    logger.info(f"\n📊 Indexing Summary:")
    logger.info(f"  Total documents: {total}")
    logger.info(f"  ✅ Successfully indexed: {success_count}")
    logger.info(f"  ❌ Errors: {error_count}")
    logger.info(f"  ⏭️  Skipped: {total - success_count - error_count}")
    
    return {
        "success": error_count == 0,
        "total_documents": total,
        "success_count": success_count,
        "error_count": error_count,
        "skipped_count": total - success_count - error_count,
        "results": results
    }


def initialize_document_store(documents_dir: str = "documents") -> bool:
    """
    Initialize document store with documents from directory.
    Called on application startup.
    
    Args:
        documents_dir: Path to documents directory
        
    Returns:
        True if successful
    """
    try:
        result = load_documents_from_directory(documents_dir, force_reindex=False)
        return result["success"]
    except Exception as e:
        logger.error(f"Failed to initialize document store: {e}")
        return False


__all__ = [
    'load_documents_from_directory',
    'initialize_document_store'
]

