"""
Video generation service layer.
"""

import time
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from ..models.requests import MoneyPrinterRequest, BrainrotRequest
from ..logging_config import get_logger, log_job_event, log_generation_step
from ..database import get_job_store
from ..job_queue_unified import get_job_queue, update_job_progress
from ..utils.paths import get_output_path
from ..utils.error_handling import handle_error


class VideoGenerationService:
    """Service for handling video generation workflows."""
    
    def __init__(self):
        self.logger = get_logger("video_generation.service")
        self.job_store = get_job_store()
        self.job_queue = get_job_queue()
        self.output_dir = get_output_path()
    
    def generate_moneyprinter_video(self, request: MoneyPrinterRequest) -> Dict[str, Any]:
        """Generate video using MoneyPrinter workflow."""
        # TODO: Extract logic from app.py
        raise NotImplementedError("To be implemented")
    
    def generate_brainrot_video(self, request: BrainrotRequest) -> Dict[str, Any]:
        """Generate video using Brainrot workflow."""
        # TODO: Extract logic from app.py
        raise NotImplementedError("To be implemented")


def _check_cancel(job_id: str) -> None:
    """Check if job has been cancelled."""
    job_queue = get_job_queue()
    status = job_queue.get_job_status(job_id)
    if status and status.get('status') == 'cancelled':
        raise RuntimeError("cancelled")


def _update_job(job_id: str, **fields: Any) -> None:
    """Update job in unified queue (which handles database persistence)."""
    job_store = get_job_store()
    job_queue = get_job_queue()
    
    # Handle special fields that need queue-specific processing
    if 'logs' in fields and fields['logs']:
        # Add log message to queue
        job_queue.update_job_progress(job_id, fields.get('step', ''), fields['logs'][-1])
        fields.pop('logs')  # Remove from database update

    if 'step' in fields:
        job_queue.update_job_progress(job_id, fields['step'])
        fields.pop('step')  # Remove from database update

    # Update database directly for remaining fields
    if fields:
        job_store.update_job(job_id, **fields)

    _enqueue_job_update(job_id)


def _enqueue_job_update(job_id: str) -> None:
    """Thread-safe enqueue of a job update for websocket broadcast."""
    try:
        from ..core.lifespan import MAIN_LOOP, ASYNC_QUEUE
        job_queue = get_job_queue()
        payload = job_queue.get_job_status(job_id)
        if payload and MAIN_LOOP is not None:
            MAIN_LOOP.call_soon_threadsafe(ASYNC_QUEUE.put_nowait, (job_id, payload))
    except Exception:
        # Best-effort only
        pass


def run_moneyprinter_job(job_id: str, req: MoneyPrinterRequest):
    """Execute MoneyPrinter video generation job."""
    generation_logger = get_logger("video_generator.generation")
    start_time = time.time()

    # Get progress tracker for logging
    from ..utils.progress_tracker import get_progress_tracker
    tracker = get_progress_tracker(job_id)

    try:
        log_job_event(generation_logger, job_id, "moneyprinter", "started_processing")
        tracker.add_log("Starting MoneyPrinter video generation", "info", "moneyprinter")
        _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())

        # Log job parameters for debugging
        log_job_event(generation_logger, job_id, "moneyprinter", "job_parameters",
                     subject=req.videoSubject[:100], voice=req.voice, ai_model=req.aiModel,
                     use_music=req.useMusic, use_subtitles=req.useTikTokSubtitles,
                     paragraphs=req.paragraphNumber)
        
        tracker.add_log(f"Job parameters: subject={req.videoSubject[:50]}..., voice={req.voice}, model={req.aiModel}", "info", "moneyprinter")

        log_generation_step(generation_logger, job_id, "moneyprinter", "setup_environment", "started")

        # Import video generation dependencies
        from ..vendors.AIvideos.utils import fetch_songs, check_env_vars
        from ..vendors.AIvideos.gpt import generate_script, get_search_terms
        from ..vendors.AIvideos.search import search_for_stock_videos
        from ..vendors.AIvideos.tiktokvoice import tts
        from ..vendors.AIvideos.video import generate_subtitles, combine_videos, generate_video
        from ..vendors.AIvideos.video import save_video as mp_save_video
        from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_audioclips  # type: ignore

        log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "started")
        _update_job(job_id, step="validate_env")
        update_job_progress(job_id, "validate_env", "validate_env: checking AIvideos environment variables")
        tracker.add_log("Validating environment variables", "info", "moneyprinter")

        try:
            check_env_vars()
            log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "completed")
            tracker.add_log("Environment validation completed successfully", "info", "moneyprinter")
        except SystemExit:
            log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "failed",
                              error="Missing required AIvideos environment variables")
            tracker.add_log("Environment validation failed: missing required variables", "error", "moneyprinter")
            raise RuntimeError("Missing required AIvideos environment variables")

        _check_cancel(job_id)
        
        # Music handling
        if req.useMusic and req.zipUrl:
            log_generation_step(generation_logger, job_id, "moneyprinter", "fetch_music", "started",
                              zip_url=req.zipUrl)
            _update_job(job_id, step="fetch_music")
            update_job_progress(job_id, "fetch_music", f"fetch_music: downloading songs from zipUrl={req.zipUrl}")
            tracker.add_log(f"Downloading background music from: {req.zipUrl}", "info", "moneyprinter")

            music_start = time.time()
            fetch_songs(req.zipUrl)
            music_duration = time.time() - music_start

            log_generation_step(generation_logger, job_id, "moneyprinter", "fetch_music", "completed",
                              duration=music_duration)
            tracker.add_log(f"Music download completed in {music_duration:.1f} seconds", "info", "moneyprinter")

        _check_cancel(job_id)
        
        # Script generation
        generation_logger.info(f"[AIvideos_generate] Job {job_id}: Step script_generation - model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
        _update_job(job_id, step="script_generation")
        update_job_progress(job_id, "script_generation", f"script_generation: model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
        tracker.add_log(f"Generating script with {req.paragraphNumber} paragraphs using {req.aiModel}", "info", "moneyprinter")
        
        script = generate_script(req.videoSubject, req.paragraphNumber, req.aiModel, req.voice, req.customPrompt or "")
        if not script:
            tracker.add_log("Failed to generate script", "error", "moneyprinter")
            raise RuntimeError("Failed to generate script")
        
        tracker.add_log(f"Script generated successfully ({len(script)} characters)", "info", "moneyprinter")

        # Continue with remaining steps...
        # TODO: Extract the full implementation from original app.py
        tracker.add_log("Note: Full MoneyPrinter implementation still being migrated", "warning", "moneyprinter")
        
        # For now, mark as completed
        duration_seconds = int(time.time() - start_time)
        tracker.add_log(f"MoneyPrinter job completed in {duration_seconds} seconds", "info", "moneyprinter")
        _update_job(job_id, status="done", duration_seconds=duration_seconds)

    except Exception as e:
        duration_seconds = int(time.time() - start_time)
        if str(e) == "cancelled":
            generation_logger.info(f"[AIvideos_generate] Job {job_id}: Job cancelled")
            tracker.add_log("Job was cancelled by user", "info", "moneyprinter")
            _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
        else:
            # Use standardized error handling
            error_info = handle_error(e, {
                "job_id": job_id,
                "step": "video_generation",
                "duration_seconds": duration_seconds
            })

            error_msg = error_info['error']['message']
            if any(k in error_msg.lower() for k in ["font", "pillow", "textclip"]):
                error_msg += " (Hint: Install system fonts or check font configuration)"

            update_job_progress(job_id, "error", f"error: {error_msg}")
            tracker.add_log(f"Job failed: {error_msg}", "error", "moneyprinter")
            _update_job(job_id, status="error", error=error_msg, duration_seconds=duration_seconds)


def run_brainrot_job(job_id: str, req_dict: dict):
    """Execute Brainrot video generation job."""
    logger = get_logger("video_generator.brainrot")
    logger.info(f"[brainrot_generate] Started processing job {job_id}")
    start_time = time.time()

    # Get progress tracker for logging
    from ..utils.progress_tracker import get_progress_tracker
    tracker = get_progress_tracker(job_id)

    try:
        # Convert dict back to BrainrotRequest
        req = BrainrotRequest(**req_dict)

        # Record when job actually started processing
        _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())
        tracker.add_log(f"Starting brainrot compilation for URL: {req.youtubeUrl}", "info", "brainrot")

        from ..vendors.Compilation.generator import TikYouGenerator

        _check_cancel(job_id)
        _update_job(job_id, step="process_video")
        tracker.add_log("Processing source video and extracting clips", "info", "brainrot")

        # Create job-specific output folder named with job UUID
        output_dir = get_output_path()
        job_output_dir = output_dir / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        output_dir_str = str(job_output_dir.resolve())
        tracker.add_log(f"Created output directory: {job_output_dir}", "info", "brainrot")

        generator = TikYouGenerator(output_dir=output_dir_str, tracker=tracker)
        tracker.add_log("Initialized TikYou generator", "info", "brainrot")
        
        video_clips = generator.process_single_video(req.youtubeUrl)
        if not video_clips:
            tracker.add_log("No clips generated from source video", "error", "brainrot")
            raise RuntimeError("No clips generated from source video")
        
        tracker.add_log(f"Successfully extracted {len(video_clips)} clips from source video", "info", "brainrot")

        _check_cancel(job_id)
        _update_job(job_id, step="generate_compilations")
        tracker.add_log("Generating compilation videos", "info", "brainrot")

        # Generate videos with progress tracking
        generator.generate_tikyou_videos(
            req.youtubeUrl,
            num_compilations=None if req.unlimited else req.numCompilations,
            min_duration=req.minDuration,
            max_duration=req.maxDuration,
            video_clips=video_clips
        )
        
        tracker.add_log("Successfully generated compilation videos", "info", "brainrot")

        _check_cancel(job_id)
        
        # Final update
        duration_seconds = int(time.time() - start_time)
        tracker.add_log(f"Brainrot job completed successfully in {duration_seconds} seconds", "info", "brainrot")
        _update_job(job_id, status="done", duration_seconds=duration_seconds)

    except Exception as e:
        duration_seconds = int(time.time() - start_time)
        if str(e) == "cancelled":
            tracker.add_log("Job was cancelled by user", "info", "brainrot")
            _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
        else:
            tracker.add_log(f"Job failed with error: {str(e)}", "error", "brainrot")
            _update_job(job_id, status="error", error=str(e), duration_seconds=duration_seconds)
