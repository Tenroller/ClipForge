"""
Video generation endpoints.
"""

import json
import shutil
import uuid
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, File, UploadFile, Depends, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ...models.requests import MoneyPrinterRequest, BrainrotRequest, PodcastClipsRequest, SuggestSubjectRequest
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

# Chunked upload constants
CHUNK_SIZE_LIMIT = 80 * 1024 * 1024  # 80MB per chunk
MAX_TOTAL_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv'}


class ChunkedUploadInitRequest(BaseModel):
    filename: str
    total_size: int


class ChunkedUploadFinalizeRequest(BaseModel):
    upload_id: str


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

        # Create uploads directory in shared temp space
        uploads_dir = get_temp_path("uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        filename = f"{file_id}{file_extension}"
        file_path = uploads_dir / filename

        # Stream file to disk in chunks to avoid loading entire file into memory
        max_size = 10 * 1024 * 1024 * 1024  # 10GB
        chunk_size = 1024 * 1024  # 1MB chunks
        total_written = 0

        try:
            with open(file_path, "wb") as buffer:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_size:
                        buffer.close()
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10GB")
                    buffer.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            file_path.unlink(missing_ok=True)
            logger.error(f"Failed to save uploaded file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")

        if total_written == 0:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Verify file was saved correctly
        if not file_path.exists() or file_path.stat().st_size != total_written:
            raise HTTPException(status_code=500, detail="File upload verification failed")

        logger.info(f"Video file uploaded successfully: {filename} ({total_written} bytes)")

        return {
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "file_path": str(file_path),
            "size_bytes": total_written,
            "original_filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-video/init", summary="Initialize Chunked Upload")
async def upload_video_init(req: ChunkedUploadInitRequest):
    """Initialize a chunked upload session for large files."""
    # Validate extension
    ext = Path(req.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Validate total size
    if req.total_size <= 0:
        raise HTTPException(status_code=400, detail="total_size must be positive")
    if req.total_size > MAX_TOTAL_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10GB")

    upload_id = str(uuid.uuid4())
    total_chunks = -(-req.total_size // CHUNK_SIZE_LIMIT)  # ceiling division

    chunk_dir = get_temp_path("uploads") / "chunks" / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "upload_id": upload_id,
        "filename": req.filename,
        "total_size": req.total_size,
        "total_chunks": total_chunks,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "received_chunks": [],
    }
    (chunk_dir / "_meta.json").write_text(json.dumps(meta))

    logger.info(f"Chunked upload initialized: {upload_id} ({req.filename}, {req.total_size} bytes, {total_chunks} chunks)")

    return {"upload_id": upload_id, "total_chunks": total_chunks}


@router.post("/upload-video/chunk", summary="Upload a Chunk")
async def upload_video_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
):
    """Upload a single chunk of a large file."""
    # Validate upload_id is a UUID to prevent path traversal
    try:
        uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload_id")

    chunk_dir = get_temp_path("uploads") / "chunks" / upload_id
    meta_path = chunk_dir / "_meta.json"

    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")

    meta = json.loads(meta_path.read_text())

    if chunk_index < 0 or chunk_index >= meta["total_chunks"]:
        raise HTTPException(
            status_code=400,
            detail=f"chunk_index must be between 0 and {meta['total_chunks'] - 1}",
        )

    # Stream chunk to disk
    part_path = chunk_dir / f"{chunk_index:06d}.part"
    buf_size = 1024 * 1024  # 1MB buffer
    written = 0
    try:
        with open(part_path, "wb") as f:
            while True:
                data = await chunk.read(buf_size)
                if not data:
                    break
                written += len(data)
                if written > CHUNK_SIZE_LIMIT:
                    f.close()
                    part_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=400, detail="Chunk exceeds 80MB limit")
                f.write(data)
    except HTTPException:
        raise
    except Exception as e:
        part_path.unlink(missing_ok=True)
        logger.error(f"Failed to write chunk {chunk_index} for upload {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to write chunk")

    # Update metadata (idempotent: overwrite duplicate index)
    received = set(meta["received_chunks"])
    received.add(chunk_index)
    meta["received_chunks"] = sorted(received)
    meta_path.write_text(json.dumps(meta))

    logger.debug(f"Chunk {chunk_index}/{meta['total_chunks']} received for upload {upload_id} ({written} bytes)")

    return {
        "received": chunk_index,
        "chunks_so_far": len(meta["received_chunks"]),
        "total_chunks": meta["total_chunks"],
    }


@router.post("/upload-video/finalize", summary="Finalize Chunked Upload")
async def upload_video_finalize(req: ChunkedUploadFinalizeRequest):
    """Concatenate all chunks and produce the final uploaded file."""
    # Validate upload_id is a UUID to prevent path traversal
    try:
        uuid.UUID(req.upload_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload_id")

    chunk_dir = get_temp_path("uploads") / "chunks" / req.upload_id
    meta_path = chunk_dir / "_meta.json"

    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")

    meta = json.loads(meta_path.read_text())

    # Discover which .part files actually exist on disk (avoids _meta.json race condition)
    expected = set(range(meta["total_chunks"]))
    received = {
        int(p.stem)
        for p in chunk_dir.glob("*.part")
        if p.stem.isdigit()
    }
    missing = expected - received
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing chunks: {sorted(missing)}",
        )

    # Build final file
    uploads_dir = get_temp_path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    ext = Path(meta["filename"]).suffix.lower()
    filename = f"{file_id}{ext}"
    final_path = uploads_dir / filename

    total_written = 0
    buf_size = 1024 * 1024  # 1MB buffer
    try:
        with open(final_path, "wb") as out:
            for idx in range(meta["total_chunks"]):
                part_path = chunk_dir / f"{idx:06d}.part"
                with open(part_path, "rb") as part:
                    while True:
                        data = part.read(buf_size)
                        if not data:
                            break
                        out.write(data)
                        total_written += len(data)
    except Exception as e:
        final_path.unlink(missing_ok=True)
        logger.error(f"Failed to assemble chunks for upload {req.upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to assemble file from chunks")

    # Validate assembled size
    if total_written != meta["total_size"]:
        final_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Size mismatch: expected {meta['total_size']} bytes, got {total_written}",
        )

    # Clean up chunk directory
    shutil.rmtree(chunk_dir, ignore_errors=True)

    logger.info(f"Chunked upload finalized: {filename} ({total_written} bytes)")

    return {
        "success": True,
        "file_id": file_id,
        "filename": filename,
        "file_path": str(final_path),
        "size_bytes": total_written,
        "original_filename": meta["filename"],
    }


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
            tracker.add_log(f"Duration: {req.minDuration}s-{req.maxDuration}s (AI decides clip count)", "info", "config")
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
            "message": "Podcast clips generation started. AI will determine optimal clip count."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate podcast clips: {e}")


@router.get("/voices", summary="List TTS Voices")
async def list_voices() -> Dict[str, list]:
    """
    List available TTS voices.

    This endpoint queries the video-processor service for available voices.
    Falls back to a static list if the processor is unavailable.
    """
    # Default fallback voices
    fallback_voices = [
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

    try:
        # Try to get voices from video processor
        from ...services.video_orchestrator import get_video_orchestrator
        orchestrator = get_video_orchestrator()

        # Query processor for available voices
        voices = await orchestrator.processor_manager.get_available_voices()

        if voices and len(voices) > 0:
            logger.info(f"Retrieved {len(voices)} voices from video-processor")
            return {"voices": voices}
        else:
            logger.warning("No voices returned from video-processor, using fallback list")
            return {"voices": fallback_voices}

    except Exception as e:
        logger.error(f"Failed to list voices from video-processor: {e}")
        # Fallback to default voices
        return {"voices": fallback_voices}


@router.post("/AIvideos/suggest-subject", summary="Suggest a Video Subject")
async def suggest_subject(
    req: SuggestSubjectRequest,
    current_user: dict = Depends(get_current_user)
):
    """Use AI to suggest a creative video subject."""
    try:
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

        # Map short model names to OpenRouter model IDs
        model_map = {
            "gemini-2.0-flash": "openrouter/free",
            "gpt-4o-mini": "openai/gpt-4o-mini",
            "gpt-4o": "openai/gpt-4o",
            "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
        }
        model = model_map.get(req.aiModel, req.aiModel) if req.aiModel else "openrouter/free"

        prompt = (
            "Generate ONE creative, trending short-form video topic idea. "
            "It should be engaging, suitable for a 30-60 second vertical video, and appeal to a wide audience. "
            "Return ONLY the topic as a single short sentence (max 10 words). No explanation, no quotes."
        )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 1.0,
                },
            )
            response.raise_for_status()
            data = response.json()

        subject = data["choices"][0]["message"]["content"].strip().strip('"\'')
        return {"subject": subject}

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter API error: {e.response.status_code}")
        raise HTTPException(status_code=502, detail="AI service returned an error")
    except Exception as e:
        logger.error(f"Failed to suggest subject: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate subject suggestion")


@router.get("/voice-sample", summary="Preview TTS Voice Sample")
async def get_voice_sample(
    voice: str = Query(..., description="Voice name to preview"),
):
    """Proxy a voice sample request to the video-processor TTS engine."""
    try:
        import httpx

        processor_url = os.environ.get("VIDEO_PROCESSOR_URLS", "http://localhost:8090").split(",")[0].rstrip("/")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{processor_url}/api/v1/voice-sample",
                params={"voice": voice},
            )
            resp.raise_for_status()

        return Response(
            content=resp.content,
            media_type=resp.headers.get("content-type", "audio/wav"),
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"Processor voice-sample error: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="Voice sample generation failed")
    except Exception as e:
        logger.error(f"Failed to get voice sample for '{voice}': {e}")
        raise HTTPException(status_code=500, detail="Failed to generate voice sample")
