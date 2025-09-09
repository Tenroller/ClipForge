"""
Job management endpoints.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from ...services.job_management import JobManagementService

router = APIRouter()
job_service = JobManagementService()


@router.get("/jobs/resumable", summary="Get Resumable Jobs")
def get_resumable_jobs() -> Dict[str, Any]:
    """Get jobs that can be resumed (failed or cancelled jobs)."""
    return job_service.get_resumable_jobs()


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Get job status by ID."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/logs", summary="Get Job Logs")
def get_job_logs(job_id: str) -> Dict[str, Any]:
    """Get comprehensive logs for a specific job."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_service.get_job_logs(job_id)


@router.get("/jobs", summary="List Jobs")
def list_jobs(
    limit: int = 50,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """List jobs with optional filtering."""
    jobs = job_service.list_jobs(limit=min(limit, 100), status=status)
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/jobs/{job_id}/cancel", summary="Cancel Job")
def cancel_job(job_id: str):
    """Cancel a job."""
    if not job_service.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
    return {"status": "cancelled", "jobId": job_id}
