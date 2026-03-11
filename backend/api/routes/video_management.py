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
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    workflow: Optional[str] = Query(None),
    posted: Optional[bool] = Query(None),
    job_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in filename/title"),
    # Sorting params
    sort_by: Optional[str] = Query("created_at", description="Sort by: created_at, file_size, duration, filename, workflow, posted"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    # Legacy AI metadata filters (applied post-query)
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    min_viral_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum viral score"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence"),
) -> Dict[str, Any]:
    """
    List videos tracked in the database with server-side filtering, sorting, and pagination.

    Filtering by workflow, posted status, and filename search are handled in the database query.
    The response includes an accurate ``total`` count for pagination.
    """
    try:
        # Use server-side search_videos for filtering, sorting, and pagination
        result = job_store.search_videos(
            limit=limit,
            offset=offset,
            workflow=workflow,
            posted=posted,
            job_id=job_id,
            search=search,
            sort_by=sort_by or "created_at",
            sort_order=sort_order or "desc",
        )

        videos = result["videos"]
        total = result["total"]

        # Safety filter: exclude source/raw files incorrectly registered in the past
        def is_final_output(v: Dict[str, Any]) -> bool:
            wf = v.get("workflow")
            video_type = v.get("video_type")
            filename = str(v.get("filename", "")).lower()
            banned_markers = ["source", "download", "cropped", "raw"]
            if any(marker in filename for marker in banned_markers):
                return False
            if wf == "moneyprinter" and video_type == "ai_generated":
                return True
            if wf == "brainrot" and video_type == "compilation":
                return True
            if wf == "podcastclips" and video_type == "podcast_clip":
                return True
            return False

        videos = [v for v in videos if is_final_output(v)]

        # Apply legacy AI metadata filters (post-query, kept for backward compatibility)
        if tags:
            tag_list = [t_val.strip() for t_val in tags.split(",")]
            videos = [
                v for v in videos
                if v.get("metadata", {}).get("tags") and
                any(tag in v["metadata"]["tags"] for tag in tag_list)
            ]

        if min_viral_score is not None:
            videos = [
                v for v in videos
                if v.get("metadata", {}).get("viral_score", 0) >= min_viral_score
            ]

        if min_confidence is not None:
            videos = [
                v for v in videos
                if v.get("metadata", {}).get("confidence", 0.0) >= min_confidence
            ]

        # Add download URLs and enhance the response
        for video in videos:
            video["download_url"] = f"/api/download?path={video['file_path']}"
            video["file_exists"] = Path(video["file_path"]).exists()
            video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(video["file_path"])

            if video.get("size_bytes"):
                video["size_mb"] = round(video["size_bytes"] / (1024 * 1024), 2)

        return {
            "videos": videos,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < total,
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


@router.patch("/videos/managed/{video_id}/metadata", summary="Update Video Metadata")
def update_video_metadata(video_id: str, metadata_updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update specific fields in video metadata (AI-generated metadata).

    This endpoint allows partial updates to metadata fields like title, tags, caption, etc.
    Existing metadata fields not included in the update will be preserved.
    """
    try:
        # Check if video exists
        video = video_service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get existing metadata
        existing_metadata = video.get("metadata", {})

        # Merge updates with existing metadata
        updated_metadata = {**existing_metadata, **metadata_updates}

        # Update the video with merged metadata
        success = job_store.update_video(video_id, metadata=updated_metadata)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update video metadata")

        logger.info(f"Updated metadata for video {video_id}: {list(metadata_updates.keys())}")

        # Return updated video
        updated_video = video_service.get_video(video_id)
        if not updated_video:
            raise HTTPException(status_code=500, detail="Updated video not found")

        # Enhance response
        file_path = updated_video.get("file_path")
        if file_path:
            updated_video["download_url"] = f"/api/download?path={file_path}"
            updated_video["file_exists"] = Path(file_path).exists()
            updated_video["thumbnail_url"] = thumbnail_service.get_thumbnail_url(file_path)

        if updated_video.get("size_bytes"):
            updated_video["size_mb"] = round(updated_video["size_bytes"] / (1024 * 1024), 2)

        return updated_video

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update video metadata for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update metadata: {e}")


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


# ============================================================================
# Podcast Projects API - Source videos and their clips
# ============================================================================

@router.get("/projects/podcast", summary="List Podcast Projects")
def list_podcast_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status: active, expired, analysis_complete"),
    sort_by: Optional[str] = Query("created_at", description="Sort by: created_at, clips_count, title"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc")
) -> Dict[str, Any]:
    """
    List podcast projects (source YouTube videos with their generated clips).

    Each project represents a source YouTube video that was used to generate clips.
    Returns metadata about the source video and count of clips generated from it.
    """
    try:
        from sqlalchemy import func, distinct
        from ...database import SessionLocal, Video, Job, YouTubeVideo

        with SessionLocal() as session:
            # Get unique source videos from podcastclips jobs
            # Join jobs with videos to get source info and clip counts
            projects = []

            # Get all podcastclips jobs
            jobs = session.query(Job).filter(
                Job.workflow == "podcastclips",
                Job.status.in_(["done", "completed", "running", "queued"])
            ).order_by(Job.created_at.desc()).all()

            seen_sources = set()

            for job in jobs:
                request_data = job.request_data or {}
                youtube_url = request_data.get("youtubeUrl", "")

                if not youtube_url or youtube_url in seen_sources:
                    continue

                seen_sources.add(youtube_url)

                # Get clips count for this job
                clips = session.query(Video).filter(
                    Video.job_id == job.id,
                    Video.workflow == "podcastclips"
                ).all()

                # Get source video info from YouTube cache if available
                from ...utils.youtube import extract_video_id
                try:
                    video_id = extract_video_id(youtube_url)
                    yt_cache = session.query(YouTubeVideo).filter(
                        YouTubeVideo.video_id == video_id
                    ).first()
                except Exception:
                    video_id = None
                    yt_cache = None

                # Determine project status
                project_status = "active"
                if job.status in ["done", "completed"]:
                    project_status = "analysis_complete"
                elif job.status == "error":
                    project_status = "error"

                # Get total duration from request or cache
                total_duration = None
                if yt_cache:
                    total_duration = yt_cache.duration_seconds

                # Build project info
                project = {
                    "id": job.id,
                    "source_video_id": video_id,
                    "youtube_url": youtube_url,
                    "title": yt_cache.title if yt_cache else request_data.get("title", "Unknown Video"),
                    "channel": yt_cache.normalized_url.split("/")[-1] if yt_cache and yt_cache.normalized_url else "",
                    "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
                    "total_duration": total_duration,
                    "total_duration_formatted": _format_duration(total_duration) if total_duration else "Unknown",
                    "clips_count": len(clips),
                    "status": project_status,
                    "job_status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    # Format options from request
                    "format_options": {
                        "aspect_ratio": "9:16",
                        "mode": request_data.get("enableMixedMode", True) and "Auto" or "Single",
                        "face_tracking": request_data.get("enableMixedMode", True)
                    },
                    # Time range used
                    "time_range": {
                        "start": "0:00",
                        "end": _format_duration(total_duration) if total_duration else "Unknown"
                    }
                }

                projects.append(project)

                if len(projects) >= limit:
                    break

            # Apply sorting
            def get_sort_value(p: Dict[str, Any]) -> Any:
                if sort_by == "clips_count":
                    return p.get("clips_count", 0)
                elif sort_by == "title":
                    return p.get("title", "")
                else:  # created_at
                    return p.get("created_at", "")

            reverse_sort = (sort_order.lower() == "desc")
            projects = sorted(projects, key=get_sort_value, reverse=reverse_sort)

            # Apply offset and limit
            projects = projects[offset:offset + limit]

            return {
                "projects": projects,
                "total": len(seen_sources),
                "offset": offset,
                "limit": limit,
                "has_more": len(projects) == limit
            }

    except Exception as e:
        logger.error(f"Failed to list podcast projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {e}")


@router.get("/projects/podcast/{project_id}", summary="Get Podcast Project Details")
def get_podcast_project(project_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a podcast project including all its clips.
    """
    try:
        from ...database import SessionLocal, Video, Job, YouTubeVideo

        with SessionLocal() as session:
            # Get the job
            job = session.query(Job).filter(Job.id == project_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Project not found")

            if job.workflow != "podcastclips":
                raise HTTPException(status_code=400, detail="Not a podcast clips project")

            request_data = job.request_data or {}
            youtube_url = request_data.get("youtubeUrl", "")

            # Get source video info
            from ...utils.youtube import extract_video_id
            try:
                video_id = extract_video_id(youtube_url)
                yt_cache = session.query(YouTubeVideo).filter(
                    YouTubeVideo.video_id == video_id
                ).first()
            except Exception:
                video_id = None
                yt_cache = None

            # Get all clips for this project
            clips_query = session.query(Video).filter(
                Video.job_id == project_id,
                Video.workflow == "podcastclips"
            ).order_by(Video.created_at.desc())

            clips = []
            for clip in clips_query.all():
                clip_metadata = clip.video_metadata or {}

                clips.append({
                    "id": str(clip.id),
                    "filename": clip.filename,
                    "file_path": clip.file_path,
                    "download_url": f"/api/download?path={clip.file_path}",
                    "thumbnail_url": thumbnail_service.get_thumbnail_url(clip.file_path),
                    "duration_seconds": clip.duration_seconds,
                    "duration_formatted": _format_duration(clip.duration_seconds) if clip.duration_seconds else "0:00",
                    "size_bytes": clip.size_bytes,
                    "size_mb": round(clip.size_bytes / (1024 * 1024), 2) if clip.size_bytes else 0,
                    "posted": clip.posted,
                    "posted_at": clip.posted_at.isoformat() if clip.posted_at else None,
                    "created_at": clip.created_at.isoformat() if clip.created_at else None,
                    # Clip-specific metadata
                    "viral_score": clip_metadata.get("viral_score", 0),
                    "title": clip_metadata.get("title", ""),
                    "hook": clip_metadata.get("hook", ""),
                    "time_interval": {
                        "start": clip_metadata.get("start_time", 0),
                        "end": clip_metadata.get("end_time", 0),
                        "start_formatted": _format_duration(clip_metadata.get("start_time", 0)),
                        "end_formatted": _format_duration(clip_metadata.get("end_time", 0))
                    },
                    "engagement_factors": clip_metadata.get("engagement_factors", []),
                    "likes": clip_metadata.get("likes", 0),
                    "dislikes": clip_metadata.get("dislikes", 0),
                    "render_status": clip_metadata.get("render_status", "preview"),
                    "file_exists": Path(clip.file_path).exists() if clip.file_path else False
                })

            # Sort clips by viral score
            clips = sorted(clips, key=lambda c: c.get("viral_score", 0), reverse=True)

            # Build project response
            total_duration = yt_cache.duration_seconds if yt_cache else None

            return {
                "id": project_id,
                "source_video_id": video_id,
                "youtube_url": youtube_url,
                "title": yt_cache.title if yt_cache else request_data.get("title", "Unknown Video"),
                "channel": "",  # Could extract from URL
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
                "total_duration": total_duration,
                "total_duration_formatted": _format_duration(total_duration) if total_duration else "Unknown",
                "clips": clips,
                "clips_count": len(clips),
                "status": "analysis_complete" if job.status in ["done", "completed"] else job.status,
                "job_status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "request_params": request_data
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get podcast project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {e}")


@router.patch("/projects/podcast/{project_id}/clips/{clip_id}", summary="Update Clip Metadata")
def update_clip_metadata(project_id: str, clip_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata for a specific clip (likes, dislikes, render_status, etc.).
    """
    try:
        # Verify clip belongs to project
        video = video_service.get_video(clip_id)
        if not video:
            raise HTTPException(status_code=404, detail="Clip not found")

        if video.get("job_id") != project_id:
            raise HTTPException(status_code=400, detail="Clip does not belong to this project")

        # Get existing metadata and merge
        existing_metadata = video.get("metadata", {})

        # Only allow certain fields to be updated
        allowed_fields = ["likes", "dislikes", "render_status", "title", "custom_notes"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        updated_metadata = {**existing_metadata, **filtered_updates}

        # Update
        success = job_store.update_video(clip_id, metadata=updated_metadata)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update clip")

        return {
            "clip_id": clip_id,
            "updated_fields": list(filtered_updates.keys()),
            "metadata": updated_metadata
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update clip {clip_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update clip: {e}")


@router.post("/projects/podcast/{project_id}/clips/{clip_id}/render", summary="Mark Clip for Rendering")
def render_clip(project_id: str, clip_id: str) -> Dict[str, Any]:
    """
    Mark a clip for high-quality rendering (changes render_status to 'rendering').

    In the current implementation, clips are already rendered in preview quality.
    This endpoint is a placeholder for future high-quality rendering support.
    """
    try:
        video = video_service.get_video(clip_id)
        if not video:
            raise HTTPException(status_code=404, detail="Clip not found")

        if video.get("job_id") != project_id:
            raise HTTPException(status_code=400, detail="Clip does not belong to this project")

        # Update render status
        existing_metadata = video.get("metadata", {})
        existing_metadata["render_status"] = "rendered"

        success = job_store.update_video(clip_id, metadata=existing_metadata)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update clip")

        return {
            "clip_id": clip_id,
            "render_status": "rendered",
            "message": "Clip marked as rendered",
            "download_url": f"/api/download?path={video['file_path']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render clip {clip_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to render clip: {e}")


@router.delete("/projects/podcast/{project_id}/clips/{clip_id}", summary="Delete Clip")
def delete_project_clip(project_id: str, clip_id: str, delete_file: bool = Query(True)) -> Dict[str, Any]:
    """Delete a clip from a project."""
    try:
        video = video_service.get_video(clip_id)
        if not video:
            raise HTTPException(status_code=404, detail="Clip not found")

        if video.get("job_id") != project_id:
            raise HTTPException(status_code=400, detail="Clip does not belong to this project")

        file_path = video["file_path"]
        file_deleted = False

        if delete_file:
            try:
                Path(file_path).unlink(missing_ok=True)
                file_deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete clip file {file_path}: {e}")

        success = job_store.delete_video(clip_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete clip record")

        return {
            "clip_id": clip_id,
            "project_id": project_id,
            "record_deleted": True,
            "file_deleted": file_deleted
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete clip {clip_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete clip: {e}")


@router.delete("/projects/podcast/{project_id}", summary="Delete Podcast Project")
def delete_podcast_project(project_id: str, delete_files: bool = Query(True)) -> Dict[str, Any]:
    """
    Delete a podcast project and all its associated clips.
    
    Args:
        project_id: ID of the project (job) to delete
        delete_files: If true, also delete the physical video files (default: True)
    
    Returns:
        Summary of deleted items (clips count, files deleted, etc.)
    """
    try:
        from ...database import SessionLocal, Video, Job

        with SessionLocal() as session:
            # Verify the job exists and is a podcastclips job
            job = session.query(Job).filter(Job.id == project_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Project not found")
            
            if job.workflow != "podcastclips":
                raise HTTPException(status_code=400, detail="Not a podcast clips project")
            
            # Get all clips for this project
            clips = session.query(Video).filter(
                Video.job_id == project_id,
                Video.workflow == "podcastclips"
            ).all()
            
            clips_deleted = 0
            files_deleted = 0
            errors = []
            
            # Delete clip files and records
            for clip in clips:
                # Delete the physical file if requested
                if delete_files and clip.file_path:
                    try:
                        Path(clip.file_path).unlink(missing_ok=True)
                        files_deleted += 1
                    except Exception as e:
                        errors.append(f"Failed to delete file {clip.file_path}: {e}")
                        logger.warning(f"Failed to delete clip file {clip.file_path}: {e}")
                
                # Delete the database record
                session.delete(clip)
                clips_deleted += 1
            
            # Delete the job record
            session.delete(job)
            session.commit()
            
            logger.info(f"Deleted project {project_id}: {clips_deleted} clips, {files_deleted} files")
            
            return {
                "project_id": project_id,
                "deleted": True,
                "clips_deleted": clips_deleted,
                "files_deleted": files_deleted,
                "errors": errors if errors else None,
                "message": f"Project deleted successfully with {clips_deleted} clips"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {e}")


def _format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS string."""
    if seconds is None:
        return "0:00"

    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


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
