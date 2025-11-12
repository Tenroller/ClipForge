"""
Traditional closed caption subtitle generator for podcast clips.

Generates professional-style subtitles with word-level timing from Whisper transcription.
Supports karaoke-style highlighting with rounded background boxes.
"""

from loguru import logger as loguru_logger
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from moviepy import TextClip, CompositeVideoClip, VideoClip, ImageClip
from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageDraw

# Add parent directory to path to import font_detection
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from font_detection import get_font_fallback_list

logger = loguru_logger.bind(name="PodcastClips.subtitle_generator")


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
        font_size: int = 70,
        color: str = "#FFFFFF",
        stroke_color: str = "#000000",
        stroke_width: int = 3,
        position: str = "bottom",
        vertical_offset: int = 300,
        highlight_color: str = "#FFEB3B",
        max_words_visible: int = 5
    ):
        """
        Initialize subtitle generator.

        Args:
            font_size: Font size in points
            color: Text color (hex format)
            stroke_color: Stroke/outline color (hex format)
            stroke_width: Stroke width in pixels
            position: Subtitle position ("top", "center", "bottom")
            vertical_offset: Distance from bottom in pixels (for karaoke mode)
            highlight_color: Background box color for highlighted word (hex format)
            max_words_visible: Maximum words visible at once (karaoke window)
        """
        self.font_size = font_size
        self.color = color
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.position = position
        self.vertical_offset = vertical_offset
        self.highlight_color = highlight_color
        self.max_words_visible = max_words_visible

        # Position mapping
        self.position_map = {
            "top": ("center", 100),
            "center": ("center", "center"),
            "bottom": ("center", 100)  # 100 pixels from bottom
        }

    def create_rounded_rectangle(
        self,
        width: int,
        height: int,
        radius: int = 15,
        color: str = "#6366f1"
    ) -> ImageClip:
        """
        Create a rounded rectangle background clip using PIL.

        Args:
            width: Width of rectangle in pixels
            height: Height of rectangle in pixels
            radius: Corner radius in pixels
            color: Fill color (hex format)

        Returns:
            ImageClip with rounded rectangle
        """
        # Convert hex color to RGB
        color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

        # Create image with transparency
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle
        draw.rounded_rectangle(
            [(0, 0), (width, height)],
            radius=radius,
            fill=color_rgb + (255,)  # Add alpha channel (fully opaque)
        )

        # Convert PIL image to numpy array for MoviePy
        img_array = np.array(img)

        # Create ImageClip from array
        return ImageClip(img_array, duration=1, is_mask=False)

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

    def generate_karaoke_subtitle_clips(
        self,
        word_timings: List[Dict[str, Any]],
        video_size: Tuple[int, int],
        video_duration: float
    ) -> List[CompositeVideoClip]:
        """
        Generate karaoke-style subtitle clips with word-by-word highlighting.

        Creates a sliding window of words where the current word is highlighted
        with a rounded background box, and surrounding words are shown in plain text.

        Args:
            word_timings: List of word timing dicts from Whisper
            video_size: (width, height) of video
            video_duration: Total video duration in seconds

        Returns:
            List of CompositeVideoClip objects with highlighted words
        """
        if not word_timings:
            return []

        video_width, video_height = video_size
        subtitle_clips = []

        # Calculate vertical position using vertical_offset
        # Add 20% extra space for descenders and text rendering margins
        safety_margin = int(self.font_size * 0.2)
        y_pos = video_height - self.vertical_offset - safety_margin

        # Get font fallback list once
        font_choices = get_font_fallback_list()

        # Process each word as the "current" highlighted word
        for i, current_word_data in enumerate(word_timings):
            current_word = current_word_data.get('word', '').strip()
            if not current_word:
                continue

            start_time = current_word_data.get('start_time', 0)
            end_time = current_word_data.get('end_time', start_time + 0.5)
            duration = end_time - start_time

            # Determine window of visible words (current word + context)
            window_start = max(0, i - self.max_words_visible // 2)
            window_end = min(len(word_timings), window_start + self.max_words_visible)

            # Adjust window if we're near the end
            if window_end - window_start < self.max_words_visible:
                window_start = max(0, window_end - self.max_words_visible)

            visible_words = word_timings[window_start:window_end]

            # Create text clips for all visible words
            word_clips = []
            current_word_clip = None
            current_word_index = i - window_start

            for j, word_data in enumerate(visible_words):
                word = word_data.get('word', '').strip()
                if not word:
                    continue

                is_current = (j == current_word_index)

                # Try fonts until one works
                txt_clip = None
                for font_choice in font_choices:
                    try:
                        # For current word, create without stroke to go on top of background
                        # For other words, use normal stroke
                        txt_clip = TextClip(
                            text=word,
                            font_size=self.font_size,
                            color=self.color,
                            stroke_color=self.stroke_color if not is_current else None,
                            stroke_width=self.stroke_width if not is_current else 0,
                            font=font_choice
                        )

                        if txt_clip and txt_clip.w > 0 and txt_clip.h > 0:
                            break
                        else:
                            txt_clip = None

                    except Exception as e:
                        logger.warning(f"Font '{font_choice}' failed for word '{word}': {e}")
                        txt_clip = None
                        continue

                if txt_clip:
                    word_clips.append({
                        'clip': txt_clip,
                        'word': word,
                        'is_current': is_current,
                        'index': j
                    })

                    if is_current:
                        current_word_clip = txt_clip

            if not word_clips:
                logger.error(f"Failed to create any text clips for word '{current_word}' - all fonts failed")
                continue

            # Calculate horizontal layout for all words
            total_width = sum(clip_data['clip'].w for clip_data in word_clips)
            spacing = 30  # Space between words
            total_width_with_spacing = total_width + spacing * (len(word_clips) - 1)

            # Start x position (centered)
            start_x = (video_width - total_width_with_spacing) // 2
            current_x = start_x

            # Position each word clip
            positioned_clips = []
            highlighted_clip_info = None

            for clip_data in word_clips:
                clip = clip_data['clip']
                is_current = clip_data['is_current']

                # Set position for this word
                word_pos = (current_x, y_pos)
                positioned_clip = clip.with_position(word_pos)

                if is_current:
                    # Save info for creating background box
                    highlighted_clip_info = {
                        'x': current_x,
                        'y': y_pos,
                        'width': clip.w,
                        'height': clip.h
                    }

                positioned_clips.append(positioned_clip)
                current_x += clip.w + spacing

            # Create rounded background box for current word
            if highlighted_clip_info and current_word_clip:
                # Make padding proportional to font size for better scaling
                padding_x = max(40, int(self.font_size * 0.5))  # 50% of font size, minimum 40px
                padding_y = max(20, int(self.font_size * 0.3))  # 30% of font size, minimum 20px
                box_width = highlighted_clip_info['width'] + 2 * padding_x
                box_height = highlighted_clip_info['height'] + 2 * padding_y

                bg_box = self.create_rounded_rectangle(
                    width=box_width,
                    height=box_height,
                    radius=25,
                    color=self.highlight_color
                )

                # Position background box (accounting for padding)
                box_x = highlighted_clip_info['x'] - padding_x
                box_y = highlighted_clip_info['y'] - padding_y
                bg_box = bg_box.with_position((box_x, box_y))

                # Composite: background box first, then all text clips
                # Create composite with proper layering
                composite_clips = [bg_box] + positioned_clips

                try:
                    composite = CompositeVideoClip(composite_clips, size=video_size)
                    composite = composite.with_start(start_time)
                    composite = composite.with_duration(duration)

                    subtitle_clips.append(composite)

                except Exception as e:
                    logger.error(f"Failed to create composite for word '{current_word}': {e}")
                    continue

        logger.info(f"Generated {len(subtitle_clips)} karaoke subtitle clips")
        return subtitle_clips

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
        clip_start_time: float = 0.0,
        use_karaoke_style: bool = True
    ) -> CompositeVideoClip:
        """
        Add subtitles to a video clip.

        Args:
            video_clip: MoviePy VideoClip to add subtitles to
            word_timings: List of word timing dicts from Whisper
            clip_start_time: Start time of this clip in original video (for timing adjustment)
            use_karaoke_style: Use karaoke-style highlighting (default: True)

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

        # Generate subtitle clips based on style preference
        video_size = (video_clip.w, video_clip.h)

        if use_karaoke_style:
            # Use new karaoke-style subtitle generation
            subtitle_clips = self.generate_karaoke_subtitle_clips(
                adjusted_timings,
                video_size,
                video_clip.duration
            )
        else:
            # Use traditional segment-based subtitles
            segments = self.create_subtitle_segments(adjusted_timings)
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

            logger.info(f"Added {len(subtitle_clips)} karaoke subtitle clips to video" if use_karaoke_style else f"Added {len(subtitle_clips)} subtitle segments to video")
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
