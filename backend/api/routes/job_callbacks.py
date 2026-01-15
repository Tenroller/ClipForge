"""
Job callback endpoints for video processor notifications.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...logging_config import get_logger
from ...database import get_job_store
from ...utils.progress_tracker import get_progress_tracker
from ...services.video_service import get_video_service
from ...utils.paths import get_output_path

router = APIRouter()
logger = get_logger("job_callbacks")

# Get database instance
job_store = get_job_store()
video_service = get_video_service()


class JobCallbackPayload(BaseModel):
    """Payload for job status callbacks from video processor."""
    job_id: str
    status: str
    progress: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


def _auto_register_videos(job_id: str, workflow: Optional[str], result_data: Dict[str, Any]) -> None:
    """
    Automatically register videos when a job completes.

    This ensures videos appear in the gallery immediately without requiring manual sync.
    """
    if not workflow or not result_data:
        return

    registered_count = 0

    try:
        # Check if videos are already registered for this job
        existing_videos = video_service.list_videos(job_id=job_id, limit=1)
        if existing_videos:
            logger.debug(f"Videos already registered for job {job_id}, skipping auto-registration")
            return

        # Handle MoneyPrinter workflow
        if workflow == "moneyprinter" and "output" in result_data:
            video_path = result_data["output"]
            if video_path and Path(video_path).exists():
                video_service.register_video(
                    job_id=job_id,
                    file_path=video_path,
                    workflow=workflow,
                    video_type="ai_generated",
                    metadata={"auto_registered": True}
                )
                registered_count += 1
                logger.info(f"Auto-registered MoneyPrinter video for job {job_id}: {video_path}")

        # Handle Brainrot workflow
        elif workflow == "brainrot" and "generated_videos" in result_data:
            generated_videos = result_data.get("generated_videos", [])
            for video_data in generated_videos:
                if not video_data:
                    continue

                video_path = video_data.get("path")
                if video_path and Path(video_path).exists():
                    video_service.register_video(
                        job_id=job_id,
                        file_path=video_path,
                        workflow=workflow,
                        video_type="compilation",
                        compilation_type=video_data.get("compilation_type"),
                        compilation_num=video_data.get("compilation_num"),
                        metadata={"auto_registered": True}
                    )
                    registered_count += 1

            if registered_count > 0:
                logger.info(f"Auto-registered {registered_count} Brainrot videos for job {job_id}")

        # Handle PodcastClips workflow
        elif workflow == "podcastclips" and "generated_videos" in result_data:
            generated_videos = result_data.get("generated_videos", [])
            for video_data in generated_videos:
                if not video_data:
                    continue

                video_path = video_data.get("path") or video_data.get("output_path")
                if video_path:
                    # Resolve relative paths (from video-processor)
                    if not Path(video_path).is_absolute():
                        project_root = get_output_path().parent  # Get project root
                        absolute_path = project_root / "video-processor" / video_path
                    else:
                        absolute_path = Path(video_path)

                    if absolute_path.exists():
                        # Extract AI metadata from video_data
                        # Support both nested ai_metadata object and top-level fields
                        ai_metadata = video_data.get("ai_metadata", {})
                        
                        # Build comprehensive metadata by merging all sources
                        video_metadata = {
                            "auto_registered": True,
                            # Core fields with fallback chain
                            "title": video_data.get("title") or ai_metadata.get("title", ""),
                            "clip_index": video_data.get("clip_index") or ai_metadata.get("clip_index", 0),
                            "duration": video_data.get("duration", 0),
                            "start_time": video_data.get("start_time") or ai_metadata.get("start_time", 0),
                            "end_time": video_data.get("end_time") or ai_metadata.get("end_time", 0),
                            # AI scoring
                            "viral_score": video_data.get("viral_score") or ai_metadata.get("viral_score", 0),
                            "hook_strength": video_data.get("hook_strength") or ai_metadata.get("hook_strength", 0),
                            "confidence": video_data.get("confidence") or ai_metadata.get("confidence", 0),
                            # Content
                            "hook": video_data.get("hook") or ai_metadata.get("hook", ""),
                            "caption": video_data.get("caption") or ai_metadata.get("caption", ""),
                            "reason": video_data.get("reason") or ai_metadata.get("reason", ""),
                            "tags": video_data.get("tags") or ai_metadata.get("tags", []),
                            "thumbnail_text": video_data.get("thumbnail_text") or ai_metadata.get("thumbnail_text", ""),
                            # Technical
                            "face_coverage_pct": video_data.get("face_coverage_pct", 0),
                        }

                        video_service.register_video(
                            job_id=job_id,
                            file_path=str(absolute_path),
                            workflow=workflow,
                            video_type="podcast_clip",
                            compilation_type=video_data.get("compilation_type"),
                            compilation_num=video_data.get("compilation_num"),
                            metadata=video_metadata
                        )
                        registered_count += 1

                        # Log metadata inclusion
                        logger.debug(f"Registered video with metadata: title={video_metadata.get('title', 'N/A')}, "
                                   f"viral_score={video_metadata.get('viral_score', 0)}, "
                                   f"duration={video_metadata.get('duration', 0)}s")

            if registered_count > 0:
                logger.info(f"Auto-registered {registered_count} PodcastClips videos for job {job_id}")

    except Exception as e:
        logger.error(f"Error in auto-registration for job {job_id}: {e}")
        raise


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

        # Auto-register videos when job completes successfully
        if payload.status == "completed" and payload.result_data:
            try:
                _auto_register_videos(job_id, job.get("workflow"), payload.result_data)
            except Exception as e:
                logger.error(f"Failed to auto-register videos for job {job_id}: {e}")

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