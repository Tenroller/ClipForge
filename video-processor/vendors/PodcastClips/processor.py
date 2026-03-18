"""
Podcast Clips Processor

Generates viral short-form videos from podcast content:
1. Downloads YouTube podcast video
2. Transcribes with word-level timestamps (Whisper)
3. Uses AI to detect viral moments
4. Tracks speaker faces for intelligent cropping
5. Generates 5-10 clips in 9:16 format with subtitles
"""

import os
import sys
import json
import cv2
import base64
from loguru import logger
from pathlib import Path
from typing import Dict, Any, List, Optional
import tempfile
import gc  # For explicit garbage collection after major operations

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Use video-processor's utils instead of backend modules
from utils.youtube import download_video, extract_video_id
from utils.artifacts import persist_artifact, load_artifact

# Create wrapper for job store that uses the job queue
class JobQueueWrapper:
    """Wrapper for job queue to act as job store for progress updates."""
    def __init__(self, job_queue=None, loop=None):
        self.job_queue = job_queue
        self.loop = loop

    def update_job_progress(self, job_id, progress, status, step=None, message=None):
        """Update job progress through the job queue."""
        if not self.job_queue:
            # No job queue available, skip progress updates
            logger.debug(f"No job queue available for progress update: {step} - {progress}%")
            return

        try:
            import asyncio
            # Import JobStatus from src.models
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from src.models.job import JobStatus

            # Map status string to JobStatus enum
            status_map = {
                "processing": JobStatus.RUNNING,
                "completed": JobStatus.COMPLETED,
                "error": JobStatus.FAILED,
                "queued": JobStatus.QUEUED
            }
            job_status = status_map.get(status, JobStatus.RUNNING)

            # Format progress as string (e.g., "50%")
            progress_str = f"{progress}%" if progress is not None else None

            # Use run_coroutine_threadsafe to schedule the async call in the main event loop
            if self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.job_queue.update_job_status(
                        job_id=job_id,
                        status=job_status,
                        progress=progress_str,
                        current_step=step,
                        error_message=message if status == "error" else None
                    ),
                    self.loop
                )
                # Wait for the result (with timeout to avoid blocking)
                try:
                    future.result(timeout=5)
                    logger.debug(f"Progress update sent: {step} - {progress}%")
                except Exception as e:
                    logger.warning(f"Progress update timeout or failed: {e}")
            else:
                logger.warning(f"Event loop not available for progress update: {step}")

        except Exception as e:
            logger.error(f"Failed to update job progress via queue: {e}")

def get_job_store(job_queue=None, loop=None):
    """Return job store wrapper for video-processor context."""
    return JobQueueWrapper(job_queue, loop)

from .face_tracker import FaceTracker, FaceBox
from .clip_generator import ClipGenerator, ViralMoment
from .content_detector import ContentModeDetector
from .thumbnail_generator import ThumbnailGenerator
from .audio_enhancer import AudioEnhancer
from .clip_scorer import ClipScorer
from .hook_optimizer import HookOptimizer
from .speaker_diarization import SpeakerDiarizer, SpeakerSegment, is_speaker_diarization_available
from vendors.AIvideos.stable_ts_enhanced_subtitles import extract_word_timings_with_stable_ts
from vendors.AIvideos.gpt import generate_structured_response, ViralMomentsResponse

# Logger is now imported from loguru
logger = logger.bind(name="PodcastClips.processor")


class PodcastClipsProcessor:
    """
    Main processor for podcast clips workflow.

    Orchestrates the entire pipeline from YouTube download to final clip generation.
    """

    def __init__(
        self,
        job_id: str,
        output_dir: str,
        temp_dir: Optional[str] = None,
        job_queue=None,
        loop=None
    ):
        """
        Initialize processor.

        Args:
            job_id: Unique job identifier
            output_dir: Directory for final outputs
            temp_dir: Temporary directory for intermediate files
            job_queue: Job queue for progress updates (optional)
            loop: Event loop for async operations (optional)
        """
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / f"podcastclips_{job_id}"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Job store for progress tracking
        self.job_store = get_job_store(job_queue, loop)

        # Component instances (initialized during processing)
        self.face_tracker: Optional[FaceTracker] = None
        self.text_color: Optional[str] = None
        self.highlight_color: Optional[str] = None
        self.clip_generator: Optional[ClipGenerator] = None

        logger.info(f"Initialized PodcastClipsProcessor for job {job_id}")

    def update_progress(self, step: str, progress: int, message: str = ""):
        """Update job progress in database."""
        try:
            self.job_store.update_job_progress(
                self.job_id,
                progress=progress,
                status="processing",
                step=step,
                message=message
            )
            logger.info(f"Progress update: {step} - {progress}% - {message}")
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")

    def process(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method.

        Args:
            parameters: Request parameters from PodcastClipsRequest

        Returns:
            Dictionary with processing results and metadata
        """
        try:
            logger.info(f"Starting podcast clips processing for job {self.job_id}")
            self.update_progress("initialization", 0, "Starting workflow")

            # Extract parameters
            youtube_url = parameters.get('youtubeUrl')
            uploaded_video_path = parameters.get('uploadedVideoPath')
            if not youtube_url and not uploaded_video_path:
                raise ValueError("Either YouTube URL or uploaded video file is required")
            
            # Hardcoded AI configuration (simplified - always use best settings)
            ai_model = 'openrouter/free'  # Always use latest flash model
            whisper_model = 'turbo'  # Always use turbo for fast transcription
            # max_clip_count removed - AI decides optimal clip count based on content quality
            
            min_duration = parameters.get('minDuration', 45)  # Minimum clip duration (45s default for viral shorts)
            max_duration = parameters.get('maxDuration', 90)  # Maximum clip duration (90s default)
            use_gpu = parameters.get('useGPU', False)
            subtitle_font_size = parameters.get('subtitleFontSize', 50)
            subtitle_color = parameters.get('subtitleColor', '#FFFFFF')
            subtitle_stroke_color = parameters.get('subtitleStrokeColor', '#000000')
            subtitle_stroke_width = parameters.get('subtitleStrokeWidth', 3)
            subtitle_vertical_offset = parameters.get('subtitleVerticalOffset', 400)
            subtitle_highlight_color = parameters.get('subtitleHighlightColor', '#FFEB3B')
            subtitle_max_words_visible = parameters.get('subtitleMaxWordsVisible', 5)
            subtitle_style = parameters.get('subtitleStyle', 'yellow_highlight')
            subtitle_display_mode = parameters.get('subtitleDisplayMode', 'word')
            subtitle_position = parameters.get('subtitlePosition', 'bottom')
            viral_keywords = parameters.get('viralFocusKeywords', [])

            # Mixed-mode configuration (always enabled for best quality)
            enable_mixed_mode = True  # Always enabled
            face_loss_threshold = parameters.get('faceLossThreshold', 1.0)
            face_return_threshold = parameters.get('faceReturnThreshold', 0.5)
            min_segment_duration = parameters.get('minSegmentDuration', 0.5)
            use_ocr = True  # Always enabled
            transition_duration = parameters.get('transitionDuration', 0.5)

            # AI-powered thumbnail configuration
            thumbnail_use_ai = parameters.get('thumbnailUseAI', True)
            thumbnail_red_box_color = parameters.get('thumbnailRedBoxColor', '#DC2626')
            thumbnail_text_color = parameters.get('thumbnailTextColor', '#FFFF64')
            thumbnail_blur_intensity = parameters.get('thumbnailBlurIntensity', 0.3)
            thumbnail_box_position = parameters.get('thumbnailBoxPosition', 'bottom')
            thumbnail_box_opacity = parameters.get('thumbnailBoxOpacity', 0.95)

            # Store ai_model for thumbnail generation
            self.ai_model = ai_model

            # Store thumbnail config as instance variable for post-processing
            self.thumbnail_config = {
                'use_ai': thumbnail_use_ai,
                'box_color': self._hex_to_rgb(thumbnail_red_box_color),
                'text_color': self._hex_to_rgb(thumbnail_text_color),
                'blur_intensity': thumbnail_blur_intensity,
                'position': thumbnail_box_position,
                'opacity': thumbnail_box_opacity
            }

            # Debug mode configuration
            debug_mode = parameters.get('debugMode', False)
            self.debug_mode = debug_mode  # Store as instance variable
            if debug_mode:
                logger.info("🐛 Debug mode enabled - will save extra artifacts and launch debug UI")

            # Face tracking smoothing configuration
            smoothing_strength = parameters.get('smoothingStrength', 11)  # 5=light, 11=medium, 21=strong

            # Speaker detection configuration
            enable_speaker_detection = parameters.get('enableSpeakerDetection', True)
            min_face_size_ratio = parameters.get('minFaceSizeRatio', 0.02)  # Filter out audience (2% of frame)
            max_tracked_faces = parameters.get('maxTrackedFaces', 4)  # Track up to 4 people

            # Speaker diarization configuration (always enabled for best speaker tracking)
            enable_speaker_diarization = True  # Always enabled
            min_speakers = parameters.get('minSpeakers', None)  # None = auto-detect
            max_speakers = parameters.get('maxSpeakers', None)  # None = auto-detect

            # Phase 2: Advanced speaker features
            target_speaker = parameters.get('targetSpeaker', None)  # Focus on specific speaker (e.g., "SPEAKER_00")
            min_speaker_percentage = parameters.get('minSpeakerPercentage', 0.0)  # Min % target speaker must speak
            require_exchange = parameters.get('requireExchange', False)  # Require multiple speakers in moment
            prioritize_guest = parameters.get('prioritizeGuest', False)  # Prioritize secondary speaker (guest) over main (host)

            # Split-screen configuration
            enable_split_screen = parameters.get('enableSplitScreen', True)  # Enable split-screen mode
            separation_threshold = parameters.get('separationThreshold', 0.40)  # 40% of frame width
            split_orientation = parameters.get('splitOrientation', 'vertical')  # 'vertical' or 'horizontal'

            # Launch debug UI if debug mode enabled
            if debug_mode:
                self._launch_debug_ui_thread()

            # Step 1: Download video or use uploaded file
            if uploaded_video_path:
                import os
                if not os.path.exists(uploaded_video_path):
                    raise RuntimeError(f"Uploaded video file not found: {uploaded_video_path}")
                logger.info(f"Using uploaded video file: {uploaded_video_path}")
                self.update_progress("download", 15, "Using uploaded video file")
                video_path = uploaded_video_path
            else:
                video_path = self._download_video(youtube_url)

            # Get video dimensions for font size recommendations
            import moviepy
            temp_clip = moviepy.VideoFileClip(video_path)
            video_height = temp_clip.h
            video_width = temp_clip.w
            temp_clip.close()
            logger.info(f"Video dimensions: {video_width}x{video_height}")

            # Step 2: Transcribe
            word_timings = self._transcribe_video(video_path, whisper_model, use_gpu)

            # Step 2.5: Speaker diarization (who speaks when)
            speaker_segments = None
            if enable_speaker_diarization and is_speaker_diarization_available():
                speaker_segments = self._diarize_speakers(
                    video_path, word_timings, use_gpu, min_speakers, max_speakers
                )
                # Store for later use
                self.speaker_segments = speaker_segments
            else:
                self.speaker_segments = None

            # Step 3: Detect viral moments (with speaker context if available)
            viral_moments = self._detect_viral_moments(
                word_timings, ai_model,
                min_duration, max_duration, viral_keywords,
                speaker_segments=speaker_segments
            )

            # Step 3.5: Apply Phase 2 speaker filtering if requested
            if speaker_segments and (target_speaker or min_speaker_percentage > 0 or require_exchange or prioritize_guest):
                logger.info("Applying Phase 2 speaker filtering")

                # If prioritizing guest, identify main speaker and target the secondary one
                if prioritize_guest and speaker_segments:
                    from .speaker_diarization import SpeakerDiarizer
                    diarizer = SpeakerDiarizer(use_gpu=False)
                    speaker_stats = diarizer.get_speaker_statistics(speaker_segments)

                    # Find secondary speaker (not the main one)
                    sorted_speakers = sorted(speaker_stats.items(), key=lambda x: x[1]['percentage'], reverse=True)
                    if len(sorted_speakers) >= 2:
                        target_speaker = sorted_speakers[1][0]  # Second most speaking time (guest)
                        min_speaker_percentage = max(min_speaker_percentage, 30.0)  # Guest should speak at least 30%
                        logger.info(f"Prioritizing guest speaker: {target_speaker}")

                # Apply filtering
                viral_moments = self._filter_moments_by_speaker(
                    viral_moments,
                    speaker_segments,
                    target_speaker=target_speaker,
                    min_speaker_percentage=min_speaker_percentage,
                    require_exchange=require_exchange
                )

            # Step 4: Optimize hooks for better engagement (MOVED BEFORE SCORING)
            # This ensures we score the final, optimized clip timings, not AI's rough guesses
            viral_moments = self._optimize_hooks(viral_moments, word_timings)

            # Step 5: Score and rank viral moments (NOW USES OPTIMIZED TIMINGS + SPEAKER DYNAMICS)
            viral_moments = self._score_and_rank_moments(
                viral_moments, word_timings,
                speaker_segments=speaker_segments
            )

            # Re-save viral moments with optimized timings and scores for debug UI
            persist_artifact(
                self.job_id,
                "ai_analysis",
                "viral_moments",
                payload={
                    "moments": [
                        {
                            "title": m.title,
                            "start_time": m.start_time,
                            "end_time": m.end_time,
                            "optimized_start": m.optimized_start,
                            "optimized_end": m.optimized_end,
                            "reason": m.reason,
                            "hook": m.hook,
                            "clip_index": m.clip_index,
                            "thumbnail_text": m.thumbnail_text,
                            "viral_score": m.viral_score,
                            "confidence": m.confidence,
                            "caption": m.caption,
                            "tags": m.tags,
                            "recommended_crop": m.recommended_crop,
                            "cut_padding_before": m.cut_padding_before,
                            "cut_padding_after": m.cut_padding_after,
                            "subtitles": m.subtitles,
                            "notes": m.notes,
                            "engagement_factors": getattr(m, 'engagement_factors', {})
                        }
                        for m in viral_moments
                    ],
                    "moment_count": len(viral_moments),
                    "optimized": True,
                    "scored": True
                }
            )
            logger.info("Updated viral moments artifact with optimized timings and scores")

            # Step 6: Analyze faces (REMOVED - now done per-clip for better performance)
            # Face and speaker detection moved into _generate_clips() to only process
            # the specific clip segments instead of the entire video (8x faster)

            # Font size recommendation based on video height
            # Recommend font size to be 3.5-5% of video height for optimal readability
            recommended_size = int(video_height * 0.04)  # 4% of height
            if subtitle_font_size < recommended_size * 0.7:
                logger.warning(
                    f"Font size {subtitle_font_size}px may be too small for {video_height}px height video. "
                    f"Recommended: {recommended_size}px (current is {int((subtitle_font_size / recommended_size) * 100)}% of recommended)"
                )
            elif subtitle_font_size > recommended_size * 1.5:
                logger.info(
                    f"Font size {subtitle_font_size}px is large for {video_height}px height video. "
                    f"Recommended: {recommended_size}px (current is {int((subtitle_font_size / recommended_size) * 100)}% of recommended)"
                )
            else:
                logger.info(f"Font size {subtitle_font_size}px is optimal for {video_height}px height video")

            # Step 7: Store subtitle colors for clip generation
            self.text_color = subtitle_color
            self.highlight_color = subtitle_highlight_color

            # Step 8: Generate clips (parallel) with optimized face detection
            generated_clips = self._generate_clips(
                video_path, viral_moments, word_timings,
                enable_mixed_mode, face_loss_threshold, face_return_threshold,
                min_segment_duration, use_ocr, transition_duration,
                smoothing_strength, use_gpu,
                enable_speaker_detection, min_face_size_ratio, max_tracked_faces,
                subtitle_style, subtitle_display_mode, subtitle_position
            )

            # Step 9: Post-processing (audio enhancement & thumbnails)
            generated_clips = self._post_process_clips(generated_clips, viral_moments)

            # Step 10: Finalize
            result = self._finalize(generated_clips, viral_moments)

            self.update_progress("completed", 100, "All clips generated successfully")

            return result

        except Exception as e:
            logger.error(f"Podcast clips processing failed: {e}", exc_info=True)
            self.update_progress("error", -1, f"Error: {str(e)}")
            raise

        finally:
            self._cleanup()

    def _download_video(self, youtube_url: str) -> str:
        """Download video from YouTube."""
        self.update_progress("download", 5, "Downloading video from YouTube")

        try:
            video_id = extract_video_id(youtube_url)
            logger.info(f"Downloading video: {video_id}")

            result = download_video(youtube_url, str(self.temp_dir))

            logger.info(f"Downloaded: {result.title} ({result.duration}s, {result.resolution})")

            # Persist video metadata
            persist_artifact(
                self.job_id,
                "download",
                "video_metadata",
                payload={
                    "video_id": video_id,
                    "title": result.title,
                    "duration": result.duration,
                    "resolution": result.resolution,
                    "video_path": result.video_path
                }
            )

            self.update_progress("download", 15, f"Downloaded: {result.title}")

            return result.video_path

        except Exception as e:
            logger.error(f"Video download failed: {e}")
            raise RuntimeError(f"Failed to download video: {e}")

    def _transcribe_video(self, video_path: str, model_size: str, use_gpu: bool) -> List[Dict[str, Any]]:
        """Transcribe video with Whisper."""
        self.update_progress("transcription", 20, "Transcribing audio with Whisper")

        try:
            # Check if transcript already exists (resume support)
            existing = load_artifact(self.job_id, "transcription", "transcript")
            if existing:
                logger.info("Found existing transcript, using cached version")
                return existing.get('word_timings', [])

            logger.info(f"Starting transcription with Whisper model: {model_size}")

            # Extract audio path (Whisper can handle video files directly)
            word_timings = extract_word_timings_with_stable_ts(
                audio_path=video_path,
                model_size=model_size,
                use_gpu=use_gpu,
                vad_threshold=0.35,
            )

            logger.info(f"Transcription complete: {len(word_timings)} words")

            # Build full transcript text
            transcript_text = ' '.join([w.get('word', '') for w in word_timings])

            # Persist transcript
            persist_artifact(
                self.job_id,
                "transcription",
                "transcript",
                payload={
                    "word_timings": word_timings,
                    "transcript_text": transcript_text,
                    "word_count": len(word_timings),
                    "model": model_size
                }
            )

            self.update_progress("transcription", 35, f"Transcribed {len(word_timings)} words")

            return word_timings

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe video: {e}")

    def _annotate_words_with_speakers(
        self,
        word_timings: List[Dict[str, Any]],
        speaker_segments: List[SpeakerSegment]
    ):
        """
        Annotate word timings with speaker labels based on speaker segments.
        Updates word_timings in-place and re-saves the transcription artifact.
        """
        try:
            logger.info("Annotating word timings with speaker labels")

            # Create a sorted list of speaker segments for efficient lookup
            sorted_segments = sorted(speaker_segments, key=lambda s: s.start_time)

            # Annotate each word with its speaker
            annotated_count = 0
            for word in word_timings:
                word_time = word.get('start_time', 0)

                # Find the speaker segment that contains this word
                speaker_label = None
                for segment in sorted_segments:
                    if segment.start_time <= word_time <= segment.end_time:
                        speaker_label = segment.speaker
                        break

                # Update word with speaker label
                word['speaker'] = speaker_label if speaker_label else 'UNKNOWN'
                if speaker_label:
                    annotated_count += 1

            logger.info(f"Annotated {annotated_count}/{len(word_timings)} words with speaker labels")

            # Re-save the transcription artifact with speaker annotations
            transcript_text = ' '.join([w.get('word', '') for w in word_timings])
            persist_artifact(
                self.job_id,
                "transcription",
                "transcript",
                payload={
                    "word_timings": word_timings,
                    "transcript_text": transcript_text,
                    "word_count": len(word_timings),
                    "has_speaker_labels": True,
                    "annotated_words": annotated_count
                }
            )

            logger.info("Updated transcription artifact with speaker annotations")

        except Exception as e:
            logger.error(f"Failed to annotate words with speakers: {e}", exc_info=True)

    def _diarize_speakers(
        self,
        video_path: str,
        word_timings: List[Dict[str, Any]],
        use_gpu: bool,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> Optional[List[SpeakerSegment]]:
        """
        Perform speaker diarization to identify who speaks when.

        Args:
            video_path: Path to video file
            word_timings: Word timing data from transcription
            use_gpu: Whether to use GPU acceleration
            min_speakers: Minimum number of speakers (None = auto-detect)
            max_speakers: Maximum number of speakers (None = auto-detect)

        Returns:
            List of SpeakerSegment objects or None if diarization fails
        """
        self.update_progress("speaker_diarization", 37, "Analyzing speakers")

        try:
            # Check if diarization already exists (resume support)
            existing = load_artifact(self.job_id, "speaker_diarization", "segments")
            if existing:
                logger.info("Found existing speaker diarization data")
                segments_data = existing.get('segments', [])
                speaker_segments = [
                    SpeakerSegment(
                        start_time=s['start_time'],
                        end_time=s['end_time'],
                        speaker=s['speaker']
                    )
                    for s in segments_data
                ]

                # Check if word timings need speaker annotation
                if word_timings and not word_timings[0].get('speaker'):
                    logger.info("Annotating existing transcription with speaker labels")
                    self._annotate_words_with_speakers(word_timings, speaker_segments)

                return speaker_segments

            logger.info("Starting speaker diarization")

            # Initialize diarizer
            diarizer = SpeakerDiarizer(
                use_gpu=use_gpu,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            # Run diarization
            speaker_segments = diarizer.diarize(
                audio_path=video_path,  # pyannote can handle video files
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            if not speaker_segments:
                logger.warning("No speaker segments detected")
                return None

            # Persist speaker segments
            persist_artifact(
                self.job_id,
                "speaker_diarization",
                "segments",
                payload={
                    "segments": [
                        {
                            "start_time": s.start_time,
                            "end_time": s.end_time,
                            "speaker": s.speaker
                        }
                        for s in speaker_segments
                    ],
                    "speaker_count": len(set(s.speaker for s in speaker_segments)),
                    "segment_count": len(speaker_segments)
                }
            )

            # Annotate word timings with speaker labels
            self._annotate_words_with_speakers(word_timings, speaker_segments)

            self.update_progress("speaker_diarization", 39, f"Identified {len(set(s.speaker for s in speaker_segments))} speakers")

            return speaker_segments

        except ImportError as e:
            logger.warning(f"Speaker diarization not available: {e}")
            logger.warning("Install pyannote-audio: pip install pyannote-audio")
            return None
        except Exception as e:
            logger.warning(f"Speaker diarization failed (non-critical): {e}")
            logger.info("Continuing without speaker diarization")
            return None

    def _detect_viral_moments(
        self,
        word_timings: List[Dict[str, Any]],
        ai_model: str,
        min_duration: int,
        max_duration: int,
        keywords: List[str],
        speaker_segments: Optional[List[SpeakerSegment]] = None
    ) -> List[ViralMoment]:
        """Use Gemini AI to detect viral moments with optional speaker context."""
        self.update_progress("ai_analysis", 40, "Analyzing content for viral moments")

        try:
            # Check if analysis already exists (resume support)
            existing = load_artifact(self.job_id, "ai_analysis", "viral_moments")
            if existing:
                logger.info("Found existing viral moments analysis")
                moments_data = existing.get('moments', [])
                return [ViralMoment(**m) for m in moments_data]

            # Merge speaker labels with word timings if available
            if speaker_segments:
                logger.info("Merging speaker labels with transcript")
                diarizer = SpeakerDiarizer(use_gpu=False)  # Just for annotation
                word_timings = diarizer.annotate_word_timings(word_timings, speaker_segments)
                logger.info("✓ Transcript annotated with speaker labels")

            def group_words_into_phrases(word_timings: list, speaker_segments: list) -> list:
                """
                Group word timings into sentence/phrase boundaries with speaker information.

                Returns a list of phrase objects with indexed JSON format:
                {"i": 0, "start": 0.00, "end": 3.42, "speaker": "SPEAKER_00", "text": "..."}

                Boundaries are detected by:
                - Punctuation marks (. ! ? - for sentence ends, , ; for phrase pauses)
                - Speaker changes
                - Long pauses between words (> 0.5s)
                """
                if not word_timings:
                    return []

                phrases = []
                current_phrase_words = []
                current_speaker = None
                phrase_index = 0

                # Punctuation that ends a sentence/phrase
                sentence_end_punct = {'.', '!', '?', ':', ';', ','}

                for i, word in enumerate(word_timings):
                    word_text = word.get('word', '').strip()
                    word_speaker = word.get('speaker', 'SPEAKER_UNKNOWN')
                    word_start = word.get('start_time', 0.0)

                    # Detect boundary conditions
                    is_speaker_change = word_speaker != current_speaker and current_speaker is not None
                    is_long_pause = False

                    if current_phrase_words and i > 0:
                        prev_word = word_timings[i - 1]
                        pause_duration = word_start - prev_word.get('end_time', word_start)
                        is_long_pause = pause_duration > 0.5

                    # Check if previous word ended with punctuation
                    has_sentence_punct = False
                    if current_phrase_words:
                        last_word = current_phrase_words[-1]['word'].strip()
                        has_sentence_punct = any(last_word.endswith(p) for p in sentence_end_punct)

                    # Start new phrase if boundary detected
                    if current_phrase_words and (is_speaker_change or is_long_pause or has_sentence_punct):
                        # Save current phrase
                        phrase_text = ' '.join(w['word'].strip() for w in current_phrase_words)
                        phrase_start = current_phrase_words[0]['start_time']
                        phrase_end = current_phrase_words[-1]['end_time']

                        phrases.append({
                            "i": phrase_index,
                            "start": round(phrase_start, 2),
                            "end": round(phrase_end, 2),
                            "speaker": current_speaker or word_speaker,
                            "text": phrase_text
                        })

                        phrase_index += 1
                        current_phrase_words = []

                    # Add word to current phrase
                    current_phrase_words.append(word)
                    current_speaker = word_speaker

                # Add final phrase
                if current_phrase_words:
                    phrase_text = ' '.join(w['word'].strip() for w in current_phrase_words)
                    phrase_start = current_phrase_words[0]['start_time']
                    phrase_end = current_phrase_words[-1]['end_time']

                    phrases.append({
                        "i": phrase_index,
                        "start": round(phrase_start, 2),
                        "end": round(phrase_end, 2),
                        "speaker": current_speaker,
                        "text": phrase_text
                    })

                return phrases

            # Group words into phrases with speaker information
            logger.info("Grouping word timings into sentence/phrase boundaries")
            phrases = group_words_into_phrases(word_timings, speaker_segments or [])
            logger.info(f"Grouped {len(word_timings)} words into {len(phrases)} phrases")

            # Format phrases as Natural Dialogue for better AI comprehension
            def format_as_natural_dialogue(phrases: list) -> str:
                """
                Format phrases as natural dialogue (screenplay-style).
                
                Example output:
                [00:00.00 - 00:03.42] SPEAKER_00: So this is an interesting thing about AI.
                [00:03.50 - 00:07.21] SPEAKER_01: I completely agree, but here's the catch.
                """
                lines = []
                for phrase in phrases:
                    start = phrase.get('start', 0)
                    end = phrase.get('end', 0)
                    speaker = phrase.get('speaker', 'UNKNOWN')
                    text = phrase.get('text', '')
                    
                    # Format time as MM:SS.cc
                    start_min, start_sec = divmod(start, 60)
                    end_min, end_sec = divmod(end, 60)
                    
                    time_str = f"[{int(start_min):02d}:{start_sec:05.2f} - {int(end_min):02d}:{end_sec:05.2f}]"
                    lines.append(f"{time_str} {speaker}: {text}")
                
                return "\n".join(lines)
            
            transcript_dialogue = format_as_natural_dialogue(phrases)

            # Build speaker context information if available
            speaker_info = ""
            if speaker_segments:
                speakers = list(set(s.speaker for s in speaker_segments))
                speaker_count = len(speakers)
                speaker_info = f"This podcast has {speaker_count} speaker(s): {', '.join(speakers)}."

            # SYSTEM INSTRUCTION - All rules and guidelines for the AI
            system_instruction = f"""
            ROLE
            You are an elite short-form editorial strategist for TikTok/Reels/Shorts. You surgically extract only HIGH-CONVICTION viral moments from a podcast transcript.

            OBJECTIVE
            Return ALL high-quality viral moments you can find, ordered BEST-FIRST. Do NOT pad quantity—quality is paramount. Extract as many or as few clips as the content deserves.

            HOOK QUALITY EXAMPLES
            
            EXCELLENT HOOKS (Hook Strength: 90+):
            ✓ "I lost $2 million in 48 hours because of this mistake"
            ✓ "Why do we park in driveways and drive on parkways?"
            ✓ "This will make you question everything you know about sleep"
            ✓ "Never, ever do this in a job interview"
            
            WEAK HOOKS TO AVOID (Hook Strength: <50):
            ✗ "So, continuing from where we left off earlier..."
            ✗ "That's actually a really interesting question"
            ✗ "Um, I think what's important to understand is..."
            ✗ "Another aspect of this topic that we should discuss..."
            
            TRANSFORMATION EXAMPLES:
            Poor: "That's a good point about productivity" 
            Better: "The #1 productivity myth that's destroying your workflow"
            
            Poor: "So there's this study I read about relationships"
            Better: "Couples who do this one thing are 60% more likely to divorce"

            TRANSCRIPT FORMAT
            You will receive a transcript in Natural Dialogue format (screenplay-style). Each line follows this pattern:
            [MM:SS.cc - MM:SS.cc] SPEAKER_ID: spoken text
            
            Example:
            [00:00.00 - 00:03.42] SPEAKER_00: So this is an interesting thing about AI.
            [00:03.50 - 00:07.21] SPEAKER_01: I completely agree, but here's the catch.
            
            The timestamps show [start_time - end_time] in minutes:seconds.centiseconds format.
            Use these timestamps to identify clip boundaries.

            SELECTION RULES
            - Dynamic count: Choose any number of clips based on content quality. Stop when quality drops. 1 amazing clip beats 8 mediocre ones.
            - **DURATION GUIDELINES**: Use {min_duration}s to {max_duration}s as the primary range for clip length. These are guiderails rather than hard limits; you may provide clips slightly shorter or longer if the natural narrative arc requires it or if additional context would be counterproductive to the clip's impact.
            - Target optimal length: {min_duration}–{max_duration}s. Aim for the middle of this range when possible.
            - Time values: start_time, end_time, duration use seconds as float with ≤2 decimal places. duration MUST equal end_time - start_time.
            - Order: Sort strictly by viral potential descending (strongest first).
            - Overlap: Avoid near-duplicate clips. Merge overlapping segments if they cover the same punchline. Two clips may overlap only if they deliver distinct hooks.
            - Speaker changes: If a segment crosses a speaker turn OR contains an interruption, note it in notes (e.g., "Speaker change at 23.4s").
            - Exclusions: Omit hate, illegal activity, private data, or incoherent fragments.

            SPEAKER-AWARE SELECTION
            - Prioritize dynamic exchanges: back-and-forth moments, questions + answers, reactions
            - Value speaker transitions that create tension/release or setup/punchline patterns
            - Identify moments where one speaker dominates (monologues) vs. rapid exchanges (debates)
            - Note multi-speaker interactions in the 'notes' field
            - For interview-style podcasts, favor guest responses over host questions
            - Look for controversial disagreements or surprising agreements between speakers

            HOOK REQUIREMENT (MANDATORY GATE)
            Every selected clip MUST pass this gate or be discarded:
            - First 3 seconds MUST contain one or more of:
              • Shocking statement or controversial claim
              • Provocative question that creates curiosity
              • Surprising statistic or fact
              • Strong emotional declaration (anger, excitement, awe)
              • Direct challenge to common belief
              • Immediate actionable insight
              • Pattern interrupt (unexpected sound, interruption, laughter)

            ANTI-PATTERNS TO REJECT:
            - Starting mid-sentence or mid-thought
            - Opening with context that requires prior knowledge
            - Slow build-ups or explanations before payoff
            - Filler phrases ("um", "like", "so basically")
            - References to earlier parts ("as I mentioned", "going back to")
            - Generic transitions ("another thing is", "moving on")

            If a moment has great content at seconds 10-40 but weak opening, it should be REJECTED 
            unless you can identify an earlier hook point within the same topic.

            VIRAL HEURISTICS (PRIORITIZE)
            1. Hook strength in first 3-5 seconds (CRITICAL - 40% of score)
            2. Emotional resonance (laughter, anger, awe), audible reactions, tension + release (25%)
            3. Standalone clarity—clip makes sense with minimal prior context (10%)
            4. Quotability—memorable lines, shareable phrasing (15%)
            5. Actionable or contrarian insight (10%)
            6. Visually compelling moments likely to show facial reactions / emphasis

            DE-PREFER / AVOID
            - Long multi-step setups without payoff.
            - Dry technical droning unless containing a surprising twist.
            - Moments requiring niche prior knowledge to understand.
            - Redundant restatements.

            SCORING & FIELDS (Provide meaningful, non-default values)
            - viral_score (0–100): Weighted composite calculated as:
              viral_score = (hook_strength × 0.4) + (emotional × 0.25) + (shareability × 0.15) + (clarity × 0.1) + (novelty × 0.1)
              Scores ≥60 indicate publishable; ≤50 should generally be excluded unless transcript is very weak.
              
            - hook_strength (0–100): SEPARATE score evaluating ONLY the first 3-5 seconds. This is NOT viral_score.
              • 90-100: Instant attention grab, impossible to scroll past
              • 70-89: Strong opener, clearly engaging
              • 50-69: Moderate interest, might retain viewer
              • Below 50: REJECT - weak opening that loses viewers
              Minimum acceptable hook_strength: 70. Clips below 70 MUST be discarded even if overall content is strong.
              
            - confidence (0.0–1.0): Your certainty this moment will perform (NOT identical to viral_score—confidence reflects selection reliability).
            
            - title: Punchy ≤60 chars, no clickbait fluff words repeated (avoid "insane", "shocking" unless justified).
            
            - hook: The EXACT spoken words from seconds 0-5 of the clip (max 120 chars). This must be a direct quote, not a summary.
              Evaluate this text independently: "Would a viewer stop scrolling after reading/hearing this in 3 seconds?"
              If answer is "maybe" or "no", reject the clip.
              
            - reason: 1–2 sentences explaining WHY it will go viral (no generic phrasing like "engaging" alone).
            
            - caption: Social-ready copy ≤150 chars; may include 1 relevant emoji IF it enhances, not decorates.
            
            - tags: Up to 6 lowercase thematic tags (no #, no duplicates, no generic "podcast", avoid more than 2 ultra-broad terms). If none strong, fewer is better.
            
            - thumbnail_text: ≤25 chars, ultra-punchy, no quotation marks.
            
            - recommended_crop: one of [close-up, mid, wide, focus-on-person-X]; prefer close-up if emotional emphasis.
            
            - cut_padding_before / cut_padding_after: 0.0–2.0s each; add slight breathing room without exceeding bounds.
            
            - subtitles: Exact transcript excerpt inside the chosen time window (≤300 chars) — preserve original words only.
            
            - notes: Speaker changes, audible cues ("laughter", "applause"), pacing suggestions, or why padding was added.

            HOOK VALIDATION CHECKLIST
            Before including any moment, verify:
            1. ✓ First sentence is complete (not mid-thought)
            2. ✓ Opening creates immediate curiosity or emotion
            3. ✓ No context dependency - makes sense standalone
            4. ✓ First 3 seconds contain clear value proposition
            5. ✓ Viewer would want to hear "what happens next"

            If any check fails, adjust start_time to earlier hook point or REJECT.

            TIMING INTEGRITY
            - Ensure end_time > start_time.
            - Round all time floats to at most 2 decimal places.
            - If selected segment slightly exceeds {max_duration}, trim at a natural sentence boundary without killing payoff.
            - If emotional peak occurs just outside window, shift boundaries minimally to include it (still respect {max_duration}).
            - Use the "start" and "end" times from the transcript phrases to identify viral moments.

            KEYWORD GUIDANCE
            Use keywords ONLY if they actually align with a strong viral moment; NEVER force irrelevant segments.

            MULTI-LANGUAGE
            If transcript language != English, produce title/hook/caption in that language. Tags may be in transcript language too.

            OUTPUT QUALITY FILTER
            - Discard any candidate whose hook_strength < 70 (MANDATORY).
            - Discard any candidate whose viral_score < 55 unless very few high moments exist—in scarcity, include up to the strongest available.
            - Final list MUST be sorted by viral_score descending.

            FINAL REMINDERS
            - Never hallucinate.
            - No meta-commentary about the task.
            - Do not mention you are an AI.
            - Provide ONLY high-quality moments; zero is acceptable if nothing meets criteria.
            - Only use words present in the transcript. Never invent, alter, or guess missing words.
            - Hook strength is CRITICAL: if first 3-5 seconds don't grab attention, REJECT the clip.
            """

            # CONTENT - Only the data to analyze
            keywords_section = f"Priority keywords: {', '.join(keywords)}\n\n" if keywords else ""
            speaker_section = f"{speaker_info}\n\n" if speaker_info else ""

            content = f"""{keywords_section}{speaker_section}TRANSCRIPT:
{transcript_dialogue}"""

            logger.info(f"Sending transcript to {ai_model} for structured analysis")

            # Use structured output to guarantee valid JSON with system instruction
            response_data = generate_structured_response(
                prompt=content,
                ai_model=ai_model,
                response_schema=ViralMomentsResponse,
                system_instruction=system_instruction
            )

            # Extract moments from response
            moments_data = response_data.get('moments', [])

            # Convert to ViralMoment objects
            viral_moments = []
            for i, moment in enumerate(moments_data):
                viral_moments.append(ViralMoment(
                    title=moment.get('title', f'Clip {i+1}'),
                    start_time=float(moment.get('start_time', 0)),
                    end_time=float(moment.get('end_time', 30)),
                    reason=moment.get('reason', 'Engaging content'),
                    hook=moment.get('hook', ''),
                    clip_index=i + 1,
                    thumbnail_text=moment.get('thumbnail_text', ''),
                    # AI-generated metadata fields
                    viral_score=float(moment.get('viral_score', 0)),
                    hook_strength=float(moment.get('hook_strength', 0)),
                    confidence=float(moment.get('confidence', 0.0)),
                    caption=moment.get('caption', ''),
                    tags=moment.get('tags', []),
                    recommended_crop=moment.get('recommended_crop', 'mid'),
                    cut_padding_before=float(moment.get('cut_padding_before', 0.0)),
                    cut_padding_after=float(moment.get('cut_padding_after', 0.0)),
                    subtitles=moment.get('subtitles', ''),
                    notes=moment.get('notes', '')
                ))

            logger.info(f"AI detected {len(viral_moments)} viral moments")

            # Filter out clips with weak hooks (minimum hook_strength threshold)
            MIN_HOOK_STRENGTH = 70
            moments_before_filter = len(viral_moments)
            viral_moments = [
                m for m in viral_moments 
                if m.hook_strength >= MIN_HOOK_STRENGTH
            ]
            
            if moments_before_filter > len(viral_moments):
                logger.info(f"Filtered out {moments_before_filter - len(viral_moments)} clips with hook_strength < {MIN_HOOK_STRENGTH}")
            
            # Post-process: Validate and fix clip durations
            valid_moments = []
            for m in viral_moments:
                clip_duration = m.end_time - m.start_time
                
                if clip_duration < min_duration:
                    # Try to extend clip to minimum duration
                    needed_extra = min_duration - clip_duration
                    # Add padding equally to both ends
                    extend_before = min(needed_extra / 2, m.start_time)  # Don't go before 0
                    extend_after = needed_extra - extend_before
                    
                    new_start = m.start_time - extend_before
                    new_end = m.end_time + extend_after
                    new_duration = new_end - new_start
                    
                    if new_duration >= min_duration:
                        logger.info(f"Extended clip '{m.title}' from {clip_duration:.1f}s to {new_duration:.1f}s")
                        m.start_time = new_start
                        m.end_time = new_end
                        valid_moments.append(m)
                    else:
                        logger.warning(f"Skipping clip '{m.title}' - too short ({clip_duration:.1f}s < {min_duration}s) and cannot extend")
                elif clip_duration > max_duration:
                    logger.warning(f"Trimming clip '{m.title}' from {clip_duration:.1f}s to {max_duration}s")
                    m.end_time = m.start_time + max_duration
                    valid_moments.append(m)
                else:
                    valid_moments.append(m)
            
            if len(viral_moments) > len(valid_moments):
                logger.info(f"Duration validation: {len(viral_moments)} -> {len(valid_moments)} clips")
            viral_moments = valid_moments
            
            logger.info(f"Final selection: {len(viral_moments)} clips with strong hooks (hook_strength >= {MIN_HOOK_STRENGTH})")

            # Persist viral moments
            persist_artifact(
                self.job_id,
                "ai_analysis",
                "viral_moments",
                payload={
                    "moments": [
                        {
                            "title": m.title,
                            "start_time": m.start_time,
                            "end_time": m.end_time,
                            "reason": m.reason,
                            "hook": m.hook,
                            "clip_index": m.clip_index,
                            "thumbnail_text": m.thumbnail_text,
                            "viral_score": m.viral_score,
                            "confidence": m.confidence,
                            "caption": m.caption,
                            "tags": m.tags,
                            "recommended_crop": m.recommended_crop,
                            "cut_padding_before": m.cut_padding_before,
                            "cut_padding_after": m.cut_padding_after,
                            "subtitles": m.subtitles,
                            "notes": m.notes
                        }
                        for m in viral_moments
                    ],
                    "ai_model": ai_model,
                    "actual_count": len(viral_moments)
                }
            )

            self.update_progress("ai_analysis", 55, f"Detected {len(viral_moments)} viral moments")

            return viral_moments

        except Exception as e:
            logger.error(f"Viral moment detection failed: {e}")
            raise RuntimeError(f"Failed to detect viral moments: {e}")

    def _analyze_faces(
        self,
        video_path: str,
        use_gpu: bool,
        enable_speaker_detection: bool = True,
        min_face_size_ratio: float = 0.08,
        max_tracked_faces: int = 4
    ):
        """
        Analyze video for face detection and speaker tracking.

        Args:
            video_path: Path to video file
            use_gpu: Whether to use GPU acceleration
            enable_speaker_detection: Enable audio-based speaker detection
            min_face_size_ratio: Minimum face size ratio to filter audience
            max_tracked_faces: Maximum number of faces to track
        """
        self.update_progress("face_detection", 60, "Analyzing video for face tracking")

        # Get optimization parameters from environment
        detection_height = int(os.getenv("FACE_DETECTION_HEIGHT", "720"))  # Default: 720p for 2-3x speedup
        batch_size = int(os.getenv("FACE_DETECTION_BATCH_SIZE", "4"))  # Default: 4 frames per batch

        try:
            # Check if face analysis already exists
            existing = load_artifact(self.job_id, "face_detection", "face_positions")
            if existing:
                logger.info("Found existing face detection data")
                # Initialize face tracker with existing data
                self.face_tracker = FaceTracker(
                    detection_height=detection_height,
                    batch_size=batch_size,
                    min_face_size_ratio=min_face_size_ratio,
                    max_tracked_faces=max_tracked_faces,
                    enable_speaker_detection=enable_speaker_detection
                )
                # Convert string keys back to float and reconstruct FaceBox objects
                face_positions_data = existing.get('face_positions', {})
                self.face_tracker.face_positions = {
                    float(k): FaceBox(**v) if isinstance(v, dict) else v
                    for k, v in face_positions_data.items()
                }
                self.face_tracker.video_width = existing.get('video_width', 1920)
                self.face_tracker.video_height = existing.get('video_height', 1080)
                return

            logger.info("Starting face detection analysis")
            logger.info(f"  Detection resolution: {detection_height}p, Batch size: {batch_size}")
            if enable_speaker_detection:
                logger.info(f"  Speaker detection: ENABLED (min_face_size={min_face_size_ratio}, max_faces={max_tracked_faces})")
            else:
                logger.info(f"  Speaker detection: DISABLED (legacy single-face mode)")

            self.face_tracker = FaceTracker(
                detection_height=detection_height,
                batch_size=batch_size,
                min_face_size_ratio=min_face_size_ratio,
                max_tracked_faces=max_tracked_faces,
                enable_speaker_detection=enable_speaker_detection
            )

            # Define progress callback to update job status
            def face_detection_progress(progress_pct: int, message: str):
                # Map face detection progress (0-100%) to job progress (60-70%)
                job_progress = 60 + int(progress_pct * 0.1)
                self.update_progress("face_detection", job_progress, message)

            face_positions = self.face_tracker.analyze_video(
                video_path,
                sample_rate=10,  # Reduced from 5 to 10 for less sensitive speaker switching
                progress_callback=face_detection_progress
            )

            logger.info(f"Face detection complete: {len(face_positions)} positions detected")

            # Step 4b: Speaker detection (if enabled)
            if enable_speaker_detection:
                try:
                    self.update_progress("speaker_detection", 70, "Analyzing audio for speech activity")

                    # Extract audio from video for speaker detection
                    import moviepy
                    video_clip = moviepy.VideoFileClip(video_path)
                    audio_path = str(self.temp_dir / f"{self.job_id}_audio.wav")

                    if video_clip.audio:
                        video_clip.audio.write_audiofile(audio_path, logger=None)
                        video_clip.close()

                        # Analyze audio for speech segments
                        self.face_tracker.analyze_audio_for_speech(audio_path)

                        # Correlate faces with speech
                        self.face_tracker.correlate_faces_with_speech()

                        logger.info(f"Speaker detection complete: {len(self.face_tracker.speech_segments)} speech segments detected")
                        self.update_progress("speaker_detection", 72, "Speech-face correlation complete")
                    else:
                        logger.warning("No audio track found in video - speaker detection skipped")

                except Exception as e:
                    logger.warning(f"Speaker detection failed, continuing with face-only tracking: {e}")

            # Persist face positions (convert timestamps to strings for JSON)
            persist_artifact(
                self.job_id,
                "face_detection",
                "face_positions",
                payload={
                    "face_positions": {str(k): v.__dict__ for k, v in face_positions.items()},
                    "video_width": self.face_tracker.video_width,
                    "video_height": self.face_tracker.video_height,
                    "detection_count": len(face_positions),
                    "speaker_detection_enabled": enable_speaker_detection,
                    "speech_segments_count": len(self.face_tracker.speech_segments) if enable_speaker_detection else 0
                }
            )

            self.update_progress("face_detection", 75, f"Detected faces in {len(face_positions)} frames")

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            # Face detection is not critical, continue with center crop
            logger.warning("Continuing with center crop fallback")
            self.face_tracker = FaceTracker(
                detection_height=detection_height,
                batch_size=batch_size,
                min_face_size_ratio=min_face_size_ratio,
                max_tracked_faces=max_tracked_faces,
                enable_speaker_detection=False  # Disable speaker detection on fallback
            )

    def _generate_clips(
        self,
        video_path: str,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        enable_mixed_mode: bool = True,
        face_loss_threshold: float = 1.0,
        face_return_threshold: float = 0.5,
        min_segment_duration: float = 0.5,
        use_ocr: bool = True,
        transition_duration: float = 0.5,
        smoothing_strength: int = 11,
        use_gpu: bool = True,
        enable_speaker_detection: bool = True,
        min_face_size_ratio: float = 0.02,
        max_tracked_faces: int = 4,
        subtitle_style: str = "yellow_highlight",
        subtitle_display_mode: str = "word",
        subtitle_position: str = "bottom"
    ) -> List[Dict[str, Any]]:
        """
        Generate all video clips with optional mixed-mode support.
        Performs optimized face detection only on clip segments.

        Args:
            video_path: Path to video file
            viral_moments: List of viral moments to generate
            word_timings: Word-level timings for subtitles
            enable_mixed_mode: Enable horizontal content mode detection
            face_loss_threshold: Seconds without face to trigger horizontal mode
            face_return_threshold: Seconds with face to return to face mode
            min_segment_duration: Minimum segment duration to avoid flicker
            use_ocr: Use OCR for content detection
            transition_duration: Crossfade duration between modes
            smoothing_strength: Smoothing strength for face tracking (5=light, 11=medium, 21=strong)
            use_gpu: Whether to use GPU acceleration
            enable_speaker_detection: Enable audio-based speaker detection
            min_face_size_ratio: Minimum face size ratio to filter audience
            max_tracked_faces: Maximum number of faces to track
        """
        self.update_progress("clip_generation", 60, f"Analyzing faces for {len(viral_moments)} clips")

        # Get optimization parameters from environment
        detection_height = int(os.getenv("FACE_DETECTION_HEIGHT", "720"))  # Default: 720p
        batch_size = int(os.getenv("FACE_DETECTION_BATCH_SIZE", "4"))  # Default: 4 frames
        ocr_height = int(os.getenv("OCR_HEIGHT", "720"))  # Default: 720p for OCR

        try:
            # OPTIMIZATION: Analyze faces only for clip segments (not entire video)
            # This provides 8x+ performance improvement for typical podcast with ~10 clips
            logger.info(f"Performing segment-based face detection for {len(viral_moments)} clips")

            # Initialize face tracker
            self.face_tracker = FaceTracker(
                detection_height=detection_height,
                batch_size=batch_size,
                min_face_size_ratio=min_face_size_ratio,
                max_tracked_faces=max_tracked_faces,
                enable_speaker_detection=enable_speaker_detection
            )

            # Collect all face positions from clip segments
            all_face_positions = {}
            total_segment_duration = 0.0

            for i, moment in enumerate(viral_moments):
                logger.info(f"Analyzing clip {i+1}/{len(viral_moments)}: {moment.start_time:.1f}s - {moment.end_time:.1f}s")

                # Analyze faces for this segment
                face_positions = self.face_tracker.analyze_video(
                    video_path,
                    sample_rate=10,
                    start_time=moment.start_time,
                    end_time=moment.end_time
                )

                # Merge face positions
                all_face_positions.update(face_positions)
                total_segment_duration += (moment.end_time - moment.start_time)

                # Update progress
                progress = 60 + int((i + 1) / len(viral_moments) * 10)
                self.update_progress("face_detection", progress,
                    f"Analyzed faces for clip {i+1}/{len(viral_moments)}")

            # Update face tracker with merged positions
            self.face_tracker.face_positions = all_face_positions

            logger.info(
                f"Segment-based face detection complete: "
                f"{len(all_face_positions)} positions from {total_segment_duration:.1f}s of clips "
                f"(vs analyzing entire video)"
            )

            # Perform speaker detection if enabled
            if enable_speaker_detection and self.face_tracker.speaker_detector:
                self.update_progress("speaker_detection", 70, "Analyzing audio for speech activity")

                # Extract audio from video
                import moviepy
                video_clip = moviepy.VideoFileClip(video_path)
                audio_path = str(self.temp_dir / f"{self.job_id}_audio.wav")

                if video_clip.audio:
                    video_clip.audio.write_audiofile(audio_path, logger=None)
                    video_clip.close()

                    # Analyze audio for each clip segment
                    all_speech_segments = []
                    for i, moment in enumerate(viral_moments):
                        logger.info(f"Analyzing speech for clip {i+1}/{len(viral_moments)}")

                        speech_segments = self.face_tracker.analyze_audio_for_speech(
                            audio_path,
                            start_time=moment.start_time,
                            end_time=moment.end_time
                        )
                        all_speech_segments.extend(speech_segments)

                    # Update face tracker with all speech segments
                    self.face_tracker.speech_segments = all_speech_segments

                    # Correlate faces with speech
                    if self.face_tracker.face_tracks:
                        self.face_tracker.correlate_faces_with_speech()
                        logger.info(f"Speech-face correlation complete")

                    self.update_progress("speaker_detection", 72, "Speech analysis complete")
                else:
                    logger.warning("No audio track found in video - speaker detection skipped")

            # Save debug face tracking data if debug mode is enabled
            if hasattr(self, 'debug_mode') and self.debug_mode:
                logger.info("🐛 Saving face tracking debug data")
                try:
                    self._save_face_tracking_debug_data(video_path, viral_moments)
                except Exception as e:
                    logger.warning(f"Failed to save face tracking debug data: {e}")

            self.update_progress("clip_generation", 75, f"Generating {len(viral_moments)} clips")

            # Initialize content mode detector if mixed mode is enabled
            content_mode_detector = None
            if enable_mixed_mode:
                logger.info(f"Mixed-mode enabled: face_loss={face_loss_threshold}s, face_return={face_return_threshold}s, OCR={use_ocr}")
                content_mode_detector = ContentModeDetector(
                    face_loss_threshold=face_loss_threshold,
                    face_return_threshold=face_return_threshold,
                    min_segment_duration=min_segment_duration,
                    use_ocr=use_ocr,
                    ocr_height=ocr_height,
                    face_tracker=self.face_tracker
                )
            else:
                logger.info("Mixed-mode disabled, using traditional face-tracking only")

            # Initialize clip generator with mixed-mode support
            self.clip_generator = ClipGenerator(
                face_tracker=self.face_tracker,
                output_dir=self.output_dir,
                use_gpu=True,
                content_mode_detector=content_mode_detector,
                enable_mixed_mode=enable_mixed_mode,
                ocr_height=ocr_height,
                subtitle_style=subtitle_style,
                subtitle_display_mode=subtitle_display_mode,
                subtitle_position=subtitle_position,
                text_color=self.text_color,
                highlight_color=self.highlight_color
            )

            # Set transition duration if mixed mode enabled
            if enable_mixed_mode:
                self.clip_generator.transition_duration = transition_duration

            # Generate clips in parallel
            # Use environment variable to control parallelism based on hardware
            max_workers = int(os.getenv("MAX_CLIP_WORKERS", "1"))  # Default: 1 for limited hardware
            logger.info(f"Generating {len(viral_moments)} clips with max_workers={max_workers}")

            generated_clip_objects = self.clip_generator.generate_all_clips(
                video_path=video_path,
                viral_moments=viral_moments,
                word_timings=word_timings,
                job_id=self.job_id,
                parallel=True,  # Enable parallel processing
                max_workers=max_workers,  # Configurable via MAX_CLIP_WORKERS env var
                smoothing_strength=smoothing_strength  # Smoothing for face tracking
            )

            # Convert to dict format
            generated_clips = []
            for clip in generated_clip_objects:
                generated_clips.append({
                    "clip_index": clip.clip_index,
                    "title": clip.title,
                    "output_path": clip.output_path,
                    "duration": clip.duration,
                    "file_size_mb": clip.file_size_bytes / (1024 * 1024),
                    "viral_reason": clip.viral_reason,
                    "face_coverage_pct": clip.face_coverage_pct
                })

            logger.info(f"Successfully generated {len(generated_clips)} clips in parallel")

            return generated_clips

        except Exception as e:
            logger.error(f"Clip generation failed: {e}")
            raise RuntimeError(f"Failed to generate clips: {e}")

    def _finalize(self, generated_clips: List[Dict[str, Any]], viral_moments: List[ViralMoment]) -> Dict[str, Any]:
        """Finalize processing and generate summary."""
        self.update_progress("finalization", 95, "Finalizing outputs")

        try:
            # Enrich clips with full AI metadata from viral moments
            enriched_clips = []
            for clip in generated_clips:
                clip_index = clip["clip_index"]
                # Find corresponding viral moment
                moment = next((m for m in viral_moments if m.clip_index == clip_index), None)

                # Create enriched clip data with all AI metadata
                enriched_clip = {
                    **clip,  # Keep existing data (title, output_path, duration, etc.)
                    "ai_metadata": {
                        # Core identifiers
                        "title": moment.title if moment else clip.get("title", ""),
                        "clip_index": clip_index,

                        # Timing information
                        "start_time": moment.start_time if moment else 0,
                        "end_time": moment.end_time if moment else 0,
                        "optimized_start": moment.optimized_start if moment else None,
                        "optimized_end": moment.optimized_end if moment else None,
                        "cut_padding_before": moment.cut_padding_before if moment else 0.0,
                        "cut_padding_after": moment.cut_padding_after if moment else 0.0,

                        # AI-generated content
                        "hook": moment.hook if moment else "",
                        "reason": moment.reason if moment else "",
                        "caption": moment.caption if moment else "",
                        "subtitles": moment.subtitles if moment else "",
                        "notes": moment.notes if moment else "",

                        # Scoring and confidence
                        "viral_score": moment.viral_score if moment else 0,
                        "confidence": moment.confidence if moment else 0.0,
                        "engagement_factors": moment.engagement_factors if moment else {},

                        # Metadata for publishing
                        "tags": moment.tags if moment else [],
                        "thumbnail_text": moment.thumbnail_text if moment else "",
                        "recommended_crop": moment.recommended_crop if moment else "mid",
                    } if moment else None
                }
                enriched_clips.append(enriched_clip)

            # Create summary with enriched clips
            summary = {
                "job_id": self.job_id,
                "total_clips_generated": len(enriched_clips),
                "total_clips_requested": len(viral_moments),
                "clips": enriched_clips,
                "generated_videos": enriched_clips,  # Alias for compatibility
                "total_size_mb": sum(c["file_size_mb"] for c in enriched_clips),
                "average_duration": sum(c["duration"] for c in enriched_clips) / len(enriched_clips) if enriched_clips else 0
            }

            # Save summary JSON
            summary_path = self.output_dir / f"{self.job_id}_summary.json"
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Summary saved to {summary_path}")
            logger.info(f"Enriched {len(enriched_clips)} clips with full AI metadata")

            return summary

        except Exception as e:
            logger.error(f"Finalization failed: {e}")
            raise RuntimeError(f"Failed to finalize: {e}")

    def _filter_moments_by_speaker(
        self,
        viral_moments: List[ViralMoment],
        speaker_segments: List[SpeakerSegment],
        target_speaker: Optional[str] = None,
        min_speaker_percentage: float = 0.0,
        require_exchange: bool = False
    ) -> List[ViralMoment]:
        """
        Filter moments based on Phase 2 speaker criteria.

        Args:
            viral_moments: List of ViralMoment objects
            speaker_segments: Speaker diarization segments
            target_speaker: Focus on specific speaker
            min_speaker_percentage: Min % target speaker must speak
            require_exchange: Require multiple speakers

        Returns:
            Filtered list of moments
        """
        from .speaker_diarization import SpeakerDiarizer

        diarizer = SpeakerDiarizer(use_gpu=False)

        # Convert to dicts for filtering
        moments_dicts = [
            {
                'start_time': m.optimized_start if m.optimized_start is not None else m.start_time,
                'end_time': m.optimized_end if m.optimized_end is not None else m.end_time,
                'moment': m
            }
            for m in viral_moments
        ]

        # Apply filtering
        filtered_dicts = diarizer.filter_moments_by_speaker(
            moments_dicts,
            speaker_segments,
            target_speaker=target_speaker,
            min_speaker_percentage=min_speaker_percentage,
            require_exchange=require_exchange
        )

        # Extract moments
        return [d['moment'] for d in filtered_dicts]

    def _score_and_rank_moments(
        self,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        speaker_segments: Optional[List[SpeakerSegment]] = None
    ) -> List[ViralMoment]:
        """Score and rank viral moments by quality (using optimized timing + speaker dynamics)."""
        self.update_progress("scoring", 58, f"Scoring {len(viral_moments)} optimized clips")

        try:
            logger.info("Scoring clip quality and viral potential")

            scorer = ClipScorer()

            # Score each moment
            scored_moments = []
            for moment in viral_moments:
                # Use optimized timing if available, otherwise fall back to original
                start_time = moment.optimized_start if moment.optimized_start is not None else moment.start_time
                end_time = moment.optimized_end if moment.optimized_end is not None else moment.end_time

                # Extract transcript for this moment using optimized timing
                clip_words = [
                    w['word'] for w in word_timings
                    if start_time <= w.get('start_time', 0) <= end_time
                ]
                clip_transcript = ' '.join(clip_words)

                # Score the clip with optimized timing and speaker dynamics
                score_data = scorer.score_clip(
                    transcript_text=clip_transcript,
                    word_timings=word_timings,
                    start_time=start_time,
                    end_time=end_time,
                    title=moment.title,
                    reason=moment.reason,
                    face_coverage=0.0,  # Will be updated after face detection
                    speaker_segments=speaker_segments  # Phase 2: Speaker dynamics scoring
                )

                # Update moment with score
                moment.viral_score = score_data['total_score']
                moment.engagement_factors = score_data['scores']

                scored_moments.append(moment)

                logger.debug(f"Clip {moment.clip_index} ({moment.title}): Score={moment.viral_score:.1f} (Grade: {score_data['grade']})")

            # Rank by score
            ranked_moments = sorted(scored_moments, key=lambda m: m.viral_score, reverse=True)

            # Filter to qualified clips (minimum score threshold: 60/100)
            qualified_moments = [m for m in ranked_moments if m.viral_score >= 60.0]

            # If no clips meet threshold, include the best available ones
            if not qualified_moments:
                logger.warning("No clips meet quality threshold (60/100), including top available clips")
                qualified_moments = ranked_moments[:10]  # Include up to 10 best clips even if below threshold

            # Re-index clips
            for i, moment in enumerate(qualified_moments):
                moment.clip_index = i + 1

            avg_score = sum(m.viral_score for m in qualified_moments) / len(qualified_moments) if qualified_moments else 0
            logger.info(f"Selected {len(qualified_moments)} clips (avg score: {avg_score:.1f})")

            self.update_progress("scoring", 59, f"Selected {len(qualified_moments)} quality clips")

            return qualified_moments

        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            # Return original moments if scoring fails
            return viral_moments

    def _optimize_hooks(
        self,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]]
    ) -> List[ViralMoment]:
        """Optimize clip hooks for better engagement."""
        self.update_progress("hook_optimization", 56, "Optimizing hooks for maximum engagement")

        try:
            logger.info("Optimizing clip hooks")

            optimizer = HookOptimizer(search_window=10.0)  # Expanded from 5s to 10s for better coverage

            # Build full transcript
            transcript_text = ' '.join([w['word'] for w in word_timings])

            optimized_moments = []
            for moment in viral_moments:
                # Optimize timing
                opt_start, opt_end, metadata = optimizer.optimize_clip_timing(
                    original_start=moment.start_time,
                    original_end=moment.end_time,
                    word_timings=word_timings,
                    transcript_text=transcript_text
                )

                # Update moment with optimized timing
                moment.optimized_start = opt_start
                moment.optimized_end = opt_end

                optimized_moments.append(moment)

                adjustment = opt_start - moment.start_time
                logger.debug(f"Clip {moment.clip_index} hook: {moment.start_time:.1f}s → {opt_start:.1f}s (Δ{adjustment:+.1f}s)")

            logger.info(f"Hook optimization complete for {len(optimized_moments)} clips")

            self.update_progress("hook_optimization", 60, "Hooks optimized")

            return optimized_moments

        except Exception as e:
            logger.error(f"Hook optimization failed: {e}")
            # Return original moments if optimization fails
            return viral_moments

    def _post_process_clips(
        self,
        generated_clips: List[Dict[str, Any]],
        viral_moments: List[ViralMoment]
    ) -> List[Dict[str, Any]]:
        """Post-process clips: audio enhancement only (thumbnail generation disabled)."""
        self.update_progress("post_processing", 96, "Enhancing audio")

        try:
            logger.info("Post-processing clips with audio enhancement")

            audio_enhancer = AudioEnhancer()

            enhanced_clips = []

            for i, clip_data in enumerate(generated_clips):
                clip_path = clip_data['output_path']
                clip_index = clip_data['clip_index']
                title = clip_data['title']

                logger.info(f"Post-processing clip {clip_index}/{len(generated_clips)}: {title}")

                # Audio enhancement (quick normalize)
                try:
                    logger.debug(f"Normalizing audio for clip {clip_index}")
                    audio_enhancer.quick_normalize(clip_path, output_path=clip_path)
                    logger.debug(f"Audio normalized for clip {clip_index}")
                except Exception as e:
                    logger.warning(f"Audio normalization failed for clip {clip_index}: {e}")

                # Thumbnail generation disabled - not needed for now
                clip_data['thumbnail_path'] = None

                enhanced_clips.append(clip_data)

            logger.info(f"Post-processing complete for {len(enhanced_clips)} clips")

            return enhanced_clips

        except Exception as e:
            logger.error(f"Post-processing failed: {e}")
            # Return original clips if post-processing fails
            return generated_clips

    def _extract_candidate_frames(self, video_path: str, num_frames: int = 5) -> List[str]:
        """
        Extract multiple candidate frames from video for AI selection.

        Samples frames from the first 5 seconds of the video and returns them
        as base64-encoded data URIs.

        Args:
            video_path: Path to video file
            num_frames: Number of frames to extract (default: 5)

        Returns:
            List of base64-encoded image data URIs
        """
        try:
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return []

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Sample frames from first 5 seconds
            sample_duration = min(5.0, total_frames / fps)
            sample_frames_count = int(sample_duration * fps)

            frame_data_uris = []

            # Extract frames at equal intervals
            for i in range(num_frames):
                frame_num = int((i / num_frames) * sample_frames_count)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if not ret:
                    continue

                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # Convert to base64
                frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

                # Create data URI
                data_uri = f"data:image/jpeg;base64,{frame_b64}"
                frame_data_uris.append(data_uri)

            cap.release()

            logger.debug(f"Extracted {len(frame_data_uris)} candidate frames from {video_path}")

            return frame_data_uris

        except Exception as e:
            logger.error(f"Failed to extract candidate frames: {e}", exc_info=True)
            return []

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """
        Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., "#DC2626" or "DC2626")

        Returns:
            RGB tuple (r, g, b)
        """
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _launch_debug_ui_thread(self):
        """Launch the Gradio debug UI in a background thread"""
        import threading
        import webbrowser
        import time

        def launch_ui():
            try:
                time.sleep(2)  # Wait a bit for initial processing to start
                logger.info(f"🐛 Launching debug UI at http://localhost:7860")

                from .debug_ui import launch_debug_ui

                # Open browser automatically
                try:
                    webbrowser.open('http://localhost:7860')
                except:
                    pass

                # Launch Gradio (blocking call)
                launch_debug_ui(
                    job_id=self.job_id,
                    output_dir=str(self.output_dir),
                    share=False,
                    server_port=7860
                )
            except Exception as e:
                logger.error(f"Failed to launch debug UI: {e}", exc_info=True)

        # Start in background thread
        debug_thread = threading.Thread(target=launch_ui, daemon=True)
        debug_thread.start()

        logger.info("Debug UI thread started - interface will be available shortly")

    def _save_debug_artifact(self, artifact_name: str, data: Any):
        """Save debug artifact for visualization"""
        try:
            from .debug_visualizer import save_debug_artifact
            save_debug_artifact(str(self.output_dir), artifact_name, data)
        except Exception as e:
            logger.warning(f"Failed to save debug artifact {artifact_name}: {e}")

    def _save_face_tracking_debug_data(self, video_path: str, viral_moments: List[ViralMoment]):
        """
        Save detailed face tracking data for debug visualization.
        Extracts frame-by-frame face boxes from analyzed clip segments.
        """
        try:
            import cv2

            if not self.face_tracker:
                logger.warning("No face tracker available for debug data")
                return

            logger.info("Extracting face tracking debug data from clip segments")

            # Get video properties
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            # Build frame-by-frame data from face positions
            frames_data = {}
            face_tracks_summary = []

            # Get face tracks from the tracker
            if hasattr(self.face_tracker, 'face_tracks') and self.face_tracker.face_tracks:
                for track in self.face_tracker.face_tracks:
                    # FaceTrack is a dataclass, use attribute access not .get()
                    face_id = track.face_id
                    positions = track.positions

                    # Add to summary
                    face_tracks_summary.append({
                        'face_id': face_id,
                        'positions': {str(k): {
                            'x': box.x,
                            'y': box.y,
                            'width': box.width,
                            'height': box.height,
                            'confidence': box.confidence
                        } for k, box in positions.items()},
                        'avg_area_ratio': track.avg_area_ratio,
                        'speech_correlation': track.speech_correlation,
                        'frame_count': len(positions)
                    })

                    # Build frame data
                    for timestamp, box in positions.items():
                        frame_idx = int(float(timestamp) * fps)
                        frame_key = str(frame_idx)

                        if frame_key not in frames_data:
                            frames_data[frame_key] = {'tracked': [], 'untracked': []}

                        # FaceBox is a dataclass, use attribute access
                        frames_data[frame_key]['tracked'].append({
                            'x': int(box.x),
                            'y': int(box.y),
                            'width': int(box.width),
                            'height': int(box.height),
                            'confidence': float(box.confidence),
                            'face_id': face_id
                        })

            # Get speech segments
            speech_segments = []
            if hasattr(self.face_tracker, 'speech_segments') and self.face_tracker.speech_segments:
                for segment in self.face_tracker.speech_segments:
                    # AudioSegment is a dataclass, use attribute access
                    speech_segments.append({
                        'start_time': segment.start_time,
                        'end_time': segment.end_time,
                        'energy': segment.energy,
                        'confidence': segment.confidence
                    })

            # Build complete debug data structure
            debug_data = {
                'frames': frames_data,
                'face_tracks': face_tracks_summary,
                'speech_segments': speech_segments,
                'video_info': {
                    'width': width,
                    'height': height,
                    'fps': fps
                },
                'analyzed_segments': [
                    {
                        'start_time': m.start_time,
                        'end_time': m.end_time,
                        'title': m.title
                    }
                    for m in viral_moments
                ],
                'metadata': {
                    'total_frames_analyzed': len(frames_data),
                    'total_face_tracks': len(face_tracks_summary),
                    'total_speech_segments': len(speech_segments)
                }
            }

            # Save the debug data
            self._save_debug_artifact("face_boxes_by_frame.json", debug_data)

            logger.info(
                f"Saved face tracking debug data: "
                f"{len(frames_data)} frames, "
                f"{len(face_tracks_summary)} face tracks, "
                f"{len(speech_segments)} speech segments"
            )

        except Exception as e:
            logger.error(f"Error saving face tracking debug data: {e}", exc_info=True)

    def _cleanup(self):
        """Clean up temporary files and resources."""
        logger.info("Cleaning up resources")

        try:
            # Clean up face tracker (clears accumulated face positions, tracks, etc.)
            if self.face_tracker:
                self.face_tracker.cleanup()
                self.face_tracker = None

            # Clean up clip generator
            if self.clip_generator:
                self.clip_generator.cleanup()
                self.clip_generator = None

            # Clean up subtitle colors
            self.text_color = None
            self.highlight_color = None

            # Clear speaker segments
            if hasattr(self, 'speaker_segments') and self.speaker_segments:
                self.speaker_segments = None

            # Clean up temp directory
            if self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")

            # Force garbage collection to release memory
            gc.collect()
            logger.info("Garbage collection completed")

        except Exception as e:
            logger.warning(f"Cleanup encountered error: {e}")


def process_podcast_clips(job_id: str, parameters: Dict[str, Any], output_dir: str, job_queue=None, loop=None) -> Dict[str, Any]:
    """
    Main entry point for podcast clips processing.

    Args:
        job_id: Unique job identifier
        parameters: Request parameters from PodcastClipsRequest
        output_dir: Directory for outputs
        job_queue: Job queue for progress updates (optional)
        loop: Event loop for async operations (optional)

    Returns:
        Processing results dictionary
    """
    processor = PodcastClipsProcessor(job_id, output_dir, job_queue=job_queue, loop=loop)
    return processor.process(parameters)
