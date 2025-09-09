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
