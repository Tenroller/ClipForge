"""
REST API endpoints for video processing
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from ..models import (
    ProcessingJobRequest, ProcessingJobResponse, JobStatusResponse,
    JobListResponse, JobCancelRequest, HealthResponse, ProcessorStatusResponse,
    JobStatus, WorkflowType
)
from ..core.simple_queue import ProcessorJobQueue
from ..services.video_processing import VideoProcessingService

from loguru import logger

# Bind logger with context for this module
logger = logger.bind(name="api.routes")

router = APIRouter()

# These will be injected by the main app
job_queue: Optional[ProcessorJobQueue] = None
video_service: Optional[VideoProcessingService] = None
processor_id: str = "processor-1"
start_time = datetime.now(timezone.utc)


def set_dependencies(queue: ProcessorJobQueue, service: VideoProcessingService, pid: str):
    """Set the dependencies for the router."""
    global job_queue, video_service, processor_id
    job_queue = queue
    video_service = service
    processor_id = pid


@router.post("/jobs", response_model=ProcessingJobResponse)
async def create_job(request: ProcessingJobRequest):
    """Create a new processing job."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    try:
        # Validate workflow type
        if request.workflow not in [WorkflowType.MONEYPRINTER, WorkflowType.BRAINROT, WorkflowType.PODCASTCLIPS]:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow: {request.workflow}")
        
        # Add job to queue
        success = await job_queue.add_job(
            job_id=request.job_id,
            workflow=request.workflow,
            request_data=request.request_data,
            priority=request.priority,
            callback_url=request.callback_url
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add job to queue")
        
        logger.info(f"Created job {request.job_id} with workflow {request.workflow}")
        
        return ProcessingJobResponse(
            job_id=request.job_id,
            status=JobStatus.QUEUED,
            message="Job created and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Failed to create job {request.job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a specific job."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    job_status = await job_queue.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 50,
    page: int = 1
):
    """List jobs with optional filtering."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    if limit > 100:
        limit = 100
    
    jobs = await job_queue.list_jobs(status=status, limit=limit)
    
    return JobListResponse(
        jobs=jobs,
        total=len(jobs),
        page=page,
        page_size=limit
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Optional[JobCancelRequest] = None):
    """Cancel a job."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    if request is None:
        request = JobCancelRequest(reason=None)
    
    success = await job_queue.cancel_job(job_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or could not be cancelled")
    
    return {"message": f"Job {job_id} cancelled", "reason": request.reason}


@router.get("/status", response_model=ProcessorStatusResponse)
async def get_processor_status():
    """Get the status of this processor."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    stats = job_queue.get_stats()
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
    
    return ProcessorStatusResponse(
        processor_id=processor_id,
        status="running" if stats["running"] else "stopped",
        current_jobs=stats["active_jobs"],
        max_concurrent_jobs=stats["max_concurrent_jobs"],
        total_processed=stats["total_jobs"],
        uptime_seconds=int(uptime),
        last_heartbeat=datetime.now(timezone.utc),
        available_workflows=[WorkflowType.MONEYPRINTER, WorkflowType.BRAINROT, WorkflowType.PODCASTCLIPS]
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not initialized")
    
    try:
        stats = job_queue.get_stats()
        
        # Get system resources with fallback
        system_resources = {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0}
        try:
            import psutil
            system_resources = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
            }
        except ImportError:
            logger.warning("psutil not available, using default system resource values")
        except Exception as e:
            logger.warning(f"Failed to get system resources: {e}")
        
        return HealthResponse(
            status="healthy",
            processor_id=processor_id,
            timestamp=datetime.now(timezone.utc),
            queue_size=stats["queued_jobs"],
            active_jobs=stats["active_jobs"],
            system_resources=system_resources
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


@router.post("/admin/cleanup")
async def cleanup_old_jobs(max_age_hours: int = 24):
    """Admin endpoint to cleanup old jobs."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    try:
        removed = job_queue.cleanup_old_jobs(max_age_hours)
        return {"message": f"Cleaned up {removed} old jobs"}
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/stop")
async def stop_processor():
    """Admin endpoint to stop the processor."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    try:
        await job_queue.stop_processing()
        return {"message": "Processor stopped"}
    except Exception as e:
        logger.error(f"Failed to stop processor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/start")
async def start_processor():
    """Admin endpoint to start the processor."""
    if not job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")
    
    try:
        if not job_queue.running:
            asyncio.create_task(job_queue.start_processing())
        return {"message": "Processor started"}
    except Exception as e:
        logger.error(f"Failed to start processor: {e}")
        raise HTTPException(status_code=500, detail=str(e))