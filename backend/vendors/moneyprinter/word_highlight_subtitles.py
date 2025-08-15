"""
Proper word-by-word highlighting subtitle implementation for TikTok-style videos.

This module provides true word-level highlighting by creating individual text clips
for each word and precisely timing their color changes.
"""

import re
import json
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
from pathlib import Path


@dataclass
class WordHighlightConfig:
    """Configuration for word-by-word highlighting subtitles."""
    font_family: str = "Arial-Bold"
    font_size: int = 48
    default_color: str = "#FFFFFF"      # Color for unspoken words
    highlight_color: str = "#FFFF00"    # Color for currently spoken word
    stroke_color: str = "#000000"       # Text outline color
    background_color: str = "#000000"   # Background color
    stroke_width: int = 2
    background_opacity: float = 0.6
    padding_x: int = 16
    padding_y: int = 12
    position: str = "center,bottom"


def create_word_highlight_subtitle_clip(
    subtitle_data: Dict[str, Any],
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create a subtitle clip with true word-by-word highlighting.
    
    This creates individual text clips for each word and times their color changes
    to create the TikTok-style highlighting effect.
    
    Args:
        subtitle_data: Enhanced subtitle data from JSON file
        video_size: (width, height) of the video
        
    Returns:
        CompositeVideoClip with word-by-word highlighting
    """
    # Extract configuration
    config_data = subtitle_data.get('config', {})
    config = WordHighlightConfig(
        font_family=config_data.get('font_family', 'Arial-Bold'),
        font_size=config_data.get('font_size', 48),
        default_color=config_data.get('default_color', '#FFFFFF'),
        highlight_color=config_data.get('highlight_color', '#FFFF00'),
        stroke_color=config_data.get('stroke_color', '#000000'),
        background_color=config_data.get('background_color', '#000000'),
        stroke_width=config_data.get('stroke_width', 2),
        background_opacity=config_data.get('background_opacity', 0.6),
        padding_x=config_data.get('padding_x', 16),
        padding_y=config_data.get('padding_y', 12),
        position=config_data.get('position', 'center,bottom')
    )
    
    # Extract sentences and word timings
    sentences = subtitle_data.get('sentences', [])
    word_timings = subtitle_data.get('word_timings', [])
    
    if not sentences or not word_timings:
        return CompositeVideoClip([])
    
    video_width, video_height = video_size
    all_clips = []
    
    # Process each sentence
    for sentence_data in sentences:
        sentence_text = sentence_data['text']
        sentence_start = sentence_data['start_time']
        sentence_end = sentence_data['end_time']
        sentence_index = sentence_data['index']
        
        # Get word timings for this sentence
        sentence_word_timings = [
            wt for wt in word_timings 
            if wt['sentence_index'] == sentence_index
        ]
        
        if not sentence_word_timings:
            continue
        
        # Create sentence clip with word highlighting
        sentence_clip = create_sentence_with_word_highlighting(
            sentence_text=sentence_text,
            sentence_start=sentence_start,
            sentence_end=sentence_end,
            word_timings=sentence_word_timings,
            config=config,
            video_size=video_size
        )
        
        if sentence_clip:
            all_clips.append(sentence_clip)
    
    if not all_clips:
        return CompositeVideoClip([])
    
    return CompositeVideoClip(all_clips)


def create_sentence_with_word_highlighting(
    sentence_text: str,
    sentence_start: float,
    sentence_end: float,
    word_timings: List[Dict[str, Any]],
    config: WordHighlightConfig,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create a sentence clip with individual word highlighting.
    
    This method creates separate text clips for each word and precisely times
    their color changes to create the highlighting effect.
    """
    video_width, video_height = video_size
    sentence_duration = sentence_end - sentence_start
    
    if sentence_duration <= 0:
        return None
    
    # Calculate font size based on video dimensions
    font_size = max(20, int(video_height * (config.font_size / 1000)))
    
    # Extract words from sentence
    words = re.findall(r'\b\w+\b', sentence_text)
    if not words:
        return None
    
    # Create a base text clip to measure overall dimensions
    try:
        # Try with system font first (no font parameter)
        base_text = TextClip(
            text=sentence_text,
            font_size=font_size,
            color=config.default_color,
            stroke_color=config.stroke_color,
            stroke_width=config.stroke_width,
            method='caption',
            size=(int(video_width * 0.85), None)
        )
    except Exception as e:
        print(f"Error creating base text clip: {e}")
        # Fallback without stroke
        base_text = TextClip(
            text=sentence_text,
            font_size=font_size,
            color=config.default_color,
            size=(int(video_width * 0.85), None)
        )
    
    # Create background
    bg_width = base_text.w + 2 * config.padding_x
    bg_height = base_text.h + 2 * config.padding_y
    
    background = ColorClip(
        size=(bg_width, bg_height),
        color=hex_to_rgb(config.background_color)
    ).with_opacity(config.background_opacity).with_duration(sentence_duration)
    
    # Create individual word clips
    word_clips = []
    
    # Calculate word positions (simplified - assumes words are laid out horizontally)
    # For a more accurate implementation, you'd need to calculate actual text metrics
    total_text_width = base_text.w
    average_word_width = total_text_width / len(words) if words else 0
    
    for word_idx, word in enumerate(words):
        # Find timing for this word
        word_timing = None
        for wt in word_timings:
            if wt['word'].lower() == word.lower() and wt.get('word_index', -1) == word_idx:
                word_timing = wt
                break
        
        if not word_timing:
            continue
        
        # Calculate word position (simplified horizontal layout)
        word_x = config.padding_x + (word_idx * average_word_width)
        word_y = config.padding_y
        
        # Create two versions of the word: default and highlighted
        try:
            # Default color version (no font parameter for better compatibility)
            try:
                default_word_clip = TextClip(
                    text=word,
                    font_size=font_size,
                    color=config.default_color,
                    stroke_color=config.stroke_color,
                    stroke_width=config.stroke_width
                ).with_position((word_x, word_y)).with_duration(sentence_duration)
            except Exception as e:
                print(f"Error creating word clip for '{word}': {e}")
                # Fallback without stroke
                default_word_clip = TextClip(
                    text=word,
                    font_size=font_size,
                    color=config.default_color
                ).with_position((word_x, word_y)).with_duration(sentence_duration)
            
            # Highlighted color version
            try:
                highlight_word_clip = TextClip(
                    text=word,
                    font_size=font_size,
                    color=config.highlight_color,
                    stroke_color=config.stroke_color,
                    stroke_width=config.stroke_width
                ).with_position((word_x, word_y))
            except Exception as e:
                print(f"Error creating highlight clip for '{word}': {e}")
                # Fallback without stroke
                highlight_word_clip = TextClip(
                    text=word,
                    font_size=font_size,
                    color=config.highlight_color
                ).with_position((word_x, word_y))
            
            # Time the highlight to appear during word speaking time
            word_start_in_sentence = word_timing['start_time'] - sentence_start
            word_duration = word_timing['end_time'] - word_timing['start_time']
            
            # Ensure timing is within sentence bounds
            word_start_in_sentence = max(0, word_start_in_sentence)
            word_duration = min(word_duration, sentence_duration - word_start_in_sentence)
            
            if word_duration > 0:
                highlight_word_clip = highlight_word_clip.with_start(word_start_in_sentence).with_duration(word_duration)
                word_clips.extend([default_word_clip, highlight_word_clip])
            else:
                word_clips.append(default_word_clip)
                
        except Exception as e:
            print(f"Error creating word clip for '{word}': {e}")
            continue
    
    # Combine all elements
    all_elements = [background] + word_clips
    
    try:
        sentence_clip = CompositeVideoClip(all_elements).with_start(sentence_start)
        
        # Position the entire sentence clip
        positioned_clip = position_subtitle_clip(sentence_clip, config.position, video_size)
        return positioned_clip
        
    except Exception as e:
        print(f"Error creating sentence composite: {e}")
        return None


def position_subtitle_clip(clip: CompositeVideoClip, position: str, video_size: Tuple[int, int]) -> CompositeVideoClip:
    """Position subtitle clip based on position string."""
    video_width, video_height = video_size
    
    try:
        raw_pos = position.strip().lower()
        
        if raw_pos.startswith('pct:'):
            # Percentage positioning
            match = re.match(r"pct:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)", raw_pos)
            if match:
                x_pct = float(match.group(1))
                y_pct = float(match.group(2))
                
                clip_w = getattr(clip, 'w', 0) or 0
                clip_h = getattr(clip, 'h', 0) or 0
                
                center_x = int((x_pct / 100.0) * video_width)
                center_y = int((y_pct / 100.0) * video_height)
                
                left = max(0, min(center_x - clip_w // 2, video_width - clip_w))
                top = max(0, min(center_y - clip_h // 2, video_height - clip_h))
                
                return clip.with_position((left, top))
        
        elif raw_pos.startswith('px:'):
            # Pixel positioning
            match = re.match(r"px:\s*([0-9]+)\s*,\s*([0-9]+)", raw_pos)
            if match:
                x_px = int(match.group(1))
                y_px = int(match.group(2))
                
                clip_w = getattr(clip, 'w', 0) or 0
                clip_h = getattr(clip, 'h', 0) or 0
                
                left = max(0, min(x_px, video_width - clip_w))
                top = max(0, min(y_px, video_height - clip_h))
                
                return clip.with_position((left, top))
        
        else:
            # Grid positioning
            parts = [p.strip() for p in raw_pos.split(',')]
            horizontal = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom') else 'bottom'
            
            # Use MoviePy's built-in positioning for grid
            if horizontal == 'center' and vertical == 'bottom':
                return clip.with_position(('center', 'bottom'))
            elif horizontal == 'center' and vertical == 'center':
                return clip.with_position(('center', 'center'))
            elif horizontal == 'center' and vertical == 'top':
                return clip.with_position(('center', 'top'))
            else:
                # Calculate custom position
                clip_w = getattr(clip, 'w', 0) or 0
                clip_h = getattr(clip, 'h', 0) or 0
                
                h_positions = {'left': 50, 'center': video_width // 2, 'right': video_width - 50}
                v_positions = {'top': 50, 'center': video_height // 2, 'bottom': video_height - 50}
                
                x = h_positions[horizontal] - (clip_w // 2 if horizontal == 'center' else 0)
                y = v_positions[vertical] - (clip_h // 2 if vertical == 'center' else 0)
                
                return clip.with_position((max(0, x), max(0, y)))
    
    except Exception as e:
        print(f"Error positioning clip: {e}")
        # Default to center-bottom
        return clip.with_position(('center', 'bottom'))
    
    return clip.with_position(('center', 'bottom'))


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (0, 0, 0)  # Default to black
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def create_word_highlight_subtitles_from_file(
    subtitle_path: str,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create word highlighting subtitles from enhanced subtitle file.
    
    Args:
        subtitle_path: Path to the enhanced subtitle JSON file
        video_size: Video dimensions (width, height)
        
    Returns:
        CompositeVideoClip with word-by-word highlighting
    """
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            subtitle_data = json.load(f)
        
        return create_word_highlight_subtitle_clip(subtitle_data, video_size)
        
    except Exception as e:
        print(f"Error creating word highlight subtitles: {e}")
        return CompositeVideoClip([])
