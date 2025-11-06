"""
System management and maintenance endpoints.
"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/debug/jobs", summary="Debug Job Information")
def debug_jobs() -> Dict[str, Any]:
    """Get debug information about jobs and orchestrator status."""
    from ...database import get_job_store
    from ...services.video_orchestrator import get_video_orchestrator
    
    job_store = get_job_store()
    video_orchestrator = get_video_orchestrator()
    
    # Get all jobs from database
    all_jobs = job_store.list_jobs(limit=100)
    
    # Get orchestrator status
    try:
        orchestrator_status = {
            "registered_processors": len(video_orchestrator.processor_manager.processors),
            "active_jobs": len([job for job in all_jobs if job.get("status") in ["processing", "queued", "pending"]]),
        }
    except Exception as e:
        orchestrator_status = {"error": str(e)}
    
    return {
        "total_jobs_in_db": len(all_jobs),
        "job_ids": [job["id"] for job in all_jobs],
        "orchestrator_status": orchestrator_status,
        "recent_jobs": all_jobs[:5] if all_jobs else []
    }


# Cleanup and maintenance routes (moved from legacy app)
@router.get("/cleanup/temp-files/stats", summary="Get temporary files statistics")
def get_temp_files_stats() -> Dict[str, Any]:
    """Get statistics about temporary files using the temp manager.

    This mirrors the legacy endpoints so the frontend can call /api/cleanup/temp-files/stats.
    """
    try:
        from ...utils.file_management import get_temp_manager

        manager = get_temp_manager()
        stats = manager.get_stats()

        total_files = sum(d.get('file_count', 0) for d in stats.values() if isinstance(d, dict))
        total_size = sum(d.get('total_size_mb', 0) for d in stats.values() if isinstance(d, dict))

        return {
            "directories": list(stats.values()),
            "total_files": total_files,
            "total_size_mb": round(total_size, 2),
            "manager_stats": {
                "registered_directories": len(stats),
                "background_cleanup_active": True
            }
        }
    except Exception as e:
        # Return a structured error similar to legacy behavior
        raise


@router.post("/cleanup/temp-files", summary="Clean up temporary files")
def cleanup_temp_files() -> Dict[str, Any]:
    """Trigger manual cleanup of all registered temporary file directories."""
    try:
        from ...utils.file_management import get_temp_manager

        manager = get_temp_manager()
        results = manager.cleanup_all(force=True)

        total_files = sum(r.get('files_removed', 0) for r in results.values())
        total_space = sum(r.get('space_freed_mb', 0) for r in results.values())
        all_errors = []
        for dir_results in results.values():
            all_errors.extend(dir_results.get('errors', []))

        return {
            "deleted_files": total_files,
            "freed_space_mb": round(total_space, 2),
            "directories_cleaned": list(results.keys()),
            "errors": all_errors,
            "directory_details": results
        }
    except Exception:
        # Let FastAPI convert to 500 with stacktrace logged by server
        raise


# YouTube cache management endpoints
@router.get("/cache/youtube/stats", summary="Get YouTube cache statistics")
def get_youtube_cache_stats() -> Dict[str, Any]:
    """Get statistics about the YouTube video cache."""
    try:
        from ...utils.youtube_cache import get_cache_stats

        stats = get_cache_stats()
        return stats
    except Exception:
        raise


@router.get("/cache/youtube/videos", summary="List cached YouTube videos")
def list_cached_videos(limit: int = 100, offset: int = 0, order_by: str = "last_used_at") -> Dict[str, Any]:
    """
    List cached YouTube videos.

    Args:
        limit: Maximum number of videos to return (default: 100)
        offset: Number of videos to skip (default: 0)
        order_by: Sort order - "last_used_at", "created_at", or "download_count" (default: "last_used_at")
    """
    try:
        from ...database import get_job_store

        job_store = get_job_store()
        videos = job_store.list_youtube_videos(limit=limit, offset=offset, order_by=order_by)

        return {
            "videos": videos,
            "count": len(videos),
            "limit": limit,
            "offset": offset
        }
    except Exception:
        raise


@router.post("/cache/youtube/cleanup", summary="Trigger YouTube cache cleanup")
def trigger_youtube_cache_cleanup(days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
    """
    Manually trigger YouTube cache cleanup.

    Args:
        days: Delete videos unused for this many days (default: 30)
        dry_run: If true, only report what would be deleted without actually deleting (default: false)
    """
    try:
        from ...utils.youtube_cache import cleanup_old_cache

        result = cleanup_old_cache(days=days, dry_run=dry_run)
        return result
    except Exception:
        raise


@router.get("/cache/youtube/service/status", summary="Get cache cleanup service status")
def get_cache_service_status() -> Dict[str, Any]:
    """Get the status of the automatic cache cleanup service."""
    try:
        from ...services.cache_cleanup import get_cleanup_service

        service = get_cleanup_service()
        return service.get_status()
    except Exception:
        raise


@router.post("/cache/youtube/service/run", summary="Run cache cleanup now")
def run_cache_cleanup_now() -> Dict[str, Any]:
    """Manually trigger the cache cleanup service to run immediately."""
    try:
        from ...services.cache_cleanup import get_cleanup_service

        service = get_cleanup_service()
        stats = service.run_now()
        return {
            "message": "Cache cleanup completed",
            "stats": stats
        }
    except Exception:
        raise
