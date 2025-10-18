"""
Integrations Router

Handles third-party integrations like Google Drive, GitHub, Notion, etc.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from api.routers.learniva_auth import get_current_user

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class IntegrationStatus(BaseModel):
    """Integration status model."""
    connected: bool
    account: Optional[str] = None
    last_sync: Optional[str] = None


@router.get("/google-drive/status")
@router.get("/google-drive/status/")
async def get_google_drive_status(current_user: dict = Depends(get_current_user)):
    """
    Get Google Drive integration status.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "connected": false,
            "account": null,
            "last_sync": null
        }
    """
    return IntegrationStatus(
        connected=False,
        account=None,
        last_sync=None
    )


@router.get("/github/status")
@router.get("/github/status/")
async def get_github_status(current_user: dict = Depends(get_current_user)):
    """
    Get GitHub integration status.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "connected": false,
            "account": null,
            "last_sync": null
        }
    """
    return IntegrationStatus(
        connected=False,
        account=None,
        last_sync=None
    )


@router.get("/notion/status")
@router.get("/notion/status/")
async def get_notion_status(current_user: dict = Depends(get_current_user)):
    """
    Get Notion integration status.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "connected": false,
            "account": null,
            "last_sync": null
        }
    """
    return IntegrationStatus(
        connected=False,
        account=None,
        last_sync=None
    )


@router.post("/google-drive/connect")
async def connect_google_drive(current_user: dict = Depends(get_current_user)):
    """
    Connect Google Drive integration.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "message": "Integration not yet implemented",
            "oauth_url": null
        }
    """
    return {
        "message": "Google Drive integration not yet implemented",
        "oauth_url": None
    }


@router.post("/github/connect")
async def connect_github(current_user: dict = Depends(get_current_user)):
    """
    Connect GitHub integration.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "message": "Integration not yet implemented",
            "oauth_url": null
        }
    """
    return {
        "message": "GitHub integration not yet implemented",
        "oauth_url": None
    }


@router.post("/notion/connect")
async def connect_notion(current_user: dict = Depends(get_current_user)):
    """
    Connect Notion integration.
    
    Headers:
        Authorization: Token abc123...
    
    Response:
        {
            "message": "Integration not yet implemented",
            "oauth_url": null
        }
    """
    return {
        "message": "Notion integration not yet implemented",
        "oauth_url": None
    }


@router.delete("/google-drive/disconnect")
async def disconnect_google_drive(current_user: dict = Depends(get_current_user)):
    """Disconnect Google Drive integration."""
    return {"message": "Google Drive disconnected (stub)"}


@router.delete("/github/disconnect")
async def disconnect_github(current_user: dict = Depends(get_current_user)):
    """Disconnect GitHub integration."""
    return {"message": "GitHub disconnected (stub)"}


@router.delete("/notion/disconnect")
async def disconnect_notion(current_user: dict = Depends(get_current_user)):
    """Disconnect Notion integration."""
    return {"message": "Notion disconnected (stub)"}

