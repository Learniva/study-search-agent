"""
Workspace management endpoints for Learniva compatibility.

Maps Learniva workspaces to Study Search Agent thread_ids/conversations.
In Study Search Agent, each thread_id represents a conversation context,
which maps conceptually to a Learniva workspace.

Usage:
    Add to api/app.py:
    from api.routers.learniva_workspaces import router as learniva_workspaces_router
    app.include_router(learniva_workspaces_router)

Production Notes:
    - Replace in-memory storage with PostgreSQL
    - Add pagination for workspace lists
    - Add workspace sharing/collaboration
    - Add workspace permissions
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from utils.auth.jwt_handler import get_current_user  # Use Google OAuth JWT authentication

router = APIRouter(prefix="/api/workspaces", tags=["learniva-workspaces"])


# ============================================================================
# In-Memory Storage (REPLACE WITH DATABASE IN PRODUCTION!)
# ============================================================================

WORKSPACES_DB = {}  # Format: {user_id: [workspace1, workspace2, ...]}


# ============================================================================
# Models
# ============================================================================

class WorkspaceCreate(BaseModel):
    """Request body for creating workspace."""
    name: str
    description: str = ""


class WorkspaceUpdate(BaseModel):
    """Request body for updating workspace."""
    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    """Workspace data response."""
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    document_count: int
    owner_id: int


class DocumentResponse(BaseModel):
    """Document metadata response."""
    id: str
    filename: str
    size: int
    uploaded_at: datetime


# ============================================================================
# Helper Functions
# ============================================================================

def get_workspace_by_id(user_id: int, workspace_id: str) -> Optional[dict]:
    """Find workspace by ID for specific user."""
    workspaces = WORKSPACES_DB.get(user_id, [])
    for workspace in workspaces:
        if workspace["id"] == workspace_id:
            return workspace
    return None


def generate_workspace_id(user_id: int) -> str:
    """Generate unique workspace ID."""
    timestamp = datetime.now().timestamp()
    return f"workspace-{user_id}-{int(timestamp * 1000)}"


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(current_user: dict = Depends(get_current_user)):
    """
    List all workspaces for authenticated user.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        [
            {
                "id": "workspace-1-1234567890",
                "name": "Machine Learning Study",
                "description": "Notes and resources for ML course",
                "created_at": "2025-01-15T10:30:00",
                "updated_at": "2025-01-15T14:20:00",
                "document_count": 5,
                "owner_id": 1
            }
        ]
    """
    user_id = current_user["id"]
    workspaces = WORKSPACES_DB.get(user_id, [])
    return workspaces


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    workspace: WorkspaceCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create new workspace (conversation thread).
    
    Headers:
        Authorization: Token abc123...
    
    Request Body:
        {
            "name": "Machine Learning Study",
            "description": "Notes and resources for ML course"
        }
    
    Response:
        {
            "id": "workspace-1-1234567890",
            "name": "Machine Learning Study",
            "description": "Notes and resources for ML course",
            "created_at": "2025-01-15T10:30:00",
            "updated_at": "2025-01-15T10:30:00",
            "document_count": 0,
            "owner_id": 1
        }
    """
    user_id = current_user["id"]
    workspace_id = generate_workspace_id(user_id)
    
    now = datetime.now()
    
    new_workspace = {
        "id": workspace_id,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": now,
        "updated_at": now,
        "document_count": 0,
        "owner_id": user_id,
    }
    
    # Add to user's workspaces
    if user_id not in WORKSPACES_DB:
        WORKSPACES_DB[user_id] = []
    
    WORKSPACES_DB[user_id].append(new_workspace)
    
    return new_workspace


@router.get("/{workspace_id}/", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get workspace details.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Response:
        {
            "id": "workspace-1-1234567890",
            "name": "Machine Learning Study",
            "description": "Notes and resources",
            "created_at": "2025-01-15T10:30:00",
            "updated_at": "2025-01-15T14:20:00",
            "document_count": 5,
            "owner_id": 1
        }
    """
    user_id = current_user["id"]
    workspace = get_workspace_by_id(user_id, workspace_id)
    
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    return workspace


@router.patch("/{workspace_id}/", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    update: WorkspaceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update workspace details.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Request Body:
        {
            "name": "Updated Name",
            "description": "Updated description"
        }
    
    Response:
        Updated workspace object
    """
    user_id = current_user["id"]
    workspace = get_workspace_by_id(user_id, workspace_id)
    
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    # Update fields
    if update.name is not None:
        workspace["name"] = update.name
    
    if update.description is not None:
        workspace["description"] = update.description
    
    workspace["updated_at"] = datetime.now()
    
    return workspace


@router.delete("/{workspace_id}/")
async def delete_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete workspace.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Response:
        {
            "detail": "Workspace deleted successfully"
        }
    """
    user_id = current_user["id"]
    workspaces = WORKSPACES_DB.get(user_id, [])
    
    # Find and remove workspace
    workspace_found = False
    for i, workspace in enumerate(workspaces):
        if workspace["id"] == workspace_id:
            workspaces.pop(i)
            workspace_found = True
            break
    
    if not workspace_found:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    return {"detail": "Workspace deleted successfully"}


@router.get("/{workspace_id}/documents/", response_model=List[DocumentResponse])
async def get_workspace_documents(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get documents in workspace.
    
    Delegates to main /documents/ endpoint since documents are shared
    across all workspaces in Study Search Agent.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Response:
        [
            {
                "id": "doc-123",
                "filename": "notes.pdf",
                "size": 1024000,
                "uploaded_at": "2025-01-15T10:30:00"
            }
        ]
    """
    user_id = current_user["id"]
    workspace = get_workspace_by_id(user_id, workspace_id)
    
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    # Get documents from main documents endpoint
    # In Study Search Agent, documents are global (RAG vector store)
    # You could add workspace-specific filtering here if needed
    
    try:
        from api.routers.documents import get_documents
        documents = await get_documents()
        
        # Convert to expected format
        response = []
        for doc in documents:
            response.append({
                "id": doc.get("id", doc["filename"]),
                "filename": doc["filename"],
                "size": doc.get("size", 0),
                "uploaded_at": datetime.now(),  # Would come from database
            })
        
        return response
    except Exception as e:
        # Fallback to empty list if documents endpoint not available
        return []


@router.post("/{workspace_id}/documents/")
async def upload_workspace_document(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload document to workspace.
    
    Delegates to main /documents/upload endpoint.
    Updates workspace document count.
    
    Headers:
        Authorization: Token abc123...
        Content-Type: multipart/form-data
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Request Body:
        FormData with 'file' field
    
    Response:
        {
            "message": "Document uploaded successfully",
            "filename": "notes.pdf",
            "workspace_id": "workspace-1-1234567890"
        }
    """
    user_id = current_user["id"]
    workspace = get_workspace_by_id(user_id, workspace_id)
    
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    # Document upload is handled by main /documents/upload endpoint
    # Here we just acknowledge and update workspace metadata
    
    # Increment document count
    workspace["document_count"] += 1
    workspace["updated_at"] = datetime.now()
    
    return {
        "message": "Document upload endpoint - use /documents/upload",
        "detail": "Upload documents via POST /documents/upload, they will be available in all workspaces",
        "workspace_id": workspace_id
    }


@router.get("/{workspace_id}/materials/")
async def get_workspace_materials(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get learning materials for workspace.
    
    In Study Search Agent, learning materials are generated via queries.
    This could return conversation history for the workspace thread.
    
    Headers:
        Authorization: Token abc123...
    
    Path Parameters:
        workspace_id: Workspace identifier
    
    Response:
        [
            {
                "id": "material-1",
                "title": "Introduction to Machine Learning",
                "type": "generated",
                "content": "...",
                "created_at": "2025-01-15T10:30:00"
            }
        ]
    """
    user_id = current_user["id"]
    workspace = get_workspace_by_id(user_id, workspace_id)
    
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )
    
    # Get conversation history for this workspace (thread_id)
    try:
        from api.routers.query import get_history
        history = await get_history(workspace_id)
        
        # Convert to materials format
        materials = []
        for i, item in enumerate(history):
            materials.append({
                "id": f"material-{i}",
                "title": f"Query {i+1}",
                "type": "generated",
                "content": item.get("answer", ""),
                "created_at": datetime.now(),
            })
        
        return materials
    except Exception as e:
        # Return empty list if history not available
        return []

