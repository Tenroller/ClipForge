"""
System management and maintenance endpoints.
"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/debug/jobs", summary="Debug Job Information")
def debug_jobs() -> Dict[str, Any]:
    """Get debug information about jobs and queue status."""
    from ...database import get_job_store
    from ...job_queue_unified import get_job_queue
    
    job_store = get_job_store()
    job_queue = get_job_queue()
    
    # Get all jobs from database
    all_jobs = job_store.list_jobs(limit=100)
    
    # Get queue status
    try:
        queue_status = {
            "queue_size": len(job_queue.queue) if hasattr(job_queue, 'queue') else 0,
            "total_jobs": len(job_queue.jobs) if hasattr(job_queue, 'jobs') else 0,
        }
    except Exception as e:
        queue_status = {"error": str(e)}
    
    return {
        "total_jobs_in_db": len(all_jobs),
        "job_ids": [job["id"] for job in all_jobs],
        "queue_status": queue_status,
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
