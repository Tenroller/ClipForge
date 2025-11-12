"""
Job callback endpoints for video processor notifications.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...logging_config import get_logger
from ...database import get_job_store
from ...utils.progress_tracker import get_progress_tracker

router = APIRouter()
logger = get_logger("job_callbacks")

# Get database instance
job_store = get_job_store()


class JobCallbackPayload(BaseModel):
    """Payload for job status callbacks from video processor."""
    job_id: str
    status: str
    progress: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


@router.post(
    "/jobs/callback",
    summary="Receive job status updates from video processor",
    response_model=Dict[str, str]
)
async def job_callback(payload: JobCallbackPayload) -> Dict[str, str]:
    """
    Receive job status updates from video processor.
    
    This endpoint is called by the video processor when job status changes.
    """
    try:
        job_id = payload.job_id
        logger.info(f"Received callback for job {job_id}: status={payload.status}")
        
        # Validate job exists
        job = job_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found for callback")
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update job in database
        update_fields = {
            "status": payload.status,
        }

        if payload.current_step:
            update_fields["step"] = payload.current_step

        if payload.error_message:
            update_fields["error"] = payload.error_message

        if payload.result_data:
            update_fields["result"] = payload.result_data

        # Handle job start - set started_at timestamp
        import datetime
        if payload.status == "running" and not job.get("started_at"):
            update_fields["started_at"] = datetime.datetime.now(datetime.timezone.utc)

        # Handle job completion
        if payload.status in ["completed", "failed", "cancelled"]:
            update_fields["ended_at"] = datetime.datetime.now(datetime.timezone.utc)
            if job.get("started_at"):
                started_at = job["started_at"]
                if isinstance(started_at, str):
                    import dateutil.parser
                    started_at = dateutil.parser.isoparse(started_at)
                duration = datetime.datetime.now(datetime.timezone.utc) - started_at
                update_fields["duration_seconds"] = int(duration.total_seconds())
        
        job_store.update_job(job_id, **update_fields)
        logger.info(f"Updated job {job_id} status to {payload.status}")
        
        # Update progress tracker if available
        try:
            tracker = get_progress_tracker(job_id)
            
            if payload.status == "completed":
                # Just update step, no logging
                pass
            elif payload.status == "failed":
                # Just update status, no logging
                pass
                
        except Exception as e:
            logger.warning(f"Failed to update progress tracker for job {job_id}: {e}")
        
        return {"status": "success", "job_id": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process callback for job {payload.job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")