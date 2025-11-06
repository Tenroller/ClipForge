"""
Video clip generation module for podcast clips.

Handles video cutting, cropping to 9:16 format, and final composition.
"""

import logging
import platform
import sys
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from moviepy import VideoFileClip, CompositeVideoClip
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .face_tracker import FaceTracker, CropBox
from .subtitle_generator import SubtitleGenerator

# Import codec detection from AIvideos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from AIvideos.video import get_video_codec_settings

logger = logging.getLogger(__name__)


@dataclass
class ViralMoment:
    """Information about a viral moment detected by AI."""
    title: str
    start_time: float
    end_time: float
    reason: str
    hook: str
    clip_index: int
    viral_score: float = 0.0  # 0-100 quality score
    engagement_factors: Dict[str, float] = field(default_factory=dict)  # Breakdown of score
    optimized_start: Optional[float] = None  # Hook-optimized start time
    optimized_end: Optional[float] = None  # Hook-optimized end time

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time

    @property
    def optimized_duration(self) -> float:
        """Duration after hook optimization."""
        if self.optimized_start and self.optimized_end:
            return self.optimized_end - self.optimized_start
        return self.duration


@dataclass
class GeneratedClip:
    """Information about a generated clip."""
    clip_index: int
    title: str
    output_path: str
    duration: float
    file_size_bytes: int
    viral_reason: str
    face_coverage_pct: float


class ClipGenerator:
    """
    Generate short-form vertical video clips from podcast video.

    Handles video segment extraction, face-focused cropping to 9:16,
    subtitle overlay, and final export.
    """

    def __init__(
        self,
        face_tracker: FaceTracker,
        subtitle_generator: SubtitleGenerator,
        output_dir: Path,
        use_gpu: bool = True
    ):
        """
        Initialize clip generator.

        Args:
            face_tracker: FaceTracker instance for crop box calculation
            subtitle_generator: SubtitleGenerator instance for subtitles
            output_dir: Directory to save generated clips
            use_gpu: Whether to use GPU acceleration for encoding
        """
        self.face_tracker = face_tracker
        self.subtitle_generator = subtitle_generator
        self.output_dir = Path(output_dir)
        self.use_gpu = use_gpu

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Target resolution for vertical format (9:16)
        self.target_resolution = (1080, 1920)

    def generate_clip(
        self,
        video_path: str,
        viral_moment: ViralMoment,
        word_timings: List[Dict[str, Any]],
        job_id: str
    ) -> Optional[GeneratedClip]:
        """
        Generate a single viral clip.

        Args:
            video_path: Path to source video
            viral_moment: ViralMoment with timing and metadata
            word_timings: Full list of word timings from transcription
            job_id: Job ID for output filename

        Returns:
            GeneratedClip with metadata, or None if generation failed
        """
        try:
            logger.info(f"Generating clip {viral_moment.clip_index}: '{viral_moment.title}' ({viral_moment.start_time:.1f}s - {viral_moment.end_time:.1f}s)")

            # Load video and extract segment
            logger.debug(f"Loading video: {video_path}")
            video = VideoFileClip(video_path)

            # Validate timing
            if viral_moment.end_time > video.duration:
                logger.warning(f"Clip end time {viral_moment.end_time}s exceeds video duration {video.duration}s, adjusting")
                viral_moment.end_time = video.duration

            # Extract clip segment
            logger.debug(f"Extracting segment: {viral_moment.start_time:.1f}s to {viral_moment.end_time:.1f}s")
            clip = video.subclipped(viral_moment.start_time, viral_moment.end_time)

            # Get optimal crop box from face tracker
            logger.debug("Calculating optimal crop box")
            crop_box = self.face_tracker.get_optimal_crop_box(
                viral_moment.start_time,
                viral_moment.end_time
            )

            # Get face coverage percentage for metadata
            face_coverage = self.face_tracker.get_face_coverage_percentage(
                viral_moment.start_time,
                viral_moment.end_time
            )

            # Apply crop to 9:16 format
            logger.debug(f"Applying crop: x={crop_box.x}, width={crop_box.width}")
            x1, y1, x2, y2 = crop_box.to_moviepy_crop()
            clip = clip.cropped(x1, y1, x2, y2)

            # Resize to target resolution (1080x1920)
            logger.debug(f"Resizing to {self.target_resolution[0]}x{self.target_resolution[1]}")
            clip = clip.resized(self.target_resolution)

            # Extract relevant word timings for this clip
            logger.debug("Extracting word timings for subtitle generation")
            clip_word_timings = self.subtitle_generator.extract_words_for_timerange(
                word_timings,
                viral_moment.start_time,
                viral_moment.end_time
            )

            # Add subtitles
            if clip_word_timings:
                logger.debug("Adding subtitles to clip")
                clip = self.subtitle_generator.add_subtitles_to_video(
                    clip,
                    word_timings,
                    clip_start_time=viral_moment.start_time
                )
            else:
                logger.warning("No word timings found for clip, skipping subtitles")

            # Generate output filename
            safe_title = "".join(c for c in viral_moment.title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title[:50]  # Limit filename length
            output_filename = f"{job_id}_clip_{viral_moment.clip_index}_{safe_title}.mp4"
            output_path = self.output_dir / output_filename

            # Export video
            logger.info(f"Exporting clip to: {output_path}")

            # Get optimal codec settings with full FFmpeg parameters
            codec_settings = get_video_codec_settings(use_gpu=self.use_gpu)

            try:
                # Attempt export with optimal codec settings
                clip.write_videofile(
                    str(output_path),
                    codec=codec_settings['codec'],
                    audio_codec="aac",
                    fps=30,
                    ffmpeg_params=codec_settings.get('ffmpeg_params', []),
                    threads=4,
                    logger=None  # Disable MoviePy's verbose logging
                )
            except Exception as e:
                # If hardware encoding fails, fall back to software encoding
                if codec_settings['codec'] != 'libx264':
                    logger.warning(f"Hardware encoding failed ({e}), falling back to CPU encoding")
                    fallback_settings = get_video_codec_settings(use_gpu=False)
                    clip.write_videofile(
                        str(output_path),
                        codec=fallback_settings['codec'],
                        audio_codec="aac",
                        fps=30,
                        ffmpeg_params=fallback_settings.get('ffmpeg_params', []),
                        threads=4,
                        logger=None
                    )
                else:
                    # Already using CPU encoding, re-raise the error
                    raise

            # Clean up
            clip.close()
            video.close()

            # Get file size
            file_size = output_path.stat().st_size

            logger.info(f"Clip {viral_moment.clip_index} generated successfully: {file_size / (1024*1024):.2f} MB")

            return GeneratedClip(
                clip_index=viral_moment.clip_index,
                title=viral_moment.title,
                output_path=str(output_path),
                duration=viral_moment.duration,
                file_size_bytes=file_size,
                viral_reason=viral_moment.reason,
                face_coverage_pct=face_coverage
            )

        except Exception as e:
            logger.error(f"Failed to generate clip {viral_moment.clip_index}: {e}", exc_info=True)
            return None

    def generate_all_clips(
        self,
        video_path: str,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        job_id: str,
        parallel: bool = True,
        max_workers: int = 3
    ) -> List[GeneratedClip]:
        """
        Generate all viral clips from a video (supports parallel processing).

        Args:
            video_path: Path to source video
            viral_moments: List of viral moments to generate
            word_timings: Full list of word timings
            job_id: Job ID for output filenames
            parallel: Whether to use parallel processing (default: True)
            max_workers: Maximum parallel workers (default: 3)

        Returns:
            List of successfully generated clips (sorted by clip_index)
        """
        if parallel and len(viral_moments) > 1:
            return self._generate_clips_parallel(video_path, viral_moments, word_timings, job_id, max_workers)
        else:
            return self._generate_clips_sequential(video_path, viral_moments, word_timings, job_id)

    def _generate_clips_sequential(
        self,
        video_path: str,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        job_id: str
    ) -> List[GeneratedClip]:
        """Sequential clip generation (original method)."""
        generated_clips = []

        logger.info(f"Generating {len(viral_moments)} clips sequentially")

        for moment in viral_moments:
            clip = self.generate_clip(video_path, moment, word_timings, job_id)
            if clip:
                generated_clips.append(clip)

        logger.info(f"Successfully generated {len(generated_clips)}/{len(viral_moments)} clips")

        return generated_clips

    def _generate_clips_parallel(
        self,
        video_path: str,
        viral_moments: List[ViralMoment],
        word_timings: List[Dict[str, Any]],
        job_id: str,
        max_workers: int
    ) -> List[GeneratedClip]:
        """
        Parallel clip generation for 3x-5x speedup.

        Uses ThreadPoolExecutor to generate multiple clips simultaneously.
        Thread-safe for MoviePy operations.
        """
        generated_clips = []
        lock = threading.Lock()

        logger.info(f"Generating {len(viral_moments)} clips in parallel (max_workers={max_workers})")

        def generate_with_logging(moment):
            """Wrapper for thread-safe logging."""
            try:
                clip = self.generate_clip(video_path, moment, word_timings, job_id)
                if clip:
                    with lock:
                        logger.info(f"✓ Completed clip {moment.clip_index}/{len(viral_moments)}: {moment.title}")
                return clip
            except Exception as e:
                with lock:
                    logger.error(f"✗ Failed clip {moment.clip_index}: {e}")
                return None

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_moment = {
                executor.submit(generate_with_logging, moment): moment
                for moment in viral_moments
            }

            # Collect results as they complete
            for future in as_completed(future_to_moment):
                clip = future.result()
                if clip:
                    generated_clips.append(clip)

        # Sort by clip_index to maintain order
        generated_clips.sort(key=lambda c: c.clip_index)

        logger.info(f"✓ Parallel generation complete: {len(generated_clips)}/{len(viral_moments)} clips succeeded")

        return generated_clips

    def validate_viral_moment(self, moment: ViralMoment, video_duration: float) -> bool:
        """
        Validate that a viral moment is valid for video generation.

        Args:
            moment: ViralMoment to validate
            video_duration: Total video duration in seconds

        Returns:
            True if valid, False otherwise
        """
        # Check timing is valid
        if moment.start_time < 0:
            logger.warning(f"Clip {moment.clip_index} has negative start time: {moment.start_time}")
            return False

        if moment.end_time > video_duration:
            logger.warning(f"Clip {moment.clip_index} end time {moment.end_time}s exceeds video duration {video_duration}s")
            # Allow with adjustment
            return True

        if moment.start_time >= moment.end_time:
            logger.warning(f"Clip {moment.clip_index} has invalid timing: start={moment.start_time}s >= end={moment.end_time}s")
            return False

        # Check duration is reasonable (at least 5 seconds, max 120 seconds)
        duration = moment.duration
        if duration < 5:
            logger.warning(f"Clip {moment.clip_index} too short: {duration:.1f}s")
            return False

        if duration > 120:
            logger.warning(f"Clip {moment.clip_index} too long: {duration:.1f}s")
            return False

        return True

    def cleanup(self):
        """Clean up resources."""
        logger.debug("Cleaning up clip generator resources")
        # No specific cleanup needed currently
        pass
