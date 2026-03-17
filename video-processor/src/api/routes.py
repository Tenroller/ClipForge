"""
REST API endpoints for video processing
"""

import asyncio
from datetime import datetime, timezone
from typing import Annotated, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, Response

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


@router.get("/voices")
async def get_available_voices():
    """Get available TTS voices."""
    # List of available TTS voices
    voices = [
        "af_bella",
        "af_nicole", 
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_michael",
        "bf_emma",
        "bf_isabella",
        "bm_george", 
        "bm_lewis",
        "en_male_jomboy",
        "en_female_samc",
    ]
    
    logger.info(f"Returning {len(voices)} available TTS voices")
    return {"voices": voices}


@router.get("/voice-sample")
async def get_voice_sample(
    voice: Annotated[str, Query(..., description="Voice name to generate sample for")],
):
    """Generate a short TTS audio sample for a given voice and return WAV bytes."""
    import tempfile
    import os

    # Validate voice name (alphanumeric, underscores, hyphens only)
    if not voice or not all(c.isalnum() or c in ('_', '-') for c in voice):
        raise HTTPException(status_code=400, detail="Invalid voice name")

    try:
        from vendors.Compilation.tts_generator import TTSGenerator

        generator = TTSGenerator(api_key=os.environ.get("OPENROUTER_API_KEY", ""))
        sample_text = "Hello! This is a voice sample preview for ClipForge."

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            audio_path = generator.text_to_speech(
                text=sample_text,
                voice=voice,
                output_path=tmp_path,
            )
            if not audio_path or not os.path.isfile(audio_path):
                raise HTTPException(status_code=500, detail="TTS generation returned no audio")

            audio_bytes = open(audio_path, "rb").read()
            return Response(content=audio_bytes, media_type="audio/wav")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except ImportError:
        raise HTTPException(status_code=501, detail="TTS engine not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice sample generation failed for '{voice}': {e}")
        raise HTTPException(status_code=500, detail=f"Voice sample generation failed: {e}")


@router.post("/thumbnail")
async def generate_thumbnail(
    video_path: Annotated[str, Query(..., description="Path to the video file")],
    timestamp: Annotated[float, Query(description="Time in seconds to extract thumbnail from")] = 5.0,
):
    """Generate a thumbnail from a video file and return it as JPEG bytes."""
    import os
    from pathlib import Path

    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        from moviepy import VideoFileClip
        from PIL import Image
        import numpy as np
        import io

        with VideoFileClip(video_path) as clip:
            thumbnail_time = min(timestamp, clip.duration * 0.1) if clip.duration else timestamp
            frame = clip.get_frame(thumbnail_time)

        if frame.dtype != np.uint8:
            frame = (frame * 255).astype(np.uint8)

        image = Image.fromarray(frame)

        # Resize preserving aspect ratio (max 320px)
        original_width, original_height = image.size
        aspect_ratio = original_width / original_height
        max_dim = 320
        if aspect_ratio > 1:
            new_width = max_dim
            new_height = int(max_dim / aspect_ratio)
        else:
            new_height = max_dim
            new_width = int(max_dim * aspect_ratio)

        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=85, optimize=True)
        buf.seek(0)

        return Response(content=buf.getvalue(), media_type="image/jpeg")

    except ImportError:
        raise HTTPException(status_code=500, detail="moviepy or Pillow not available on this processor")
    except Exception as e:
        logger.error(f"Thumbnail generation failed for {video_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {e}")