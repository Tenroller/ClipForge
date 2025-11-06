"""
Traditional closed caption subtitle generator for podcast clips.

Generates professional-style subtitles with word-level timing from Whisper transcription.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from moviepy import TextClip, CompositeVideoClip, VideoClip
from dataclasses import dataclass

# Add parent directory to path to import font_detection
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from font_detection import get_font_fallback_list

logger = logging.getLogger(__name__)


@dataclass
class SubtitleSegment:
    """A subtitle segment with timing and text."""
    text: str
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        """Duration of segment in seconds."""
        return self.end_time - self.start_time


class SubtitleGenerator:
    """
    Generate traditional closed caption subtitles for video clips.

    Uses word-level timing data from Whisper to create professional-looking
    subtitles that appear in chunks (multiple words) for readability.
    """

    def __init__(
        self,
        font_size: int = 40,
        color: str = "#FFFFFF",
        stroke_color: str = "#000000",
        stroke_width: int = 2,
        position: str = "bottom"
    ):
        """
        Initialize subtitle generator.

        Args:
            font_size: Font size in points
            color: Text color (hex format)
            stroke_color: Stroke/outline color (hex format)
            stroke_width: Stroke width in pixels
            position: Subtitle position ("top", "center", "bottom")
        """
        self.font_size = font_size
        self.color = color
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.position = position

        # Position mapping
        self.position_map = {
            "top": ("center", 100),
            "center": ("center", "center"),
            "bottom": ("center", 100)  # 100 pixels from bottom
        }

    def create_subtitle_segments(
        self,
        word_timings: List[Dict[str, Any]],
        max_words_per_segment: int = 5,
        max_chars_per_segment: int = 50
    ) -> List[SubtitleSegment]:
        """
        Convert word-level timings to subtitle segments.

        Groups words into readable chunks based on timing and character limits.

        Args:
            word_timings: List of word timing dicts from Whisper
                          Each dict: {word, start_time, end_time, confidence}
            max_words_per_segment: Maximum words per subtitle line
            max_chars_per_segment: Maximum characters per subtitle line

        Returns:
            List of subtitle segments
        """
        if not word_timings:
            logger.warning("No word timings provided, cannot generate subtitles")
            return []

        segments = []
        current_words = []
        current_chars = 0
        segment_start = None

        for word_data in word_timings:
            word = word_data.get('word', '').strip()
            start_time = word_data.get('start_time', 0)
            end_time = word_data.get('end_time', 0)

            if not word:
                continue

            # Initialize segment start time
            if segment_start is None:
                segment_start = start_time

            word_len = len(word)

            # Check if adding this word would exceed limits
            would_exceed_words = len(current_words) >= max_words_per_segment
            would_exceed_chars = current_chars + word_len + 1 > max_chars_per_segment  # +1 for space

            # If this word would exceed limits, finalize current segment
            if current_words and (would_exceed_words or would_exceed_chars):
                segment_text = ' '.join(current_words)
                segments.append(SubtitleSegment(
                    text=segment_text,
                    start_time=segment_start,
                    end_time=word_data.get('start_time', 0)  # End at start of next word
                ))

                # Reset for next segment
                current_words = []
                current_chars = 0
                segment_start = start_time

            # Add word to current segment
            current_words.append(word)
            current_chars += word_len + 1  # +1 for space

        # Add final segment
        if current_words:
            segment_text = ' '.join(current_words)
            last_word = word_timings[-1]
            segments.append(SubtitleSegment(
                text=segment_text,
                start_time=segment_start,
                end_time=last_word.get('end_time', segment_start + 2.0)
            ))

        logger.info(f"Created {len(segments)} subtitle segments from {len(word_timings)} words")
        return segments

    def generate_subtitle_clips(
        self,
        segments: List[SubtitleSegment],
        video_size: Tuple[int, int],
        video_duration: float
    ) -> List[TextClip]:
        """
        Generate MoviePy TextClip objects for each subtitle segment.

        Args:
            segments: List of subtitle segments
            video_size: (width, height) of video
            video_duration: Total video duration in seconds

        Returns:
            List of TextClip objects with proper timing
        """
        video_width, video_height = video_size
        subtitle_clips = []

        # Calculate vertical position
        if self.position == "top":
            y_pos = 100
        elif self.position == "center":
            y_pos = video_height // 2
        else:  # bottom
            y_pos = video_height - 150  # 150px from bottom

        # Get font fallback list once for all segments
        font_choices = get_font_fallback_list()

        for segment in segments:
            txt_clip = None

            # Try each font in fallback list until one works
            for font_choice in font_choices:
                try:
                    # Create text clip with stroke
                    txt_clip = TextClip(
                        text=segment.text,
                        font_size=self.font_size,
                        color=self.color,
                        stroke_color=self.stroke_color,
                        stroke_width=self.stroke_width,
                        font=font_choice,
                        method='caption',
                        size=(video_width - 100, None),  # 50px padding on each side
                        text_align='center'
                    )

                    # Verify the clip was created successfully
                    if txt_clip and txt_clip.w > 0 and txt_clip.h > 0:
                        break  # Success! Use this font
                    else:
                        txt_clip = None

                except Exception as e:
                    logger.debug(f"Font '{font_choice}' failed for '{segment.text[:20]}...': {e}")
                    txt_clip = None
                    continue

            # If we successfully created a text clip, add timing and position
            if txt_clip:
                try:
                    # Set timing
                    txt_clip = txt_clip.with_start(segment.start_time)
                    txt_clip = txt_clip.with_duration(segment.duration)
                    txt_clip = txt_clip.with_position(('center', y_pos))

                    subtitle_clips.append(txt_clip)

                except Exception as e:
                    logger.error(f"Failed to set timing/position for subtitle '{segment.text}': {e}")
                    continue
            else:
                logger.error(f"Failed to create subtitle clip for '{segment.text}': All fonts failed")
                continue

        logger.info(f"Generated {len(subtitle_clips)} subtitle clips")
        return subtitle_clips

    def add_subtitles_to_video(
        self,
        video_clip: VideoClip,
        word_timings: List[Dict[str, Any]],
        clip_start_time: float = 0.0
    ) -> CompositeVideoClip:
        """
        Add subtitles to a video clip.

        Args:
            video_clip: MoviePy VideoClip to add subtitles to
            word_timings: List of word timing dicts from Whisper
            clip_start_time: Start time of this clip in original video (for timing adjustment)

        Returns:
            CompositeVideoClip with subtitles overlaid
        """
        # Adjust word timings relative to clip start
        adjusted_timings = []
        for word_data in word_timings:
            if word_data.get('start_time', 0) < clip_start_time:
                continue  # Skip words before clip start

            adjusted_word = word_data.copy()
            adjusted_word['start_time'] -= clip_start_time
            adjusted_word['end_time'] -= clip_start_time

            # Only include words within clip duration
            if adjusted_word['start_time'] < video_clip.duration:
                adjusted_timings.append(adjusted_word)

        if not adjusted_timings:
            logger.warning("No word timings within clip duration, returning video without subtitles")
            return video_clip

        # Create subtitle segments
        segments = self.create_subtitle_segments(adjusted_timings)

        # Generate subtitle clips
        video_size = (video_clip.w, video_clip.h)
        subtitle_clips = self.generate_subtitle_clips(
            segments,
            video_size,
            video_clip.duration
        )

        # Composite video with subtitles
        if subtitle_clips:
            final_clip = CompositeVideoClip([video_clip] + subtitle_clips)

            # IMPORTANT: Preserve audio from original video clip
            # CompositeVideoClip doesn't automatically inherit audio from the first clip
            if hasattr(video_clip, 'audio') and video_clip.audio is not None:
                final_clip = final_clip.with_audio(video_clip.audio)
                logger.debug("Preserved audio from original video clip")
            else:
                logger.warning("Original video has no audio track")

            logger.info(f"Added {len(subtitle_clips)} subtitle segments to video")
        else:
            logger.warning("No subtitle clips generated, returning original video")
            final_clip = video_clip

        return final_clip

    def extract_words_for_timerange(
        self,
        word_timings: List[Dict[str, Any]],
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """
        Extract word timings for a specific time range.

        Args:
            word_timings: Full list of word timings
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Filtered list of word timings within the range
        """
        filtered = [
            word for word in word_timings
            if start_time <= word.get('start_time', 0) <= end_time
        ]

        logger.debug(f"Extracted {len(filtered)} words for timerange {start_time:.1f}s-{end_time:.1f}s")
        return filtered
