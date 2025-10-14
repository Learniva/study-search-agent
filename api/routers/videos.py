"""Video Download Router - Serve generated animation videos."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict
import os

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.get("/")
async def videos_root():
    """
    Videos router root - redirects to list endpoint.
    
    Returns:
        Basic info about video endpoints
    """
    return {
        "message": "Video Download Service",
        "endpoints": {
            "list": "/videos/list",
            "download": "/videos/download/{filename}",
            "latest": "/videos/latest",
            "delete": "/videos/delete/{filename}",
            "cleanup": "/videos/cleanup"
        },
        "description": "Manage and download generated Manim animation videos"
    }


@router.get("/list")
async def list_videos():
    """
    List all generated animation videos available for download.
    
    Returns:
        List of videos with metadata
    """
    downloads_dir = Path("downloads/animations")
    
    if not downloads_dir.exists():
        return {"videos": [], "count": 0}
    
    videos = []
    for video_file in sorted(downloads_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = video_file.stat()
        videos.append({
            "filename": video_file.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": stat.st_mtime,
            "download_url": f"/videos/download/{video_file.name}"
        })
    
    return {
        "videos": videos,
        "count": len(videos),
        "directory": str(downloads_dir.absolute())
    }


@router.get("/download/{filename}")
async def download_video(filename: str):
    """
    Download a generated animation video.
    
    Args:
        filename: Name of the video file
        
    Returns:
        Video file for download
    """
    # Security: Validate filename to prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    video_path = Path("downloads/animations") / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    if not video_path.is_file():
        raise HTTPException(status_code=400, detail="Invalid file")
    
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/latest")
async def get_latest_video():
    """
    Get the most recently generated video.
    
    Returns:
        Latest video file for download
    """
    downloads_dir = Path("downloads/animations")
    
    if not downloads_dir.exists():
        raise HTTPException(status_code=404, detail="No videos found")
    
    video_files = sorted(downloads_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not video_files:
        raise HTTPException(status_code=404, detail="No videos found")
    
    latest = video_files[0]
    
    return FileResponse(
        path=str(latest),
        media_type="video/mp4",
        filename=latest.name,
        headers={
            "Content-Disposition": f'attachment; filename="{latest.name}"'
        }
    )


@router.delete("/delete/{filename}")
async def delete_video(filename: str):
    """
    Delete a generated animation video.
    
    Args:
        filename: Name of the video file
        
    Returns:
        Success message
    """
    # Security: Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    video_path = Path("downloads/animations") / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        video_path.unlink()
        return {"message": f"Video '{filename}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting video: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_videos(keep_last: int = 10):
    """
    Clean up old videos, keeping only the most recent ones.
    
    Args:
        keep_last: Number of recent videos to keep (default: 10)
        
    Returns:
        Cleanup statistics
    """
    downloads_dir = Path("downloads/animations")
    
    if not downloads_dir.exists():
        return {"deleted": 0, "kept": 0, "message": "No videos directory found"}
    
    video_files = sorted(downloads_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if len(video_files) <= keep_last:
        return {"deleted": 0, "kept": len(video_files), "message": "No cleanup needed"}
    
    to_delete = video_files[keep_last:]
    deleted_count = 0
    
    for video in to_delete:
        try:
            video.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {video}: {e}")
    
    return {
        "deleted": deleted_count,
        "kept": keep_last,
        "message": f"Cleaned up {deleted_count} old videos"
    }

