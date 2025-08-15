"""
TikTok-style subtitle generation with word-by-word highlighting.

This module provides enhanced subtitle functionality with:
- Word-by-word highlighting (karaoke effect)
- Customizable fonts, colors, and sizes
- Multiple subtitle styles and animations
"""

import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
import json


@dataclass
class SubtitleStyle:
    """Configuration for subtitle styling."""
    # Font settings
    font_family: str = "Arial-Bold"
    font_size: int = 48
    
    # Colors
    default_color: str = "#FFFFFF"  # White for unspoken words
    highlight_color: str = "#FFFF00"  # Yellow for currently spoken word
    stroke_color: str = "#000000"  # Black outline
    background_color: str = "#000000"  # Black background
    
    # Effects
    stroke_width: int = 2
    background_opacity: float = 0.4
    padding_x: int = 12
    padding_y: int = 8
    
    # Animation
    highlight_duration: float = 0.1  # Fade time for word highlighting
    
    # Position
    position: str = "center,bottom"  # Grid position or pct:x,y or px:x,y


@dataclass
class WordTiming:
    """Timing information for a single word."""
    word: str
    start_time: float
    end_time: float
    sentence_index: int


def extract_word_timings(sentences: List[str], audio_clips: List[Any]) -> List[WordTiming]:
    """
    Extract word-level timing information from sentences and audio clips.
    
    This is a simplified implementation that estimates word timings based on
    sentence duration and word count. For more accurate timings, you could
    integrate with speech recognition APIs that provide word-level timestamps.
    
    Args:
        sentences: List of sentences from the script
        audio_clips: List of audio clips corresponding to sentences
        
    Returns:
        List of WordTiming objects with word-level timing information
    """
    word_timings = []
    current_time = 0.0
    
    for sentence_idx, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips)):
        sentence_duration = audio_clip.duration
        
        # Clean and split sentence into words
        words = re.findall(r'\b\w+\b', sentence.lower())
        if not words:
            current_time += sentence_duration
            continue
            
        # Estimate word duration (simplified approach)
        word_duration = sentence_duration / len(words)
        
        for word in words:
            word_start = current_time
            word_end = current_time + word_duration
            
            word_timings.append(WordTiming(
                word=word,
                start_time=word_start,
                end_time=word_end,
                sentence_index=sentence_idx
            ))
            
            current_time = word_end
    
    return word_timings


def create_word_highlight_clip(
    sentences: List[str], 
    word_timings: List[WordTiming], 
    video_duration: float,
    style: SubtitleStyle,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create a video clip with TikTok-style word highlighting.
    
    Args:
        sentences: List of sentences from the script
        word_timings: Word-level timing information
        video_duration: Total duration of the video
        style: Subtitle styling configuration
        video_size: (width, height) of the video
        
    Returns:
        CompositeVideoClip with highlighted subtitles
    """
    video_width, video_height = video_size
    clips = []
    
    # Group words by sentence for display
    sentence_groups = {}
    for timing in word_timings:
        if timing.sentence_index not in sentence_groups:
            sentence_groups[timing.sentence_index] = []
        sentence_groups[timing.sentence_index].append(timing)
    
    # Create clips for each sentence
    for sentence_idx, sentence in enumerate(sentences):
        if sentence_idx not in sentence_groups:
            continue
            
        sentence_words = sentence_groups[sentence_idx]
        if not sentence_words:
            continue
            
        sentence_start = min(word.start_time for word in sentence_words)
        sentence_end = max(word.end_time for word in sentence_words)
        sentence_duration = sentence_end - sentence_start
        
        # Create the sentence subtitle clip
        sentence_clip = create_sentence_clip(
            sentence=sentence,
            sentence_words=sentence_words,
            sentence_start=sentence_start,
            sentence_duration=sentence_duration,
            style=style,
            video_size=video_size
        )
        
        clips.append(sentence_clip)
    
    if not clips:
        # Return empty clip if no subtitles
        return CompositeVideoClip([])
    
    return CompositeVideoClip(clips)


def create_sentence_clip(
    sentence: str,
    sentence_words: List[WordTiming],
    sentence_start: float,
    sentence_duration: float,
    style: SubtitleStyle,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create a clip for a single sentence with word highlighting.
    
    Args:
        sentence: The sentence text
        sentence_words: Word timing information for this sentence
        sentence_start: Start time of the sentence
        sentence_duration: Duration of the sentence
        style: Subtitle styling configuration
        video_size: (width, height) of the video
        
    Returns:
        CompositeVideoClip for the sentence
    """
    video_width, video_height = video_size
    
    def make_frame(t):
        """Generate frame at time t with appropriate word highlighting."""
        absolute_time = sentence_start + t
        
        # Find which word should be highlighted at this time
        highlighted_word_idx = None
        for idx, word_timing in enumerate(sentence_words):
            if word_timing.start_time <= absolute_time <= word_timing.end_time:
                highlighted_word_idx = idx
                break
        
        # Build the text with highlighting
        words = re.findall(r'\b\w+\b', sentence)
        highlighted_text = ""
        
        for idx, word in enumerate(words):
            if idx == highlighted_word_idx:
                # This word is currently being spoken - highlight it
                highlighted_text += f"<span style='color:{style.highlight_color}'>{word}</span> "
            else:
                # This word is not being spoken - use default color
                highlighted_text += f"<span style='color:{style.default_color}'>{word}</span> "
        
        return highlighted_text.strip()
    
    # Create text clip with dynamic content
    def text_generator(t):
        """Generate text clip for time t."""
        absolute_time = sentence_start + t
        
        # Determine which word is highlighted
        highlighted_words = []
        default_words = []
        
        words = re.findall(r'\b\w+\b', sentence)
        for idx, word in enumerate(words):
            # Check if this word should be highlighted
            is_highlighted = False
            for word_timing in sentence_words:
                if (word_timing.word.lower() == word.lower() and 
                    word_timing.start_time <= absolute_time <= word_timing.end_time):
                    is_highlighted = True
                    break
            
            if is_highlighted:
                highlighted_words.append((word, idx))
            else:
                default_words.append((word, idx))
        
        # Create the full sentence with appropriate colors
        full_text = sentence
        
        # Create TextClip with the sentence
        try:
            # Calculate font size relative to video height
            font_size = max(24, int(video_height * 0.025))
            max_text_width = int(video_width * 0.85)
            
            # For now, create a simple text clip
            # TODO: Implement actual word-by-word highlighting using MoviePy
            # This is a simplified version that shows the concept
            
            # Find which word should be highlighted
            current_color = style.default_color
            for word_timing in sentence_words:
                if word_timing.start_time <= absolute_time <= word_timing.end_time:
                    current_color = style.highlight_color
                    break
            
            text_clip = TextClip(
                text=sentence,
                font_size=font_size,
                color=current_color,
                stroke_color=style.stroke_color,
                stroke_width=style.stroke_width,
                font=style.font_family,
                method='caption',
                size=(max_text_width, None),
            )
            
            return text_clip
            
        except Exception as e:
            print(f"Error creating text clip: {e}")
            # Fallback to simple text
            return TextClip(
                text=sentence,
                font_size=48,
                color=style.default_color,
                size=(int(video_width * 0.85), None),
            )
    
    # Create the subtitle clip with timing
    subtitle_clip = CompositeVideoClip([])
    
    # For now, use a simpler approach with color changes
    # We'll create multiple text clips with different colors and timing
    clips = []
    
    # Create background
    try:
        # Estimate text dimensions
        temp_text = TextClip(
            text=sentence,
            font_size=max(24, int(video_height * 0.025)),
            color=style.default_color,
            font=style.font_family,
            method='caption',
            size=(int(video_width * 0.85), None),
        )
        
        bg_w = temp_text.w + 2 * style.padding_x
        bg_h = temp_text.h + 2 * style.padding_y
        
        bg_clip = ColorClip(
            size=(bg_w, bg_h),
            color=tuple(int(style.background_color[i:i+2], 16) for i in (1, 3, 5))
        ).with_opacity(style.background_opacity).with_duration(sentence_duration)
        
        clips.append(bg_clip)
        
        # Position text over background
        positioned_text = temp_text.with_position((style.padding_x, style.padding_y)).with_duration(sentence_duration)
        clips.append(positioned_text)
        
    except Exception as e:
        print(f"Error creating background clip: {e}")
        # Fallback without background
        simple_text = TextClip(
            text=sentence,
            font_size=48,
            color=style.default_color,
            size=(int(video_width * 0.85), None),
        ).with_duration(sentence_duration)
        clips.append(simple_text)
    
    if clips:
        sentence_clip = CompositeVideoClip(clips).with_start(sentence_start)
        
        # Position the sentence clip
        positioned_clip = position_subtitle_clip(sentence_clip, style.position, video_size)
        return positioned_clip
    
    return CompositeVideoClip([])


def position_subtitle_clip(clip: CompositeVideoClip, position: str, video_size: Tuple[int, int]) -> CompositeVideoClip:
    """
    Position the subtitle clip according to the specified position.
    
    Args:
        clip: The subtitle clip to position
        position: Position string (grid, pct:x,y, or px:x,y format)
        video_size: (width, height) of the video
        
    Returns:
        Positioned clip
    """
    video_width, video_height = video_size
    
    # Parse position
    pos_mode = 'grid'
    pct_xy = (50.0, 85.0)  # Default: center, bottom
    px_xy = (0, 0)
    
    try:
        raw_pos = position.strip().lower()
        
        if raw_pos.startswith('pct:'):
            pos_mode = 'pct'
            match = re.match(r"pct:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)", raw_pos)
            if match:
                pct_xy = (
                    max(0.0, min(100.0, float(match.group(1)))),
                    max(0.0, min(100.0, float(match.group(2))))
                )
        elif raw_pos.startswith('px:'):
            pos_mode = 'px'
            match = re.match(r"px:\s*([0-9]+)\s*,\s*([0-9]+)", raw_pos)
            if match:
                px_xy = (max(0, int(match.group(1))), max(0, int(match.group(2))))
        else:
            # Grid positioning
            parts = [p.strip().lower() for p in raw_pos.split(',')]
            horizontal = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom') else 'bottom'
            
            # Convert grid to percentage
            h_pct = {'left': 10.0, 'center': 50.0, 'right': 90.0}[horizontal]
            v_pct = {'top': 15.0, 'center': 50.0, 'bottom': 85.0}[vertical]
            pct_xy = (h_pct, v_pct)
            pos_mode = 'pct'
    
    except Exception:
        pos_mode = 'pct'
        pct_xy = (50.0, 85.0)  # Default: center, bottom
    
    # Calculate position
    if pos_mode == 'pct':
        # Percentage positioning (center of subtitle)
        clip_w = getattr(clip, 'w', 0) or 0
        clip_h = getattr(clip, 'h', 0) or 0
        
        center_x = int((pct_xy[0] / 100.0) * video_width)
        center_y = int((pct_xy[1] / 100.0) * video_height)
        
        left = max(0, min(center_x - clip_w // 2, video_width - clip_w))
        top = max(0, min(center_y - clip_h // 2, video_height - clip_h))
        
        return clip.with_position((left, top))
    
    elif pos_mode == 'px':
        # Pixel positioning (top-left of subtitle)
        clip_w = getattr(clip, 'w', 0) or 0
        clip_h = getattr(clip, 'h', 0) or 0
        
        left = max(0, min(px_xy[0], video_width - clip_w))
        top = max(0, min(px_xy[1], video_height - clip_h))
        
        return clip.with_position((left, top))
    
    # Default center-bottom positioning
    return clip.with_position(('center', 'bottom'))


def generate_tiktok_subtitles(
    audio_path: str,
    sentences: List[str],
    audio_clips: List[Any],
    style: Optional[SubtitleStyle] = None,
    video_size: Tuple[int, int] = (1080, 1920)
) -> str:
    """
    Generate TikTok-style subtitles with word highlighting.
    
    Args:
        audio_path: Path to the audio file
        sentences: List of sentences from the script
        audio_clips: List of audio clips corresponding to sentences
        style: Subtitle styling configuration
        video_size: (width, height) of the video
        
    Returns:
        Path to the generated subtitle file (JSON format with timing data)
    """
    if style is None:
        style = SubtitleStyle()
    
    # Extract word-level timings
    word_timings = extract_word_timings(sentences, audio_clips)
    
    # Create subtitle data structure
    subtitle_data = {
        "style": {
            "font_family": style.font_family,
            "font_size": style.font_size,
            "default_color": style.default_color,
            "highlight_color": style.highlight_color,
            "stroke_color": style.stroke_color,
            "background_color": style.background_color,
            "stroke_width": style.stroke_width,
            "background_opacity": style.background_opacity,
            "padding_x": style.padding_x,
            "padding_y": style.padding_y,
            "position": style.position
        },
        "sentences": [],
        "word_timings": []
    }
    
    # Add sentence data
    for idx, sentence in enumerate(sentences):
        sentence_words = [wt for wt in word_timings if wt.sentence_index == idx]
        if sentence_words:
            subtitle_data["sentences"].append({
                "text": sentence,
                "index": idx,
                "start_time": min(wt.start_time for wt in sentence_words),
                "end_time": max(wt.end_time for wt in sentence_words)
            })
    
    # Add word timing data
    for word_timing in word_timings:
        subtitle_data["word_timings"].append({
            "word": word_timing.word,
            "start_time": word_timing.start_time,
            "end_time": word_timing.end_time,
            "sentence_index": word_timing.sentence_index
        })
    
    # Save subtitle data
    subtitle_path = f"../subtitles/{uuid.uuid4()}_tiktok.json"
    
    # Ensure subtitles directory exists
    Path(subtitle_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(subtitle_path, "w", encoding="utf-8") as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"TikTok-style subtitle data saved to: {subtitle_path}")
    return subtitle_path


def load_tiktok_subtitle_data(subtitle_path: str) -> Dict[str, Any]:
    """
    Load TikTok subtitle data from JSON file.
    
    Args:
        subtitle_path: Path to the subtitle JSON file
        
    Returns:
        Dictionary containing subtitle data
    """
    with open(subtitle_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_tiktok_subtitle_clip(
    subtitle_path: str,
    video_size: Tuple[int, int],
    video_duration: float
) -> CompositeVideoClip:
    """
    Create a TikTok-style subtitle clip from saved subtitle data.
    
    Args:
        subtitle_path: Path to the subtitle JSON file
        video_size: (width, height) of the video
        video_duration: Total duration of the video
        
    Returns:
        CompositeVideoClip with TikTok-style subtitles
    """
    # Load subtitle data
    subtitle_data = load_tiktok_subtitle_data(subtitle_path)
    
    # Reconstruct style
    style_data = subtitle_data.get("style", {})
    style = SubtitleStyle(
        font_family=style_data.get("font_family", "Arial-Bold"),
        font_size=style_data.get("font_size", 48),
        default_color=style_data.get("default_color", "#FFFFFF"),
        highlight_color=style_data.get("highlight_color", "#FFFF00"),
        stroke_color=style_data.get("stroke_color", "#000000"),
        background_color=style_data.get("background_color", "#000000"),
        stroke_width=style_data.get("stroke_width", 2),
        background_opacity=style_data.get("background_opacity", 0.4),
        padding_x=style_data.get("padding_x", 12),
        padding_y=style_data.get("padding_y", 8),
        position=style_data.get("position", "center,bottom")
    )
    
    # Reconstruct word timings
    word_timings = []
    for wt_data in subtitle_data.get("word_timings", []):
        word_timings.append(WordTiming(
            word=wt_data["word"],
            start_time=wt_data["start_time"],
            end_time=wt_data["end_time"],
            sentence_index=wt_data["sentence_index"]
        ))
    
    # Get sentences
    sentences = [s["text"] for s in subtitle_data.get("sentences", [])]
    
    # Create the subtitle clip
    return create_word_highlight_clip(
        sentences=sentences,
        word_timings=word_timings,
        video_duration=video_duration,
        style=style,
        video_size=video_size
    )
