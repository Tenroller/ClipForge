"""
Video clip generation module for podcast clips.

Handles video cutting, cropping to 9:16 format, and final composition.
"""

import logging
import platform
import sys
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip, concatenate_videoclips
from moviepy import vfx
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import numpy as np

from .face_tracker import FaceTracker, CropBox
from .subtitle_generator import SubtitleGenerator
from .content_detector import ContentModeDetector, ContentSegment, ContentMode

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
        use_gpu: bool = True,
        content_mode_detector: Optional[ContentModeDetector] = None,
        enable_mixed_mode: bool = True
    ):
        """
        Initialize clip generator.

        Args:
            face_tracker: FaceTracker instance for crop box calculation
            subtitle_generator: SubtitleGenerator instance for subtitles
            output_dir: Directory to save generated clips
            use_gpu: Whether to use GPU acceleration for encoding
            content_mode_detector: Optional ContentModeDetector for mixed-mode support
            enable_mixed_mode: Whether to enable horizontal content mode detection
        """
        self.face_tracker = face_tracker
        self.subtitle_generator = subtitle_generator
        self.output_dir = Path(output_dir)
        self.use_gpu = use_gpu
        self.content_mode_detector = content_mode_detector
        self.enable_mixed_mode = enable_mixed_mode

        # Create content mode detector if not provided and mixed mode enabled
        if self.enable_mixed_mode and self.content_mode_detector is None:
            self.content_mode_detector = ContentModeDetector()

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Target resolution for vertical format (9:16)
        self.target_resolution = (1080, 1920)

        # Transition duration between modes (seconds)
        self.transition_duration = 0.5

    def create_horizontal_content_clip(
        self,
        clip: VideoFileClip,
        blur_background: bool = True,
        background_color: Tuple[int, int, int] = (20, 20, 20)
    ) -> VideoFileClip:
        """
        Create horizontal content clip centered in 9:16 canvas with blurred background.

        Args:
            clip: Source video clip (horizontal format)
            blur_background: Whether to blur the background (True) or use solid color
            background_color: RGB color for solid background (if blur_background=False)

        Returns:
            Composite clip in 9:16 format with horizontal content centered
        """
        target_width, target_height = self.target_resolution
        clip_width, clip_height = clip.size

        # Calculate scaling to fit within canvas (preserving aspect ratio)
        # Leave some padding (90% of height)
        max_content_height = int(target_height * 0.90)
        max_content_width = int(target_width * 0.95)

        # Scale clip to fit
        scale_by_width = max_content_width / clip_width
        scale_by_height = max_content_height / clip_height
        scale = min(scale_by_width, scale_by_height)

        scaled_width = int(clip_width * scale)
        scaled_height = int(clip_height * scale)

        # Resize the content clip
        content_clip = clip.resized((scaled_width, scaled_height))

        if blur_background:
            # Create blurred background from the same clip
            # 1. Resize to full height
            bg_clip = clip.resized(height=target_height)

            # 2. Apply blur by resizing down and back up
            blur_strength = 0.15  # 15% of original size
            small_width = int(bg_clip.w * blur_strength)
            small_height = int(bg_clip.h * blur_strength)

            bg_clip = bg_clip.resized((small_width, small_height))
            bg_clip = bg_clip.resized((target_width, target_height))

            # 3. Darken the background (reduce brightness by 50%)
            bg_clip = bg_clip.with_effects([vfx.MultiplyColor(0.5)])

            # 4. Center content on blurred background
            content_clip = content_clip.with_position(('center', 'center'))

            # 5. Composite
            final_clip = CompositeVideoClip(
                [bg_clip, content_clip],
                size=self.target_resolution
            )
        else:
            # Use solid color background
            bg_clip = ColorClip(
                size=self.target_resolution,
                color=background_color,
                duration=clip.duration
            )

            content_clip = content_clip.with_position(('center', 'center'))

            final_clip = CompositeVideoClip(
                [bg_clip, content_clip],
                size=self.target_resolution
            )

        # IMPORTANT: Preserve audio from original clip
        # CompositeVideoClip doesn't automatically inherit audio
        if hasattr(clip, 'audio') and clip.audio is not None:
            final_clip = final_clip.with_audio(clip.audio)

        return final_clip

    def create_face_tracked_clip(
        self,
        clip: VideoFileClip,
        start_time: float,
        dynamic_tracking: bool = True
    ) -> VideoFileClip:
        """
        Create face-tracked vertical clip with 9:16 crop.

        Args:
            clip: Source video clip
            start_time: Start time of clip in original video (for face tracking)
            dynamic_tracking: If True, crop follows face frame-by-frame. If False, use static crop.

        Returns:
            Cropped and resized clip in 9:16 format
        """
        if not dynamic_tracking:
            # Legacy static crop mode
            crop_box = self.face_tracker.get_optimal_crop_box(start_time, start_time + clip.duration)
            x1, y1, x2, y2 = crop_box.to_moviepy_crop()
            cropped = clip.cropped(x1, y1, x2, y2)
            resized = cropped.resized(self.target_resolution)
            return resized

        # Dynamic tracking mode - crop follows face frame-by-frame
        target_width, target_height = self.target_resolution
        original_width, original_height = clip.size

        def make_frame(t):
            """
            Custom frame function that crops based on face position at time t.
            """
            # Get absolute timestamp in original video
            absolute_time = start_time + t

            # Get dynamic crop box for this timestamp
            crop_box = self.face_tracker.get_dynamic_crop_box_at_time(absolute_time)

            # Get the frame from the source clip
            frame = clip.get_frame(t)

            # Apply crop
            x1, y1 = crop_box.x, crop_box.y
            x2, y2 = crop_box.x + crop_box.width, crop_box.y + crop_box.height

            # Ensure crop coordinates are within bounds
            x1 = max(0, min(x1, original_width))
            y1 = max(0, min(y1, original_height))
            x2 = max(0, min(x2, original_width))
            y2 = max(0, min(y2, original_height))

            # Crop the frame
            cropped_frame = frame[y1:y2, x1:x2]

            # Resize to target resolution using cv2 for better performance
            import cv2
            resized_frame = cv2.resize(cropped_frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)

            return resized_frame

        # Import VideoClip for creating custom clip
        from moviepy import VideoClip

        # Create new clip with dynamic cropping
        dynamic_clip = VideoClip(frame_function=make_frame, duration=clip.duration)

        # Preserve audio from original clip
        if hasattr(clip, 'audio') and clip.audio is not None:
            dynamic_clip = dynamic_clip.with_audio(clip.audio)

        # Set fps to match original
        dynamic_clip.fps = clip.fps

        return dynamic_clip

    def apply_crossfade_transition(
        self,
        clip1: VideoFileClip,
        clip2: VideoFileClip,
        duration: float = 0.5
    ) -> VideoFileClip:
        """
        Apply crossfade transition between two clips.

        Args:
            clip1: First clip (will fade out)
            clip2: Second clip (will fade in)
            duration: Transition duration in seconds

        Returns:
            Concatenated clip with crossfade transition
        """
        if duration <= 0 or duration >= min(clip1.duration, clip2.duration):
            # No transition, just concatenate
            return concatenate_videoclips([clip1, clip2], method="compose")

        # Split clips at transition point
        clip1_main = clip1.subclipped(0, clip1.duration - duration)
        clip1_fade = clip1.subclipped(clip1.duration - duration, clip1.duration)
        clip2_fade = clip2.subclipped(0, duration)
        clip2_main = clip2.subclipped(duration, clip2.duration)

        # Apply fade effects
        clip1_fade = clip1_fade.with_effects([vfx.FadeOut(duration)])
        clip2_fade = clip2_fade.with_effects([vfx.FadeIn(duration)])

        # Composite the fade region
        fade_composite = CompositeVideoClip([clip1_fade, clip2_fade])

        # IMPORTANT: Handle audio crossfade with proper mixing
        # Mix audio from both clips during transition with volume ramping
        if hasattr(clip1_fade, 'audio') and clip1_fade.audio is not None:
            if hasattr(clip2_fade, 'audio') and clip2_fade.audio is not None:
                # Both have audio - perform proper crossfade mixing
                # Import audio effects
                from moviepy import afx, CompositeAudioClip

                # Fade out clip1 audio and fade in clip2 audio
                audio1_fadeout = clip1_fade.audio.with_effects([afx.AudioFadeOut(duration)])
                audio2_fadein = clip2_fade.audio.with_effects([afx.AudioFadeIn(duration)])

                # Mix both audio streams
                mixed_audio = CompositeAudioClip([audio1_fadeout, audio2_fadein])
                fade_composite = fade_composite.with_audio(mixed_audio)
            else:
                # Only clip1 has audio
                fade_composite = fade_composite.with_audio(clip1_fade.audio)
        elif hasattr(clip2_fade, 'audio') and clip2_fade.audio is not None:
            # Only clip2 has audio
            fade_composite = fade_composite.with_audio(clip2_fade.audio)

        # Concatenate: main1 + fade + main2
        segments = [clip1_main, fade_composite, clip2_main]
        # Filter out zero-duration clips
        segments = [s for s in segments if s.duration > 0]

        # Ensure all segments have audio for proper concatenation
        result = concatenate_videoclips(segments, method="compose")

        # Verify audio is preserved
        if result.audio is None:
            logger.warning("Crossfade concatenation lost audio, attempting recovery")
            # Check if original clips had audio
            if hasattr(clip1, 'audio') and clip1.audio is not None:
                logger.info("Restoring audio from source clips")
                # Use audio from full original clips
                audio_clips = []
                if hasattr(clip1, 'audio') and clip1.audio is not None:
                    audio_clips.append(clip1.audio)
                if hasattr(clip2, 'audio') and clip2.audio is not None:
                    audio_clips.append(clip2.audio.with_start(clip1.duration))
                if audio_clips:
                    from moviepy import CompositeAudioClip
                    result = result.with_audio(CompositeAudioClip(audio_clips))

        return result

    def generate_mixed_mode_clip(
        self,
        video: VideoFileClip,
        viral_moment: ViralMoment,
        word_timings: List[Dict[str, Any]],
        content_segments: List[ContentSegment]
    ) -> VideoFileClip:
        """
        Generate clip with mixed content modes (face-tracked + horizontal).

        Args:
            video: Source video clip (already loaded)
            viral_moment: ViralMoment defining overall clip timing
            word_timings: Word timings for subtitles
            content_segments: List of ContentSegment defining mode timeline

        Returns:
            Composite video clip with mixed modes
        """
        logger.info(f"Generating mixed-mode clip with {len(content_segments)} segments")

        # Filter segments to those within viral moment timerange
        relevant_segments = [
            seg for seg in content_segments
            if seg.start_time < viral_moment.end_time and seg.end_time > viral_moment.start_time
        ]

        if not relevant_segments:
            logger.warning("No relevant segments found, using full face tracking")
            # Fallback to traditional face tracking
            return self._generate_traditional_clip(video, viral_moment, word_timings)

        logger.debug(f"Processing {len(relevant_segments)} content segments")

        # Process each segment
        segment_clips = []

        for i, segment in enumerate(relevant_segments):
            # Adjust segment times to be relative to viral moment
            seg_start = max(segment.start_time, viral_moment.start_time)
            seg_end = min(segment.end_time, viral_moment.end_time)

            if seg_start >= seg_end:
                continue

            logger.debug(f"Segment {i+1}: {seg_start:.1f}s-{seg_end:.1f}s [{segment.mode.value}]")

            # Extract segment
            segment_clip = video.subclipped(seg_start, seg_end)

            # Apply appropriate mode
            if segment.mode == ContentMode.HORIZONTAL:
                # Horizontal content mode - preserve aspect ratio with blurred bg
                processed = self.create_horizontal_content_clip(segment_clip)
            else:
                # Face tracking mode - crop to 9:16 with dynamic tracking
                processed = self.create_face_tracked_clip(segment_clip, seg_start)

            segment_clips.append(processed)

        # Concatenate segments with transitions
        if len(segment_clips) == 1:
            final_clip = segment_clips[0]
        else:
            # Apply crossfade transitions between mode changes
            clips_with_transitions = [segment_clips[0]]

            for i in range(1, len(segment_clips)):
                prev_mode = relevant_segments[i-1].mode
                curr_mode = relevant_segments[i].mode

                if prev_mode != curr_mode:
                    # Mode change - apply transition
                    logger.debug(f"Applying transition between {prev_mode.value} and {curr_mode.value}")
                    transition = self.apply_crossfade_transition(
                        clips_with_transitions[-1],
                        segment_clips[i],
                        self.transition_duration
                    )
                    # Replace last clip with transitioned version
                    clips_with_transitions[-1] = transition
                else:
                    # Same mode - just append
                    clips_with_transitions.append(segment_clips[i])

            if len(clips_with_transitions) == 1:
                final_clip = clips_with_transitions[0]
            else:
                # Validate all clips have audio before concatenation
                clips_without_audio = [
                    i for i, clip in enumerate(clips_with_transitions)
                    if not hasattr(clip, 'audio') or clip.audio is None
                ]
                if clips_without_audio:
                    logger.warning(f"Warning: {len(clips_without_audio)} clips missing audio before concatenation")

                # Use "compose" method to ensure audio is properly handled
                final_clip = concatenate_videoclips(clips_with_transitions, method="compose")

                # Verify audio was preserved
                if final_clip.audio is None:
                    logger.error("Concatenation lost audio! This should not happen.")

        return final_clip

    def _generate_traditional_clip(
        self,
        video: VideoFileClip,
        viral_moment: ViralMoment,
        word_timings: List[Dict[str, Any]]
    ) -> VideoFileClip:
        """
        Generate traditional face-tracked clip (fallback method).

        Args:
            video: Source video
            viral_moment: Timing information
            word_timings: Word timings for subtitles

        Returns:
            Processed clip
        """
        # Extract segment
        clip = video.subclipped(viral_moment.start_time, viral_moment.end_time)

        # Apply dynamic face-tracked crop and resize
        clip = self.create_face_tracked_clip(clip, viral_moment.start_time)

        return clip

    def generate_clip(
        self,
        video_path: str,
        viral_moment: ViralMoment,
        word_timings: List[Dict[str, Any]],
        job_id: str
    ) -> Optional[GeneratedClip]:
        """
        Generate a single viral clip with optional mixed-mode support.

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

            # Load video
            logger.debug(f"Loading video: {video_path}")
            video = VideoFileClip(video_path)

            # Validate timing
            if viral_moment.end_time > video.duration:
                logger.warning(f"Clip end time {viral_moment.end_time}s exceeds video duration {video.duration}s, adjusting")
                viral_moment.end_time = video.duration

            # Check if mixed-mode is enabled and analyze content modes
            content_segments = None
            if self.enable_mixed_mode and self.content_mode_detector:
                logger.debug("Analyzing content modes for mixed-mode generation")
                try:
                    content_segments = self.content_mode_detector.analyze_video_segments(
                        video_path,
                        self.face_tracker.face_positions,
                        video.fps,
                        viral_moment.start_time,
                        viral_moment.end_time
                    )
                except Exception as e:
                    logger.warning(f"Content mode detection failed: {e}, falling back to face tracking")
                    content_segments = None

            # Generate clip based on mode
            if content_segments and len(content_segments) > 0:
                # Mixed-mode generation
                logger.info("Using mixed-mode generation (face + horizontal content)")
                clip = self.generate_mixed_mode_clip(
                    video,
                    viral_moment,
                    word_timings,
                    content_segments
                )
            else:
                # Traditional face-tracking generation
                logger.info("Using traditional face-tracking mode")
                clip = self._generate_traditional_clip(video, viral_moment, word_timings)

            # Get face coverage percentage for metadata
            face_coverage = self.face_tracker.get_face_coverage_percentage(
                viral_moment.start_time,
                viral_moment.end_time
            )

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

            # Add keyframe parameters to prevent freezing
            # Force keyframes every 1 second (30 frames at 30fps) for consistent playback
            keyframe_params = [
                '-g', '30',           # GOP size: keyframe every 30 frames (1 second)
                '-keyint_min', '30',  # Minimum keyframe interval
                '-sc_threshold', '0'  # Disable scene detection for consistent keyframes
            ]

            # Merge codec params with keyframe params
            ffmpeg_params = codec_settings.get('ffmpeg_params', []) + keyframe_params

            try:
                # Attempt export with optimal codec settings
                clip.write_videofile(
                    str(output_path),
                    codec=codec_settings['codec'],
                    audio_codec="aac",
                    fps=30,
                    ffmpeg_params=ffmpeg_params,
                    threads=4,
                    logger=None  # Disable MoviePy's verbose logging
                )
            except Exception as e:
                # If hardware encoding fails, fall back to software encoding
                if codec_settings['codec'] != 'libx264':
                    logger.warning(f"Hardware encoding failed ({e}), falling back to CPU encoding")
                    fallback_settings = get_video_codec_settings(use_gpu=False)
                    # Add keyframe params to fallback as well
                    fallback_ffmpeg_params = fallback_settings.get('ffmpeg_params', []) + keyframe_params
                    clip.write_videofile(
                        str(output_path),
                        codec=fallback_settings['codec'],
                        audio_codec="aac",
                        fps=30,
                        ffmpeg_params=fallback_ffmpeg_params,
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
