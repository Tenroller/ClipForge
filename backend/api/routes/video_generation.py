"""
Video generation endpoints.
"""

import uuid
import time
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from fastapi.responses import FileResponse

from ...models.requests import MoneyPrinterRequest, BrainrotRequest, PodcastClipsRequest, SuggestSubjectRequest
from ...middleware.auth import get_current_user
from ...logging_config import get_logger, log_job_event
from ...database import get_job_store
from ...services.video_orchestrator import get_video_orchestrator
from ...utils.paths import get_backend_path, get_temp_path

router = APIRouter()
logger = get_logger("video_generation")

# Get database and orchestrator instances
job_store = get_job_store()
video_orchestrator = get_video_orchestrator()

VENDOR_ROOT = get_backend_path("vendors")


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
            tracker.add_log(f"Target: {req.targetClipCount} clips, Duration: {req.minDuration}s-{req.maxDuration}s", "info", "config")
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
            "message": f"Podcast clips generation started. Expecting {req.targetClipCount} clips."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate podcast clips: {e}")


@router.post("/AIvideos/suggest-subject")
def suggest_subject(req: SuggestSubjectRequest) -> Dict[str, str]:
    """Suggest a short content subject using Gemini."""
    try:
        from ...vendors.AIvideos.gpt import generate_response
        
        examples = req.examples or [
            "Good foods for cats",
            "How to calm your dog", 
            "How to fix a broken pipe",
        ]
        hint = (req.topicHint or "").strip()

        prompt_lines = [
            "Suggest one short, catchy subject for a short-form video.",
            "- 3 to 6 words.",
            "- No quotes, no emojis, minimal punctuation.",
            "- Return ONLY the subject text.",
            "",
            "Examples:",
        ]
        prompt_lines += [f"- {e}" for e in examples if e]
        if hint:
            prompt_lines.append(f"\nTopic area: {hint}")
        prompt = "\n".join(prompt_lines)

        try:
            raw = generate_response(prompt, req.aiModel or "gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Failed to generate subject suggestion: {e}")
            return {"subject": "Amazing facts about animals"}

        text = (raw or "").strip().splitlines()[0] if raw else ""
        # Light cleanup: drop surrounding quotes and trailing punctuation
        text = text.strip().strip('"\'').strip()
        if text.endswith(('.', '!', '?')):
            text = text[:-1]
        if not text:
            text = "Amazing facts about animals"

        return {"subject": text}
        
    except Exception as e:
        logger.error(f"Error in suggest_subject: {e}")
        return {"subject": "Amazing facts about animals"}


@router.get("/AIvideos/models", summary="List AI Models")
def list_models() -> Dict[str, list]:
    """List available Gemini models using API discovery."""
    try:
        from ...utils.gemini_client import get_available_gemini_models

        # Fetch models from Gemini API
        models = get_available_gemini_models()
        logger.info(f"Returning {len(models)} models from Gemini API")
        return {"models": models}
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        # Fallback to default models
        return {"models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro", "gemini-1.5-flash"]}


@router.get("/AIvideos/gpu-info")
def get_gpu_info() -> Dict[str, Any]:
    """Return information about locally available GPU acceleration."""
    # Try CUDA/torch detection (optional dependency in some setups)
    cuda_available = False
    gpu_name = None
    gpu_memory_gb = None
    try:
        import torch
        if torch.cuda.is_available():
            cuda_available = True
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except Exception:
        pass

    # Use MoneyPrinter's codec detection if available
    preferred_codec = None
    ffmpeg_params = None
    try:
        # Placeholder for GPU codec detection
        preferred_codec = "h264_nvenc" if cuda_available else "libx264"
        ffmpeg_params = ["-preset", "fast"] if cuda_available else ["-preset", "medium"]
    except Exception:
        pass

    return {
        "local": {
            "cudaAvailable": cuda_available,
            "gpuName": gpu_name,
            "memoryGb": gpu_memory_gb,
            "preferredCodec": preferred_codec,
            "ffmpegParams": ffmpeg_params,
        }
    }


@router.get("/voices")
def list_voices() -> Dict[str, list]:
    """Expose Kokoro voices used by the AI video workflow."""
    start_ts = time.time()
    try:
        from ...vendors.AIvideos.tiktokvoice import VOICES
        # VOICES might be a list or dict, handle both cases
        if isinstance(VOICES, dict):
            voices = list(VOICES.keys())
        else:
            voices = VOICES  # Assume it's already a list
    except Exception as e:
        logger.error(f"Failed to load voices: {e}")
        voices = ["af_bella", "en_male_jomboy", "en_female_samc"]
        
    duration = time.time() - start_ts
    max_secs = 5.0
    
    if duration > max_secs:
        logger.warning(f"Voice loading took {duration:.2f}s (>{max_secs}s)")
        
    return {"voices": voices}


@router.get("/voice-sample")
def voice_sample(voice: str, text: str | None = None):
    """Generate and return a short MP3 sample for a given voice."""
    try:
        from ...vendors.AIvideos.tiktokvoice import VOICES, tts
        
        if voice not in VOICES:
            raise HTTPException(status_code=400, detail=f"Voice '{voice}' not found")
        
        # Use a stable absolute temp path under vendors/temp
        temp_dir = (VENDOR_ROOT / "temp").resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        target = (temp_dir / f"voice_sample_{voice}.mp3").resolve()
        sample_text = text or "This is a short sample of this voice."

        # If no custom text requested and a sample already exists, reuse it
        if text is None and target.exists() and target.is_file() and target.stat().st_size > 0:
            return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")

        try:
            tts(sample_text, voice, str(target))
            if not target.exists() or target.stat().st_size == 0:
                raise RuntimeError("TTS generation failed - no output file")
        except Exception as e:
            logger.error(f"TTS generation failed for voice {voice}: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate voice sample")

        return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")
        
    except Exception as e:
        logger.error(f"Voice sample error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
