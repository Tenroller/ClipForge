"""
Video generation endpoints.
"""

import uuid
import time
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...models.requests import MoneyPrinterRequest, BrainrotRequest, SuggestSubjectRequest
from ...logging_config import get_logger, log_job_event
from ...database import get_job_store
from ...job_queue_unified import get_job_queue
from ...utils.paths import get_backend_path

router = APIRouter()
logger = get_logger("video_generation")

# Get database and queue instances
job_store = get_job_store()
job_queue = get_job_queue()

VENDOR_ROOT = get_backend_path("vendors")


@router.post(
    "/moneyprinter/generate",
    summary="Generate AI Video",
    description="""
    Create a video using AI-powered script generation, stock footage, and text-to-speech.

    This endpoint starts a video generation job and returns immediately with a job ID.
    Use the job ID to track progress via WebSocket or polling.

    **Process Overview:**
    1. Generate script from subject using AI model
    2. Extract search terms for stock footage
    3. Download relevant stock videos
    4. Generate text-to-speech audio
    5. Create subtitles
    6. Compose final video with audio and subtitles

    **Required Environment Variables:**
    - `PEXELS_API_KEY`: For stock video search
    - `GOOGLE_API_KEY` or `GEMINI_API_KEY`: For AI script generation
    """
)
def moneyprinter_generate(req: MoneyPrinterRequest):
    """Generate video using MoneyPrinter workflow."""
    job_id = str(uuid.uuid4())

    # Log request parameters with enhanced details
    logger.debug(f"MoneyPrinter request parameters: useTikTokSubtitles={req.useTikTokSubtitles}, subtitleFont={req.subtitleFont}, voice={req.voice}, aiModel={req.aiModel}")

    log_job_event(logger, job_id, "moneyprinter", "created",
                subject=req.videoSubject[:100], voice=req.voice, ai_model=req.aiModel)
    
    # Submit job to queue
    try:
        from ...services.video_generation import run_moneyprinter_job
        job_queue.add_job(
            run_moneyprinter_job,
            job_id,
            req,
            job_id=job_id,          # Explicitly specify job_id
            workflow="moneyprinter"
        )
    except Exception as e:
        logger.error(f"Failed to submit MoneyPrinter job {job_id}: {e}")
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


@router.post("/brainrot/generate", summary="Generate Brainrot Compilation")
def brainrot_generate(req: BrainrotRequest):
    """Generate video using Brainrot workflow."""
    try:
        job_id = str(uuid.uuid4())

        # Use unified queue for job management
        from ...services.video_generation import run_brainrot_job
        logger.debug(f"Adding brainrot job with ID: {job_id}")
        actual_job_id = job_queue.add_job(
            run_brainrot_job,
            job_id,                # Pass job_id as first argument to the function
            req.model_dump(),      # Convert Pydantic model to dict for serialization
            job_id=job_id,         # Specify job_id for the job queue
            workflow="brainrot"
        )
        logger.debug(f"Job queue returned ID: {actual_job_id}")
        
        if actual_job_id != job_id:
            logger.warning(f"Job ID mismatch! Expected: {job_id}, Got: {actual_job_id}")
            # Use the actual job ID for database checks
            job_id = actual_job_id

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
        try:
            # Try to get available models, fallback to defaults
            models = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-pro"]
            return {"models": models}
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}


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
