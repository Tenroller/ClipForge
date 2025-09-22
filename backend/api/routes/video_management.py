"""
Video management endpoints for the new video tracking system.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...database import get_job_store
from ...logging_config import get_logger
from ...services.video_service import get_video_service
from ...services.thumbnail_service import get_thumbnail_service

router = APIRouter()
logger = get_logger("video_management")

# Get services
job_store = get_job_store()
video_service = get_video_service()
thumbnail_service = get_thumbnail_service()


class UpdateVideoRequest(BaseModel):
    """Request model for updating video information"""
    posted: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class SyncVideosResponse(BaseModel):
    """Response model for video sync operations"""
    processed_jobs: int
    registered_videos: int
    skipped_videos: int
    errors: List[str]


@router.get("/videos/managed", summary="List Tracked Videos")
def list_managed_videos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    workflow: Optional[str] = Query(None),
    posted: Optional[bool] = Query(None),
    job_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    List videos tracked in the database with filtering options.
    
    This endpoint returns videos that are properly tracked in the database,
    as opposed to the legacy endpoint that scans files dynamically.
    """
    try:
        # Build kwargs and avoid passing None for parameters that expect a str
        _list_kwargs = {
            "limit": limit,
            "offset": offset,
            "workflow": workflow,
            "posted": posted,
            "job_id": job_id,
        }
        # Filter out None values so we don't pass Optional[str] where str is required
        _list_kwargs = {k: v for k, v in _list_kwargs.items() if v is not None}

        videos = video_service.list_videos(**_list_kwargs)

        # Safety filter: exclude source/raw files incorrectly registered in the past
        # Keep only final MoneyPrinter outputs and Brainrot compilations
        def is_final_output(v: Dict[str, Any]) -> bool:
            workflow = v.get("workflow")
            video_type = v.get("video_type")
            filename = str(v.get("filename", "")).lower()
            # Never show obvious sources
            banned_markers = ["source", "download", "cropped", "raw"]
            if any(marker in filename for marker in banned_markers):
                return False
            if workflow == "moneyprinter" and video_type == "ai_generated":
                return True
            if workflow == "brainrot" and video_type == "compilation":
                return True
            return False

        videos = [v for v in videos if is_final_output(v)]
        
        # Add download URLs and enhance the response
        for video in videos:
            video["download_url"] = f"/api/download?path={video['file_path']}"
            
            # Check if file still exists
            video["file_exists"] = Path(video["file_path"]).exists()
            
            # Add thumbnail URL
            video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(video["file_path"])
            
            # Calculate size in MB for display
            if video.get("size_bytes"):
                video["size_mb"] = round(video["size_bytes"] / (1024 * 1024), 2)
        
        # Get total count for pagination (approximate)
        total_count = len(videos) if len(videos) < limit else limit + offset + 1
        
        return {
            "videos": videos,
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "has_more": len(videos) == limit
        }
        
    except Exception as e:
        logger.error(f"Failed to list managed videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {e}")


@router.get("/videos/managed/{video_id}", summary="Get Video Details")
def get_video_details(video_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific video."""
    try:
        video = video_service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Enhance the response
        video["download_url"] = f"/api/download?path={video['file_path']}"
        video["file_exists"] = Path(video["file_path"]).exists()
        video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(video["file_path"])
        
        if video.get("size_bytes"):
            video["size_mb"] = round(video["size_bytes"] / (1024 * 1024), 2)
        
        return video
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video: {e}")


@router.put("/videos/managed/{video_id}", summary="Update Video")
def update_video(video_id: str, request: UpdateVideoRequest) -> Dict[str, Any]:
    """Update video information."""
    try:
        # Check if video exists
        video = video_service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Prepare update fields
        update_fields = {}
        if request.posted is not None:
            update_fields["posted"] = request.posted
        if request.metadata is not None:
            update_fields["metadata"] = request.metadata
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update the video
        success = job_store.update_video(video_id, **update_fields)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update video")
        
        # Mark as posted in video service if needed
        if request.posted:
            video_service.mark_video_posted(video_id)
        
        # Return updated video
        updated_video = video_service.get_video(video_id)
        if not updated_video:
            logger.error(f"Updated video {video_id} not found after update")
            raise HTTPException(status_code=500, detail="Updated video not found")
        
        file_path = updated_video.get("file_path")
        if file_path:
            updated_video["download_url"] = f"/api/download?path={file_path}"
            updated_video["file_exists"] = Path(file_path).exists()
        else:
            updated_video["download_url"] = None
            updated_video["file_exists"] = False
        
        if updated_video.get("size_bytes"):
            updated_video["size_mb"] = round(updated_video["size_bytes"] / (1024 * 1024), 2)
        
        return updated_video
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update video: {e}")


@router.post("/videos/managed/{video_id}/mark-posted", summary="Mark Video as Posted")
def mark_video_posted(video_id: str) -> Dict[str, Any]:
    """Mark a video as posted."""
    try:
        success = video_service.mark_video_posted(video_id)
        if not success:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "video_id": video_id,
            "posted": True,
            "message": f"Video {video_id} marked as posted"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark video {video_id} as posted: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark video as posted: {e}")


@router.get("/videos/unposted", summary="Get Unposted Videos")
def get_unposted_videos(
    workflow: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    """Get videos that haven't been posted yet."""
    try:
        if workflow is not None:
            videos = video_service.get_unposted_videos(workflow=workflow, limit=limit)
        else:
            videos = video_service.get_unposted_videos(limit=limit)
        
        # Enhance the response
        for video in videos:
            video["download_url"] = f"/api/download?path={video['file_path']}"
            video["file_exists"] = Path(video["file_path"]).exists()
            video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(video["file_path"])
            
            if video.get("size_bytes"):
                video["size_mb"] = round(video["size_bytes"] / (1024 * 1024), 2)
        
        return {
            "videos": videos,
            "count": len(videos),
            "workflow_filter": workflow
        }
        
    except Exception as e:
        logger.error(f"Failed to get unposted videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get unposted videos: {e}")


@router.get("/videos/random", summary="Get Random Video")
def get_random_video(workflow: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Get a random video from the database."""
    try:
        video = video_service.get_random_video(workflow=workflow)
        
        if not video:
            raise HTTPException(status_code=404, detail="No videos found")
        
        # Enhance the response
        video["download_url"] = f"/api/download?path={video['file_path']}"
        video["file_exists"] = Path(video["file_path"]).exists()
        video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(video["file_path"])
        
        if video.get("size_bytes"):
            video["size_mb"] = round(video["size_bytes"] / (1024 * 1024), 2)
        
        return video
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get random video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get random video: {e}")


@router.get("/videos/stats/managed", summary="Get Video Statistics")
def get_managed_video_stats() -> Dict[str, Any]:
    """Get statistics about tracked videos."""
    try:
        return job_store.get_video_stats()
    except Exception as e:
        logger.error(f"Failed to get video stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video stats: {e}")


@router.post("/videos/sync/from-jobs", summary="Sync Videos from Job Results")
def sync_videos_from_jobs() -> SyncVideosResponse:
    """
    Sync video records from existing job results.
    
    This is useful for migrating existing videos to the new tracking system.
    """
    try:
        stats = video_service.sync_videos_from_job_results()
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return SyncVideosResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync videos from jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync videos: {e}")


@router.post("/videos/sync/orphaned", summary="Scan and Register Orphaned Videos")
def sync_orphaned_videos() -> Dict[str, Any]:
    """
    Scan the output directory for videos not tracked in the database and register them.
    """
    try:
        stats = video_service.scan_and_register_orphaned_videos()
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync orphaned videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync orphaned videos: {e}")


@router.delete("/videos/managed/{video_id}", summary="Delete Video Record")
def delete_video_record(video_id: str, delete_file: bool = Query(False)) -> Dict[str, Any]:
    """
    Delete a video record from the database.
    
    Args:
        video_id: ID of the video to delete
        delete_file: If true, also delete the physical video file
    """
    try:
        # Get video info before deletion
        video = video_service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        file_path = video["file_path"]
        file_deleted = False
        
        # Delete physical file if requested
        if delete_file:
            try:
                Path(file_path).unlink(missing_ok=True)
                file_deleted = True
                logger.info(f"Deleted video file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete video file {file_path}: {e}")
        
        # Delete database record
        success = job_store.delete_video(video_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete video record")
        
        return {
            "video_id": video_id,
            "record_deleted": True,
            "file_deleted": file_deleted,
            "file_path": file_path,
            "message": f"Video record deleted" + (f" and file removed" if file_deleted else "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")
