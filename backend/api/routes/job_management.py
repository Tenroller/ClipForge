"""
Job management endpoints.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
import uuid

from ...logging_config import get_logger, log_job_event
from ...database import get_job_store
from ...services.video_orchestrator import get_video_orchestrator
from ...models.requests import MoneyPrinterRequest, BrainrotRequest

from ...services.job_management import JobManagementService

router = APIRouter()
job_service = JobManagementService()
logger = get_logger("job_remake")
job_store = get_job_store()
video_orchestrator = get_video_orchestrator()


@router.get("/jobs/resumable", summary="Get Resumable Jobs")
def get_resumable_jobs() -> Dict[str, Any]:
    """Get jobs that can be resumed (failed or cancelled jobs)."""
    return job_service.get_resumable_jobs()


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Get job status by ID."""
    job = job_service.get_job(job_id)
    if not job:
        # Check tombstone (purged) to return 410 Gone for purged jobs
        try:
            from ...database import get_job_store as _get_job_store
            purged_reason = _get_job_store().is_purged(job_id)
            if purged_reason:
                raise HTTPException(status_code=410, detail=str(purged_reason))
        except HTTPException:
            # Re-raise intended HTTP exceptions
            raise
        except Exception:
            # Ignore tombstone lookup failures and fallthrough to 404
            pass
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/resumable", summary="Check if job is resumable")
def job_resumable(job_id: str) -> Dict[str, Any]:
    """Return whether a specific job can be resumed.

    Logic: job exists AND status in (error,cancelled) AND original request_data present AND last step present.
    """
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    status = job.get("status")
    can_resume = bool(status in ("error", "cancelled") and job.get("request_data") and job.get("step"))
    # Provide next_step if resumable
    next_step = None
    if can_resume:
        try:
            next_step = job_service._get_next_step_for_workflow(job.get("workflow"), job.get("step"))  # type: ignore
        except Exception:
            next_step = None
    return {"jobId": job_id, "can_resume": can_resume, "next_step": next_step}


@router.post("/jobs/{job_id}/remake", summary="Remake (requeue) a completed or failed job")
async def remake_job(job_id: str) -> Dict[str, Any]:
    """Clone a previous job's request parameters and enqueue a new job.

    Returns a response matching frontend expectation.
    """
    original = job_service.get_job(job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original job not found")

    workflow = original.get("workflow")
    request_data = original.get("request_data") or {}
    if not workflow:
        raise HTTPException(status_code=400, detail="Original job missing workflow")

    new_job_id = str(uuid.uuid4())

    try:
        # Create job in database first
        job_store.create_job(
            new_job_id,
            workflow,
            request_data,
            user_id=None
        )

        # Submit to orchestrator
        success = False
        
        if workflow == "moneyprinter":
            # Reconstruct request model (best effort)
            try:
                req_model = MoneyPrinterRequest(**request_data)
            except Exception:
                raise HTTPException(status_code=400, detail="Cannot reconstruct original request data for moneyprinter job")
            
            success = await video_orchestrator.submit_moneyprinter_job(new_job_id, req_model)
            
        elif workflow == "brainrot":
            try:
                req_model = BrainrotRequest(**request_data)
            except Exception:
                raise HTTPException(status_code=400, detail="Cannot reconstruct original request data for brainrot job")
            
            success = await video_orchestrator.submit_brainrot_job(new_job_id, req_model)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow '{workflow}' for remake")

        if not success:
            # Update job status to error
            job_store.update_job(
                new_job_id,
                status="error",
                error_message="Failed to submit to video processor"
            )
            raise HTTPException(status_code=500, detail="Failed to submit job to video processor")

        # Optional: log event
        try:
            log_job_event(logger, new_job_id, workflow, "remade", original_job=job_id)
        except Exception:
            pass

        # Wait briefly for persistence (non-blocking short retries)
        for _ in range(3):
            if job_store.get_job(new_job_id):
                break
            import time as _t
            _t.sleep(0.05)

        return {
            "status": "queued",
            "job_id": new_job_id,  # legacy snake expected by some callers
            "jobId": new_job_id,   # camelCase for consistency
            "original_job_id": job_id,
            "originalJobId": job_id,
            "workflow": workflow,
            "message": f"Remade job {job_id} as {new_job_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remake job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remake job: {e}")


@router.post("/jobs/{job_id}/resume", summary="Resume a failed/cancelled job from its last step")
async def resume_job(job_id: str) -> Dict[str, Any]:
    """Attempt to resume a previously failed or cancelled job.

    Strategy:
    - Validate original job exists and status in (error,cancelled).
    - Pull stored request_data: expects {func, args, kwargs, priority} shape inserted at job creation.
    - Determine function to call based on workflow (explicit mapping overrides stored func for safety).
    - Create new job ID; set resumed_from, resume_attempt = parent.resume_attempt + 1, append to parent's resumed_to list.
    - Enqueue new job starting from next_step (currently we just re-run full pipeline; future: partial resume based on step).
    - Return new job identifiers.
    """
    parent = job_service.get_job(job_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Original job not found")

    status = parent.get("status")
    if status not in ("error", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job status '{status}' not resumable")

    workflow = parent.get("workflow")
    request_data = parent.get("request_data") or {}
    if not workflow or not isinstance(request_data, dict):
        raise HTTPException(status_code=400, detail="Original job missing workflow or request data")

    # Enforce max resume attempts
    try:
        from ...core.config import AppConfig
        cfg = AppConfig.from_env()
        current_attempt = parent.get("resume_attempt") or 1
        if current_attempt >= cfg.max_resume_attempts:
            raise HTTPException(status_code=400, detail=f"Maximum resume attempts ({cfg.max_resume_attempts}) reached for this job chain")
    except HTTPException:
        raise
    except Exception:
        pass  # Fail open if config load has an issue

    new_job_id = str(uuid.uuid4())

    # Determine starting step for partial continuation
    parent_step = parent.get("step") or "init"
    start_step = None
    if workflow == "moneyprinter":
        ordered = ["validate_env", "fetch_music", "script_generation", "search_terms", "stock_download", "tts", "subtitles", "compose_video"]
        if parent_step in ordered:
            idx = ordered.index(parent_step)
            # Next step after the last completed (parent failed at parent_step so resume there or after?)
            # If failure mid-step we re-execute that step; choose parent_step as start
            start_step = parent_step
    elif workflow == "brainrot":
        # Brainrot steps: process_video -> generate_compilations
        if parent_step == "process_video":
            # If failed during process_video, start there
            start_step = "process_video"
        elif parent_step == "generate_compilations":
            start_step = "generate_compilations"

    resume_metadata = {"start_step": start_step, "resumed_from": job_id, "parent_step": parent_step}

    try:
        # Create job in database first
        job_store.create_job(
            new_job_id,
            workflow,
            request_data,
            user_id=None
        )

        # Submit to orchestrator
        success = False
        
        if workflow == "moneyprinter":
            try:
                exec_payload = MoneyPrinterRequest(**request_data)
            except Exception:
                raise HTTPException(status_code=400, detail="Cannot reconstruct MoneyPrinterRequest for resume")
            
            success = await video_orchestrator.submit_moneyprinter_job(new_job_id, exec_payload)
            
        elif workflow == "brainrot":
            try:
                exec_payload = BrainrotRequest(**request_data)
            except Exception:
                raise HTTPException(status_code=400, detail="Cannot reconstruct BrainrotRequest for resume")
            
            success = await video_orchestrator.submit_brainrot_job(new_job_id, exec_payload)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow '{workflow}' for resume")

        if not success:
            # Update job status to error
            job_store.update_job(
                new_job_id,
                status="error",
                error_message="Failed to submit to video processor"
            )
            raise HTTPException(status_code=500, detail="Failed to submit job to video processor")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed preparing resume: {e}")

    # Update resume linkage metadata
    try:
        parent_children = parent.get("resumed_to") or []
        parent_children.append(new_job_id)
        parent_attempt = parent.get("resume_attempt") or 1
        job_store.update_job(job_id, resumed_to=parent_children)
        job_store.update_job(new_job_id, resumed_from=job_id, resume_attempt=parent_attempt + 1, resume_data=resume_metadata)
    except Exception as e:
        logger.warning(f"Failed to update resume linkage metadata for {job_id}->{new_job_id}: {e}")

    # Brief wait for persistence
    for _ in range(3):
        if job_store.get_job(new_job_id):
            break
        import time as _t
        _t.sleep(0.05)

    return {
        "status": "queued",
        "job_id": new_job_id,
        "jobId": new_job_id,
        "resumed_from": job_id,
        "workflow": workflow,
        "resume_attempt": (parent.get("resume_attempt") or 1) + 1
    }


@router.get("/jobs/{job_id}/logs", summary="Get Job Logs")
def get_job_logs(job_id: str) -> Dict[str, Any]:
    """Get comprehensive logs for a specific job."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_service.get_job_logs(job_id)


@router.get("/jobs/{job_id}/lineage", summary="Get job lineage (ancestors & descendants)")
def get_job_lineage(job_id: str) -> Dict[str, Any]:
    """Return ancestry and descendant chain for a job.

    ancestors: ordered list from root -> immediate parent (excludes job itself)
    descendants: breadth-first list of all jobs resumed from this job (children, grandchildren, ...)
    """
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    store = job_store

    # Ascend chain
    ancestors = []
    current = job
    safety = 0
    visited = set([job_id])
    while current.get("resumed_from") and safety < 100:
        parent_id = current.get("resumed_from")
        if not isinstance(parent_id, str) or parent_id in visited:
            break
        parent = store.get_job(parent_id)
        if not parent:
            break
        ancestors.append({
            "id": parent["id"],
            "status": parent.get("status"),
            "resume_attempt": parent.get("resume_attempt"),
            "resumed_from": parent.get("resumed_from"),
            "children_count": len(parent.get("resumed_to") or [])
        })
        visited.add(parent_id)
        current = parent
        safety += 1

    ancestors.reverse()  # root first

    # Descend chain (BFS)
    descendants = []
    queue = list(job.get("resumed_to") or [])
    safety = 0
    while queue and safety < 500:
        child_id = queue.pop(0)
        if child_id in visited:
            continue
        child = store.get_job(child_id)
        if not child:
            continue
        descendants.append({
            "id": child["id"],
            "status": child.get("status"),
            "resume_attempt": child.get("resume_attempt"),
            "resumed_from": child.get("resumed_from"),
            "children_count": len(child.get("resumed_to") or [])
        })
        visited.add(child_id)
        for gc in (child.get("resumed_to") or []):
            if gc not in visited:
                queue.append(gc)
        safety += 1

    return {
        "jobId": job_id,
        "ancestors": ancestors,
        "descendants": descendants,
        "ancestor_count": len(ancestors),
        "descendant_count": len(descendants)
    }


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


@router.delete("/jobs/{job_id}", summary="Delete Job")
def delete_job(job_id: str):
    """Delete a job from the database."""
    if not job_service.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "deleted", "jobId": job_id}


@router.post("/jobs/{job_id}/purge", summary="Purge (delete) a job and create tombstone")
def purge_job(job_id: str):
    purged_reason = "Purged by request"
    if job_service.purge_job(job_id, purged_reason):
        return {"status": "purged", "jobId": job_id, "reason": purged_reason}
    raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs/cleanup", summary="Cleanup Jobs")
def cleanup_jobs(
    older_than_days: int = 7,
    statuses: Optional[list[str]] = None
):
    """Cleanup old jobs based on age and status."""
    if statuses is None:
        statuses = ["done", "error", "cancelled"]
    
    result = job_service.cleanup_jobs(older_than_days, statuses)
    return {
        "cleaned_up": result["cleaned_count"],
        "details": result["details"]
    }
