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
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import tempfile

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Use video-processor's utils instead of backend modules
from utils.youtube import download_video, extract_video_id
from utils.artifacts import persist_artifact, load_artifact

# Create stub for job store since video-processor doesn't have database module
class JobStoreStub:
    """Stub for job store when running in video-processor context."""
    def update_job_progress(self, job_id, progress, status, step=None, message=None):
        # Progress updates are handled by the video-processor's job queue
        pass

def get_job_store():
    """Return stub job store for video-processor context."""
    return JobStoreStub()

from .face_tracker import FaceTracker, FaceBox
from .subtitle_generator import SubtitleGenerator
from .clip_generator import ClipGenerator, ViralMoment
from .content_detector import ContentModeDetector
from .thumbnail_generator import ThumbnailGenerator
from .audio_enhancer import AudioEnhancer
from .clip_scorer import ClipScorer
from .hook_optimizer import HookOptimizer
from vendors.AIvideos.stable_ts_enhanced_subtitles import extract_word_timings_with_stable_ts
from vendors.AIvideos.gpt import generate_structured_response, ViralMomentsResponse

logger = logging.getLogger("video_generator.podcastclips.processor")


class PodcastClipsProcessor:
    """
    Main processor for podcast clips workflow.

    Orchestrates the entire pipeline from YouTube download to final clip generation.
    """

    def __init__(
        self,
        job_id: str,
        output_dir: str,
        temp_dir: Optional[str] = None
    ):
        """
        Initialize processor.

        Args:
            job_id: Unique job identifier
            output_dir: Directory for final outputs
            temp_dir: Temporary directory for intermediate files
        """
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / f"podcastclips_{job_id}"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Job store for progress tracking
        self.job_store = get_job_store()

        # Component instances (initialized during processing)
        self.face_tracker: Optional[FaceTracker] = None
        self.subtitle_generator: Optional[SubtitleGenerator] = None
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
            if not youtube_url:
                raise ValueError("YouTube URL is required")
            
            ai_model = parameters.get('aiModel', 'gemini-2.5-pro')
            whisper_model = parameters.get('whisperModel', 'base')
            target_clip_count = parameters.get('targetClipCount', 7)
            min_duration = parameters.get('minDuration', 30)
            max_duration = parameters.get('maxDuration', 60)
            use_gpu = parameters.get('useGPU', True)
            subtitle_font_size = parameters.get('subtitleFontSize', 40)
            subtitle_color = parameters.get('subtitleColor', '#FFFFFF')
            subtitle_stroke_color = parameters.get('subtitleStrokeColor', '#000000')
            subtitle_stroke_width = parameters.get('subtitleStrokeWidth', 2)
            viral_keywords = parameters.get('viralFocusKeywords', [])

            # Mixed-mode configuration
            enable_mixed_mode = parameters.get('enableMixedMode', True)
            face_loss_threshold = parameters.get('faceLossThreshold', 1.0)
            face_return_threshold = parameters.get('faceReturnThreshold', 0.5)
            min_segment_duration = parameters.get('minSegmentDuration', 0.5)
            use_ocr = parameters.get('useOCR', True)
            transition_duration = parameters.get('transitionDuration', 0.5)

            # Step 1: Download video
            video_path = self._download_video(youtube_url)

            # Step 2: Transcribe
            word_timings = self._transcribe_video(video_path, whisper_model, use_gpu)

            # Step 3: Detect viral moments
            viral_moments = self._detect_viral_moments(
                word_timings, ai_model, target_clip_count,
                min_duration, max_duration, viral_keywords
            )

            # Step 4: Score and rank viral moments
            viral_moments = self._score_and_rank_moments(
                viral_moments, word_timings, target_clip_count
            )

            # Step 5: Optimize hooks for better engagement
            viral_moments = self._optimize_hooks(viral_moments, word_timings)

            # Step 6: Analyze faces
            self._analyze_faces(video_path, use_gpu)

            # Step 7: Initialize subtitle generator
            self._initialize_subtitle_generator(
                subtitle_font_size, subtitle_color,
                subtitle_stroke_color, subtitle_stroke_width
            )

            # Step 8: Generate clips (parallel)
            generated_clips = self._generate_clips(
                video_path, viral_moments, word_timings,
                enable_mixed_mode, face_loss_threshold, face_return_threshold,
                min_segment_duration, use_ocr, transition_duration
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
                refine_whisper_precision=0.15
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

    def _detect_viral_moments(
        self,
        word_timings: List[Dict[str, Any]],
        ai_model: str,
        target_count: int,
        min_duration: int,
        max_duration: int,
        keywords: List[str]
    ) -> List[ViralMoment]:
        """Use Gemini AI to detect viral moments."""
        self.update_progress("ai_analysis", 40, "Analyzing content for viral moments")

        try:
            # Check if analysis already exists (resume support)
            existing = load_artifact(self.job_id, "ai_analysis", "viral_moments")
            if existing:
                logger.info("Found existing viral moments analysis")
                moments_data = existing.get('moments', [])
                return [ViralMoment(**m) for m in moments_data]

            # Build transcript with timestamps for AI
            transcript_lines = []
            for i, word in enumerate(word_timings):
                if i % 20 == 0:  # Add timestamp every 20 words
                    transcript_lines.append(f"[{word['start_time']:.1f}s] {word['word']}")
                else:
                    transcript_lines.append(word['word'])

            transcript_text = ' '.join(transcript_lines)

            # Prepare prompt (simplified - no need for detailed JSON format instructions)
            keywords_hint = f"\n\nPriority keywords: {', '.join(keywords)}" if keywords else ""

            prompt = f"""
            You are an expert content editor and viral-clip scout for social media (TikTok, Reels, Shorts).
            You will analyze the provided podcast transcript and identify the {target_count} moments with the highest viral potential.

            Hard rules:
            - Return up to {target_count} moments, ordered best-first (highest viral potential first).
            - Times must be floats in seconds from video start.
            - CRITICAL: Each clip's duration MUST be AT LEAST {min_duration} seconds and AT MOST {max_duration} seconds.
            - NEVER create clips shorter than {min_duration} seconds - extend them if needed to meet this minimum.
            - Target clips around 45-50 seconds for optimal TikTok/Reels engagement (within the {min_duration}-{max_duration}s range).
            - Do not hallucinate words—use only transcript text provided.
            - If a clip crosses a speaker turn, indicate speaker change in the "notes" field.
            - If content includes hate/illegal content, exclude it (return fewer clips).

            Context / heuristics to use:
            - Prefer moments with immediate hooks in the first ~3s, emotional impact (anger, laughter, awe), surprising facts, concise strong opinions, concrete advice, or controversy.
            - Prefer lines that are quotable and make sense standalone (no long setup needed).
            - Prefer moments with clear audio cues (laughter, applause, gasps) or an energetic delivery.
            - Avoid long setup, multi-step lists that require prior context, and dry technical segments unless they include a surprising insight.
            - Prioritize moments that map well to vertical video (close-up reactions, punchlines, reveals).

            Keywords (optional): {keywords_hint}

            Transcript:
            {transcript_text}

            Additional instructions:
            - Compute "duration" exactly as end_time - start_time.
            - Keep "hook" short and commanding — it will be the first line shown/said.
            - Make "caption" usable as social post copy; include one emoji if it helps.
            - Provide tags that match the moment's theme (without # symbol).
            - If you cannot find {target_count} valid moments, return as many as you can.
            - If transcript language is not English, produce hook/caption in the transcript language.
            """

            logger.info(f"Sending transcript to {ai_model} for structured analysis")

            # Use structured output to guarantee valid JSON
            response_data = generate_structured_response(prompt, ai_model, ViralMomentsResponse)

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
                    clip_index=i + 1
                ))

            logger.info(f"AI detected {len(viral_moments)} viral moments")

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
                            "clip_index": m.clip_index
                        }
                        for m in viral_moments
                    ],
                    "ai_model": ai_model,
                    "target_count": target_count
                }
            )

            self.update_progress("ai_analysis", 55, f"Detected {len(viral_moments)} viral moments")

            return viral_moments

        except Exception as e:
            logger.error(f"Viral moment detection failed: {e}")
            raise RuntimeError(f"Failed to detect viral moments: {e}")

    def _analyze_faces(self, video_path: str, use_gpu: bool):
        """Analyze video for face detection."""
        self.update_progress("face_detection", 60, "Analyzing video for face tracking")

        try:
            # Check if face analysis already exists
            existing = load_artifact(self.job_id, "face_detection", "face_positions")
            if existing:
                logger.info("Found existing face detection data")
                # Initialize face tracker with existing data
                self.face_tracker = FaceTracker(use_gpu=use_gpu)
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

            self.face_tracker = FaceTracker(use_gpu=use_gpu)

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

            # Persist face positions (convert timestamps to strings for JSON)
            persist_artifact(
                self.job_id,
                "face_detection",
                "face_positions",
                payload={
                    "face_positions": {str(k): v.__dict__ for k, v in face_positions.items()},
                    "video_width": self.face_tracker.video_width,
                    "video_height": self.face_tracker.video_height,
                    "detection_count": len(face_positions)
                }
            )

            self.update_progress("face_detection", 70, f"Detected faces in {len(face_positions)} frames")

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            # Face detection is not critical, continue with center crop
            logger.warning("Continuing with center crop fallback")
            self.face_tracker = FaceTracker(use_gpu=use_gpu)

    def _initialize_subtitle_generator(
        self,
        font_size: int,
        color: str,
        stroke_color: str,
        stroke_width: int
    ):
        """Initialize subtitle generator."""
        logger.info("Initializing subtitle generator")

        self.subtitle_generator = SubtitleGenerator(
            font_size=font_size,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            position="bottom"
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
        transition_duration: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Generate all video clips with optional mixed-mode support.

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
        """
        self.update_progress("clip_generation", 75, f"Generating {len(viral_moments)} clips")

        try:
            # Ensure face tracker is available (fallback to basic instance if needed)
            if self.face_tracker is None:
                logger.warning("Face tracker not available, initializing fallback instance")
                self.face_tracker = FaceTracker(use_gpu=True)

            # Ensure subtitle generator is available (fallback to basic instance if needed)
            if self.subtitle_generator is None:
                logger.warning("Subtitle generator not available, initializing fallback instance")
                self.subtitle_generator = SubtitleGenerator()

            # Initialize content mode detector if mixed mode is enabled
            content_mode_detector = None
            if enable_mixed_mode:
                logger.info(f"Mixed-mode enabled: face_loss={face_loss_threshold}s, face_return={face_return_threshold}s, OCR={use_ocr}")
                content_mode_detector = ContentModeDetector(
                    face_loss_threshold=face_loss_threshold,
                    face_return_threshold=face_return_threshold,
                    min_segment_duration=min_segment_duration,
                    use_ocr=use_ocr
                )
            else:
                logger.info("Mixed-mode disabled, using traditional face-tracking only")

            # Initialize clip generator with mixed-mode support
            self.clip_generator = ClipGenerator(
                face_tracker=self.face_tracker,
                subtitle_generator=self.subtitle_generator,
                output_dir=self.output_dir,
                use_gpu=True,
                content_mode_detector=content_mode_detector,
                enable_mixed_mode=enable_mixed_mode
            )

            # Set transition duration if mixed mode enabled
            if enable_mixed_mode:
                self.clip_generator.transition_duration = transition_duration

            # Generate clips in parallel (3x-5x speedup)
            logger.info(f"Generating {len(viral_moments)} clips in parallel")

            generated_clip_objects = self.clip_generator.generate_all_clips(
                video_path=video_path,
                viral_moments=viral_moments,
                word_timings=word_timings,
                job_id=self.job_id,
                parallel=True,  # Enable parallel processing
                max_workers=3   # 3 concurrent clips
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
            # Create summary
            summary = {
                "job_id": self.job_id,
                "total_clips_generated": len(generated_clips),
                "total_clips_requested": len(viral_moments),
                "clips": generated_clips,
                "total_size_mb": sum(c["file_size_mb"] for c in generated_clips),
                "average_duration": sum(c["duration"] for c in generated_clips) / len(generated_clips) if generated_clips else 0
            }

            # Save summary JSON
            summary_path = self.output_dir / f"{self.job_id}_summary.json"
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Summary saved to {summary_path}")

            return summary

        except Exception as e:
            logger.error(f"Finalization failed: {e}")
            raise RuntimeError(f"Failed to finalize: {e}")

    def _score_and_rank_moments(
        self,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        target_count: int
    ) -> List[ViralMoment]:
        """Score and rank viral moments by quality."""
        self.update_progress("scoring", 56, f"Scoring {len(viral_moments)} viral moments")

        try:
            logger.info("Scoring clip quality and viral potential")

            scorer = ClipScorer()

            # Score each moment
            scored_moments = []
            for moment in viral_moments:
                # Extract transcript for this moment
                clip_words = [
                    w['word'] for w in word_timings
                    if moment.start_time <= w.get('start_time', 0) <= moment.end_time
                ]
                clip_transcript = ' '.join(clip_words)

                # Score the clip
                score_data = scorer.score_clip(
                    transcript_text=clip_transcript,
                    word_timings=word_timings,
                    start_time=moment.start_time,
                    end_time=moment.end_time,
                    title=moment.title,
                    reason=moment.reason,
                    face_coverage=0.0  # Will be updated after face detection
                )

                # Update moment with score
                moment.viral_score = score_data['total_score']
                moment.engagement_factors = score_data['scores']

                scored_moments.append(moment)

                logger.debug(f"Clip {moment.clip_index} ({moment.title}): Score={moment.viral_score:.1f} (Grade: {score_data['grade']})")

            # Rank by score
            ranked_moments = sorted(scored_moments, key=lambda m: m.viral_score, reverse=True)

            # Filter to top clips (minimum score threshold: 60/100)
            qualified_moments = [m for m in ranked_moments if m.viral_score >= 60.0]

            # If we don't have enough qualified clips, lower the threshold
            if len(qualified_moments) < target_count:
                logger.warning(f"Only {len(qualified_moments)} clips meet quality threshold (60/100)")
                qualified_moments = ranked_moments[:target_count]

            # Limit to target count
            final_moments = qualified_moments[:target_count]

            # Re-index clips
            for i, moment in enumerate(final_moments):
                moment.clip_index = i + 1

            logger.info(f"Selected top {len(final_moments)} clips (avg score: {sum(m.viral_score for m in final_moments)/len(final_moments):.1f})")

            self.update_progress("scoring", 58, f"Selected {len(final_moments)} top-quality clips")

            return final_moments

        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            # Return original moments if scoring fails
            return viral_moments[:target_count]

    def _optimize_hooks(
        self,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]]
    ) -> List[ViralMoment]:
        """Optimize clip hooks for better engagement."""
        self.update_progress("hook_optimization", 59, "Optimizing hooks for maximum engagement")

        try:
            logger.info("Optimizing clip hooks")

            optimizer = HookOptimizer(search_window=5.0)

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
        """Post-process clips: audio enhancement and thumbnail generation."""
        self.update_progress("post_processing", 96, "Enhancing audio and generating thumbnails")

        try:
            logger.info("Post-processing clips")

            audio_enhancer = AudioEnhancer()
            thumbnail_gen = ThumbnailGenerator(platform="universal")

            enhanced_clips = []

            for i, clip_data in enumerate(generated_clips):
                clip_path = clip_data['output_path']
                clip_index = clip_data['clip_index']
                title = clip_data['title']

                # Find corresponding viral moment
                moment = next((m for m in viral_moments if m.clip_index == clip_index), None)

                logger.info(f"Post-processing clip {clip_index}/{len(generated_clips)}: {title}")

                # 1. Audio enhancement (quick normalize)
                try:
                    logger.debug(f"Normalizing audio for clip {clip_index}")
                    audio_enhancer.quick_normalize(clip_path, output_path=clip_path)
                    logger.debug(f"Audio normalized for clip {clip_index}")
                except Exception as e:
                    logger.warning(f"Audio normalization failed for clip {clip_index}: {e}")

                # 2. Generate thumbnail
                try:
                    logger.debug(f"Generating thumbnail for clip {clip_index}")
                    thumbnail_path = clip_path.replace('.mp4', '_thumbnail.jpg')

                    # Use optimized start time if available
                    timestamp = moment.optimized_start if moment and moment.optimized_start else None

                    thumbnail_gen.generate_thumbnail(
                        video_path=clip_path,
                        title=title,
                        output_path=thumbnail_path,
                        timestamp=2.0  # 2 seconds in for best frame
                    )

                    clip_data['thumbnail_path'] = thumbnail_path
                    logger.debug(f"Thumbnail generated for clip {clip_index}")

                except Exception as e:
                    logger.warning(f"Thumbnail generation failed for clip {clip_index}: {e}")
                    clip_data['thumbnail_path'] = None

                enhanced_clips.append(clip_data)

            logger.info(f"Post-processing complete for {len(enhanced_clips)} clips")

            return enhanced_clips

        except Exception as e:
            logger.error(f"Post-processing failed: {e}")
            # Return original clips if post-processing fails
            return generated_clips

    def _cleanup(self):
        """Clean up temporary files and resources."""
        logger.info("Cleaning up resources")

        try:
            if self.face_tracker:
                self.face_tracker.cleanup()

            if self.clip_generator:
                self.clip_generator.cleanup()

            # Clean up temp directory
            if self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")

        except Exception as e:
            logger.warning(f"Cleanup encountered error: {e}")


def process_podcast_clips(job_id: str, parameters: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Main entry point for podcast clips processing.

    Args:
        job_id: Unique job identifier
        parameters: Request parameters from PodcastClipsRequest
        output_dir: Directory for outputs

    Returns:
        Processing results dictionary
    """
    processor = PodcastClipsProcessor(job_id, output_dir)
    return processor.process(parameters)
