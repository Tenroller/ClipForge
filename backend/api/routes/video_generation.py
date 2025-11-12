"""
Video generation endpoints.
"""

import uuid
import time
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from fastapi.responses import FileResponse

from ...models.requests import MoneyPrinterRequest, BrainrotRequest, PodcastClipsRequest
from ...middleware.auth import get_current_user
from ...logging_config import get_logger, log_job_event
from ...database import get_job_store
from ...services.video_orchestrator import get_video_orchestrator
from ...utils.paths import get_temp_path
from ...utils.youtube import get_video_metadata, YouTubeDownloadError

router = APIRouter()
logger = get_logger("video_generation")

# Get database and orchestrator instances
job_store = get_job_store()
video_orchestrator = get_video_orchestrator()


@router.get(
    "/youtube/metadata",
    summary="Get YouTube Video Metadata",
    description="""
    Extract metadata from a YouTube video without downloading it.

    This is useful for previewing video information before starting generation.
    Returns video title, channel, duration, thumbnail URL, and other details.
    """
)
async def get_youtube_metadata(url: str):
    """Get YouTube video metadata without downloading."""
    try:
        metadata = get_video_metadata(url)

        return {
            "video_id": metadata.video_id,
            "title": metadata.title,
            "channel": metadata.channel,
            "channel_url": metadata.channel_url,
            "duration": metadata.duration,
            "duration_formatted": metadata.duration_formatted,
            "thumbnail_url": metadata.thumbnail_url,
            "description": metadata.description[:500] if metadata.description else "",  # Limit description length
            "view_count": metadata.view_count,
            "upload_date": metadata.upload_date,
            "resolution": metadata.resolution,
        }
    except YouTubeDownloadError as e:
        logger.error(f"Failed to extract YouTube metadata: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error extracting YouTube metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract video metadata")


@router.post(
    "/moneyprinter/generate",
    summary="Generate AI Video",
    description="""
    Create a video using AI-powered script generation, stock footage, and text-to-speech.

    This endpoint starts a video generation job and returns immediately with a job ID.
    Use the job ID to track progress via REST API polling.

    **Process Overview:**
    1. Generate script from subject using AI model
    2. Extract search terms for stock footage
    3. Download relevant stock videos
    4. Generate text-to-speech audio
    5. Create subtitles
    6. Compose final video with audio and subtitles

    **Required Environment Variables:**
    - `PEXELS_API_KEY`: For stock video search
    - `GEMINI_API_KEY`: For AI script generation
    """
)
async def moneyprinter_generate(
    req: MoneyPrinterRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate video using MoneyPrinter workflow."""
    job_id = str(uuid.uuid4())

    # Log request parameters with enhanced details
    logger.debug(f"MoneyPrinter request parameters: useTikTokSubtitles={req.useTikTokSubtitles}, subtitleFont={req.subtitleFont}, voice={req.voice}, aiModel={req.aiModel}")

    log_job_event(logger, job_id, "moneyprinter", "created",
                subject=req.videoSubject[:100], voice=req.voice, ai_model=req.aiModel)
    
    # Create job in database
    try:
        job_store.create_job(
            job_id,
            "moneyprinter",
            req.model_dump(),
            user_id=None
        )
        
        # Create progress tracker and initial log
        from ...utils.progress_tracker import get_progress_tracker
        tracker = get_progress_tracker(job_id)
        tracker.add_log("MoneyPrinter job created and queued for processing", "info", "moneyprinter")
        tracker.add_log(f"Configuration: {req.aiModel} model, {req.voice} voice, {req.paragraphNumber} paragraphs", "info", "config")
        
    except Exception as e:
        logger.error(f"Failed to create job {job_id} in database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")
    
    # Submit job to orchestrator
    try:
        success = await video_orchestrator.submit_moneyprinter_job(job_id, req)
        
        if not success:
            # Update job status to error
            job_store.update_job(
                job_id,
                status="error",
                error_message="Failed to submit to video processor"
            )
            raise HTTPException(status_code=500, detail="Failed to submit job to video processor")
        
    except Exception as e:
        logger.error(f"Failed to submit MoneyPrinter job {job_id}: {e}")
        # Update job status to error
        job_store.update_job(
            job_id,
            status="error", 
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")
    
    # Ensure job is persisted to database before returning
    max_retries = 5
    for attempt in range(max_retries):
        try:
            job = job_store.get_job(job_id)
            if job:
                log_job_event(logger, job_id, "moneyprinter", "persisted_to_db", attempt=attempt)
                break
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
        except Exception as db_e:
            logger.warning(f"Database persistence check failed for job {job_id}, attempt {attempt + 1}: {db_e}",
                          extra={"job_id": job_id, "attempt": attempt, "db_error": str(db_e)})
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))

    return {"status": "queued", "jobId": job_id}


@router.post("/upload-video", summary="Upload Video File")
async def upload_video_file(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv')):
            raise HTTPException(status_code=400, detail="Invalid file type. Supported formats: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, 3GP, OGV")
        
        # Validate file size (max 10GB)
        max_size = 10 * 1024 * 1024 * 1024  # 10GB
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10GB")
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Create uploads directory in shared temp space
        uploads_dir = get_temp_path("uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        filename = f"{file_id}{file_extension}"
        file_path = uploads_dir / filename
        
        # Save file
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(content)
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")
        
        # Verify file was saved correctly
        if not file_path.exists() or file_path.stat().st_size != len(content):
            raise HTTPException(status_code=500, detail="File upload verification failed")
        
        logger.info(f"Video file uploaded successfully: {filename} ({len(content)} bytes)")
        
        return {
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "file_path": str(file_path),
            "size_bytes": len(content),
            "original_filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/brainrot/generate", summary="Generate Brainrot Compilation")
async def brainrot_generate(
    req: BrainrotRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate video using Brainrot workflow."""
    try:
        job_id = str(uuid.uuid4())

        # Create job in database
        try:
            job_store.create_job(
                job_id,
                "brainrot",
                req.model_dump(),
                user_id=None
            )
            
            # Create progress tracker and initial log
            from ...utils.progress_tracker import get_progress_tracker
            tracker = get_progress_tracker(job_id)
            tracker.add_log("Brainrot compilation job created and queued for processing", "info", "brainrot")
            if req.youtubeUrl:
                tracker.add_log(f"Source: YouTube URL - {req.youtubeUrl}", "info", "config")
            elif req.uploadedVideoPath:
                tracker.add_log(f"Source: Uploaded video - {req.uploadedVideoPath}", "info", "config")
            tracker.add_log(f"Compilations to generate: {req.numCompilations}, Duration: {req.minDuration}s-{req.maxDuration}s", "info", "config")
            
        except Exception as e:
            logger.error(f"Failed to create job {job_id} in database: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

        # Submit job to orchestrator
        try:
            success = await video_orchestrator.submit_brainrot_job(job_id, req)
            
            if not success:
                # Update job status to error
                job_store.update_job(
                    job_id,
                    status="error",
                    error_message="Failed to submit to video processor"
                )
                raise HTTPException(status_code=500, detail="Failed to submit job to video processor")
                
        except Exception as e:
            logger.error(f"Failed to submit Brainrot job {job_id}: {e}")
            # Update job status to error
            job_store.update_job(
                job_id,
                status="error",
                error_message=str(e)
            )
            raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")
        
        # Ensure job is persisted to database before returning
        max_retries = 5
        for attempt in range(max_retries):
            try:
                job = job_store.get_job(job_id)
                if job:
                    logger.info(f"[brainrot_generate] Job {job_id} successfully persisted to database")
                    break
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            except Exception as db_e:
                logger.warning(f"[brainrot_generate] Database check failed for job {job_id}, attempt {attempt + 1}: {db_e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))

        return {"status": "success", "jobId": job_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate brainrot video: {e}")


@router.post(
    "/podcastclips/generate",
    summary="Generate Podcast Clips",
    description="""
    Create viral short-form videos from podcast content.

    This endpoint analyzes a YouTube podcast video and generates 5-10 short-form (9:16 format)
    clips optimized for social media platforms like TikTok, Instagram Reels, and YouTube Shorts.

    **Process Overview:**
    1. Download podcast video from YouTube
    2. Transcribe with word-level timestamps (Whisper)
    3. AI-powered viral moment detection (Gemini)
    4. Face tracking for intelligent person-focused cropping
    5. Generate 9:16 vertical clips with professional subtitles

    **Key Features:**
    - Automatic detection of viral moments (AI-powered)
    - Face-focused cropping with MediaPipe
    - Professional closed captions
    - Multiple clips per job (5-10 clips)

    **Required Environment Variables:**
    - `GEMINI_API_KEY`: For AI viral moment detection
    """
)
async def podcastclips_generate(
    req: PodcastClipsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate viral clips from podcast video."""
    try:
        job_id = str(uuid.uuid4())

        log_job_event(logger, job_id, "podcastclips", "created",
                     url=req.youtubeUrl, ai_model=req.aiModel)

        # Create job in database
        try:
            job_store.create_job(
                job_id,
                "podcastclips",
                req.model_dump(),
                user_id=None
            )

            # Create progress tracker and initial log
            from ...utils.progress_tracker import get_progress_tracker
            tracker = get_progress_tracker(job_id)
            tracker.add_log("Podcast clips job created and queued for processing", "info", "podcastclips")
            tracker.add_log(f"Source: {req.youtubeUrl}", "info", "config")
            tracker.add_log(f"Target: {req.maxClipCount} clips, Duration: {req.minDuration}s-{req.maxDuration}s", "info", "config")
            tracker.add_log(f"AI Model: {req.aiModel}, Whisper: {req.whisperModel}", "info", "config")

        except Exception as e:
            logger.error(f"Failed to create job {job_id} in database: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

        # Submit job to orchestrator
        try:
            success = await video_orchestrator.submit_podcastclips_job(job_id, req)

            if not success:
                # Update job status to error
                job_store.update_job(
                    job_id,
                    status="error",
                    error_message="Failed to submit to video processor"
                )
                raise HTTPException(status_code=500, detail="Failed to submit job to video processor")

        except Exception as e:
            logger.error(f"Failed to submit PodcastClips job {job_id}: {e}")
            # Update job status to error
            job_store.update_job(
                job_id,
                status="error",
                error_message=str(e)
            )
            raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")

        # Ensure job is persisted to database before returning
        max_retries = 5
        for attempt in range(max_retries):
            try:
                job = job_store.get_job(job_id)
                if job:
                    logger.info(f"[podcastclips_generate] Job {job_id} successfully persisted to database")
                    break
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            except Exception as db_e:
                logger.warning(f"[podcastclips_generate] Database check failed for job {job_id}, attempt {attempt + 1}: {db_e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))

        return {
            "status": "success",
            "jobId": job_id,
            "message": f"Podcast clips generation started. Expecting up to {req.maxClipCount} clips."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate podcast clips: {e}")


@router.get("/AIvideos/models", summary="List AI Models")
async def list_models() -> Dict[str, list]:
    """
    List available AI models.

    This endpoint proxies to the video-processor service.
    """
    try:
        # Try to get models from video processor
        orchestrator = get_video_orchestrator()
        processor_status = await orchestrator.get_processor_cluster_status()

        # If we have a healthy processor, we could query it for models
        # For now, return a static list of known Gemini models
        return {
            "models": [
                "gemini-2.0-flash",
                "gemini-2.0-flash-exp",
                "gemini-2.0-pro",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        # Fallback to default models
        return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}


@router.get("/voices", summary="List TTS Voices")
async def list_voices() -> Dict[str, list]:
    """
    List available TTS voices.

    This endpoint proxies to the video-processor service.
    """
    try:
        # Return a static list of known Kokoro TTS voices
        # In the future, this could query the video-processor service
        return {
            "voices": [
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
        }
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        # Fallback to default voices
        return {"voices": ["af_bella", "en_male_jomboy", "en_female_samc"]}
