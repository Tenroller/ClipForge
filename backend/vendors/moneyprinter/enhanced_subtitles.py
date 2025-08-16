"""
Enhanced subtitle system with TikTok-style word highlighting.

This implementation provides:
- Word-by-word highlighting with smooth transitions
- Multiple subtitle clips for different word states
- Customizable fonts, colors, sizes, and effects
- Support for different animation styles
"""

import os
import re
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from moviepy import (
    VideoFileClip, TextClip, CompositeVideoClip, ColorClip,
    concatenate_videoclips
)
import numpy as np


@dataclass
class SubtitleConfig:
    """Enhanced configuration for subtitle styling and behavior."""
    
    # Font settings
    font_family: str = "Arial-Bold"
    font_size: int = 48
    font_bold: bool = True
    
    # Colors (hex format)
    default_color: str = "#FFFFFF"      # White for unspoken words
    highlight_color: str = "#FFFF00"    # Yellow for currently spoken word
    stroke_color: str = "#000000"       # Black outline
    background_color: str = "#000000"   # Black background
    
    # Visual effects
    stroke_width: int = 3
    background_opacity: float = 0.0
    padding_x: int = 16
    padding_y: int = 12
    
    # Animation settings
    highlight_transition: float = 0.1   # Smooth transition time
    word_appear_delay: float = 0.05     # Delay between word appearances
    
    # Layout settings
    position: str = "center,bottom"     # Position on screen
    max_width_percent: float = 0.85     # Max width as % of video width
    line_spacing: float = 1.2           # Line height multiplier
    
    # TikTok-style effects
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_offset_x: int = 2
    shadow_offset_y: int = 2
    glow_enabled: bool = False
    glow_color: str = "#FFFFFF"
    glow_intensity: float = 0.3


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (255, 255, 255)  # Default to white
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (255, 255, 255)
 

def estimate_word_timings(sentences: List[str], audio_clips: List[Any]) -> List[Dict[str, Any]]:
    """
    Estimate word-level timing based on sentence duration and word distribution.
    
    This provides a reasonable approximation for word timing. For production use,
    consider integrating with speech recognition APIs that provide word-level timestamps.
    """
    word_timings = []
    current_time = 0.0
    
    for sentence_idx, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips)):
        sentence_duration = audio_clip.duration
        print(f"[DEBUG] Sentence {sentence_idx}: '{sentence[:50]}...' duration: {sentence_duration:.2f}s")
        
        # Extract words and punctuation
        words = re.findall(r'\b\w+\b|\S', sentence)
        text_words = [w for w in words if re.match(r'\b\w+\b', w)]
        
        if not text_words:
            current_time += sentence_duration
            continue
        
        # More realistic timing based on typical speech rates (150-160 words per minute)
        # Average word duration is about 0.4 seconds, but varies by word length
        
        word_start_time = current_time
        total_words = len(text_words)
        
        # Add small pauses between words (more realistic)
        available_time = sentence_duration * 0.95  # 95% for words, 5% for pauses
        pause_time_per_gap = (sentence_duration * 0.05) / max(1, total_words - 1)
        
        for word_idx, word in enumerate(text_words):
            # Base duration proportional to word length but with minimum and maximum
            chars_in_word = len(word)
            
            # Minimum 0.2s per word, maximum 1.0s per word
            # Longer words get proportionally more time
            base_duration = max(0.2, min(1.0, 0.15 + (chars_in_word * 0.05)))
            
            # Scale to fit within available time
            if total_words > 0:
                time_per_word = available_time / total_words
                word_duration = min(base_duration, time_per_word)
            else:
                word_duration = base_duration
            
            # Adjust for sentence position - first and last words slightly longer
            if word_idx == 0 or word_idx == total_words - 1:
                word_duration *= 1.1
            
            word_end_time = word_start_time + word_duration
            
            word_timings.append({
                'word': word,
                'start_time': word_start_time,
                'end_time': word_end_time,
                'sentence_index': sentence_idx,
                'word_index': word_idx,
                'sentence': sentence
            })
            
            print(f"[DEBUG] Word '{word}' ({word_idx}): {word_start_time:.2f}s - {word_end_time:.2f}s ({word_duration:.2f}s)")
            
            # Move to next word start time (include small pause)
            word_start_time = word_end_time + pause_time_per_gap
        
        current_time += sentence_duration
    
    return word_timings


def create_word_clips(
    word_timings: List[Dict[str, Any]], 
    config: SubtitleConfig,
    video_size: Tuple[int, int]
) -> List[CompositeVideoClip]:
    """
    Create individual clips for each word with highlighting effects.
    """
    video_width, video_height = video_size
    clips = []
    
    # Group words by sentence for better layout
    sentences = {}
    for word_data in word_timings:
        sentence_idx = word_data['sentence_index']
        if sentence_idx not in sentences:
            sentences[sentence_idx] = {
                'words': [],
                'text': word_data['sentence'],
                'start_time': float('inf'),
                'end_time': 0
            }
        sentences[sentence_idx]['words'].append(word_data)
        sentences[sentence_idx]['start_time'] = min(sentences[sentence_idx]['start_time'], word_data['start_time'])
        sentences[sentence_idx]['end_time'] = max(sentences[sentence_idx]['end_time'], word_data['end_time'])
    
    # Create clips for each sentence
    for sentence_idx, sentence_data in sentences.items():
        sentence_clip = create_sentence_highlight_clip(
            sentence_data=sentence_data,
            config=config,
            video_size=video_size
        )
        if sentence_clip:
            clips.append(sentence_clip)
    
    return clips


def create_sentence_highlight_clip(
    sentence_data: Dict[str, Any],
    config: SubtitleConfig,
    video_size: Tuple[int, int]
) -> Optional[CompositeVideoClip]:
    """
    Create a clip for a single sentence with word-by-word highlighting.
    """
    video_width, video_height = video_size
    words = sentence_data['words']
    sentence_text = sentence_data['text']
    sentence_start = sentence_data['start_time']
    sentence_end = sentence_data['end_time']
    sentence_duration = sentence_end - sentence_start
    
    if sentence_duration <= 0:
        return None
    
    # Calculate font size based on video size
    font_size = max(20, int(video_height * (config.font_size / 1000)))
    max_width = int(video_width * config.max_width_percent)
    
    # Create base text clip to measure dimensions
    try:
        base_text_clip = TextClip(
            text=sentence_text,
            font_size=font_size,
            color=config.default_color,
            font=config.font_family,
            stroke_color=config.stroke_color,
            stroke_width=config.stroke_width,
            method='caption',
            size=(max_width, None)
        )
    except Exception as e:
        print(f"Error creating base text clip: {e}")
        # Fallback with minimal parameters
        base_text_clip = TextClip(
            text=sentence_text,
            font_size=font_size,
            color=config.default_color,
            size=(max_width, None)
        )
    
    # Create background only if opacity > 0
    if config.background_opacity > 0:
        bg_width = base_text_clip.w + 2 * config.padding_x
        bg_height = base_text_clip.h + 2 * config.padding_y
        
        background = ColorClip(
            size=(bg_width, bg_height),
            color=hex_to_rgb(config.background_color)
        ).with_opacity(config.background_opacity).with_duration(sentence_duration)
        
        text_padding_x = config.padding_x
        text_padding_y = config.padding_y
    else:
        background = None
        text_padding_x = 0
        text_padding_y = 0
    
    # Create the dynamic text clip with highlighting
    def make_text_frame(t):
        """Generate text with appropriate highlighting at time t."""
        absolute_time = sentence_start + t
        
        # Find currently spoken word
        current_word_idx = None
        for word_data in words:
            if word_data['start_time'] <= absolute_time <= word_data['end_time']:
                current_word_idx = word_data['word_index']
                break
        
        # Create text with highlighting
        sentence_words = re.findall(r'\b\w+\b', sentence_text)
        highlighted_text = ""
        
        for idx, word in enumerate(sentence_words):
            if idx == current_word_idx:
                # Apply highlight styling
                highlighted_text += word + " "
            else:
                highlighted_text += word + " "
        
        return highlighted_text.strip()
    
    # For now, create a simpler version with color transitions
    # We'll create overlapping clips with different colors
    text_clips = []
    
    # Base text (always visible with default color)
    base_positioned = base_text_clip.with_position((text_padding_x, text_padding_y)).with_duration(sentence_duration)
    text_clips.append(base_positioned)
    
    # Create highlight clips for each word
    for word_data in words:
        word_start_rel = word_data['start_time'] - sentence_start
        word_duration = word_data['end_time'] - word_data['start_time']
        
        if word_start_rel >= 0 and word_duration > 0:
            try:
                # Create highlighted version of the entire sentence
                highlighted_text_clip = TextClip(
                    text=sentence_text,
                    font_size=font_size,
                    color=config.highlight_color,
                    font=config.font_family,
                    stroke_color=config.stroke_color,
                    stroke_width=config.stroke_width,
                    method='caption',
                    size=(max_width, None)
                ).with_position((text_padding_x, text_padding_y)).with_duration(word_duration).with_start(word_start_rel)
                
                # TODO: Implement actual word-level masking
                # For now, this will highlight the entire sentence during each word
                # In a full implementation, you would create a mask that only highlights the specific word
                
                text_clips.append(highlighted_text_clip)
                
            except Exception as e:
                print(f"Error creating highlight clip for word '{word_data['word']}': {e}")
                continue
    
    # Combine all elements
    if background is not None:
        all_clips = [background] + text_clips
    else:
        all_clips = text_clips
    
    try:
        sentence_clip = CompositeVideoClip(all_clips).with_start(sentence_start)
        
        # Position the entire sentence clip
        positioned_clip = position_subtitle_clip(sentence_clip, config.position, video_size)
        return positioned_clip
        
    except Exception as e:
        print(f"Error creating sentence clip: {e}")
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
            # Grid positioning - use consistent coordinate system
            parts = [p.strip() for p in raw_pos.split(',')]
            horizontal = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom') else 'bottom'
            
            # Get clip dimensions
            clip_w = getattr(clip, 'w', 0) or 0
            clip_h = getattr(clip, 'h', 0) or 0
            
            # Calculate position based on grid - align with frontend preview
            # Use the same positioning logic as in video.py for consistency
            if horizontal == 'left':
                x = int(0.10 * video_width) - (clip_w // 2)  # 10% from left, centered on subtitle
            elif horizontal == 'right':
                x = int(0.90 * video_width) - (clip_w // 2)  # 90% from left, centered on subtitle
            else:  # center
                x = (video_width - clip_w) // 2  # Center horizontally
            
            if vertical == 'top':
                y = int(0.15 * video_height) - (clip_h // 2)  # 15% from top, centered on subtitle
            elif vertical == 'center':
                y = (video_height - clip_h) // 2  # Center vertically
            else:  # bottom
                y = int(0.85 * video_height) - clip_h  # 85% from top, subtitle bottom aligns with this line
            
            # Ensure position is within bounds with proper margin for bottom positioning
            x = max(0, min(x, video_width - clip_w))
            y = max(0, min(y, video_height - clip_h))
            
            return clip.with_position((x, y))
    
    except Exception as e:
        print(f"Error positioning clip: {e}")
        # Default to center-bottom
        return clip.with_position(('center', 'bottom'))
    
    return clip.with_position(('center', 'bottom'))


def generate_enhanced_subtitles(
    sentences: List[str],
    audio_clips: List[Any],
    config: Optional[SubtitleConfig] = None,
    video_size: Tuple[int, int] = (1080, 1920)
) -> str:
    """
    Generate enhanced subtitle data with TikTok-style configuration.
    
    Returns:
        Path to JSON file containing subtitle data and configuration
    """
    if config is None:
        config = SubtitleConfig()
    
    # Generate word timings
    word_timings = estimate_word_timings(sentences, audio_clips)
    
    # Create subtitle data structure with properly formatted sentences
    sentence_data = []
    for idx, sentence in enumerate(sentences):
        sentence_words = [wt for wt in word_timings if wt['sentence_index'] == idx]
        if sentence_words:
            sentence_data.append({
                "text": sentence,
                "index": idx,
                "start_time": min(wt['start_time'] for wt in sentence_words),
                "end_time": max(wt['end_time'] for wt in sentence_words)
            })
        else:
            # Handle case where no words found for sentence
            sentence_data.append({
                "text": sentence,
                "index": idx,
                "start_time": 0.0,
                "end_time": 1.0
            })
    
    subtitle_data = {
        'version': '1.0',
        'type': 'tiktok_enhanced',
        'config': asdict(config),
        'video_size': video_size,
        'sentences': sentence_data,
        'word_timings': word_timings,
        'metadata': {
            'total_words': len(word_timings),
            'total_sentences': len(sentences),
            'total_duration': max([wt['end_time'] for wt in word_timings]) if word_timings else 0
        }
    }
    
    # Save to file - use absolute path
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    subtitles_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'subtitles')
    subtitle_path = os.path.join(subtitles_dir, f"{uuid.uuid4()}_enhanced.json")
    Path(subtitle_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"Enhanced subtitle data saved to: {subtitle_path}")
    return subtitle_path


def create_enhanced_subtitle_clip(
    subtitle_path: str,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create enhanced subtitle clip from saved data.
    
    Args:
        subtitle_path: Path to the enhanced subtitle JSON file
        video_size: Video dimensions (width, height)
        
    Returns:
        CompositeVideoClip with enhanced subtitles
    """
    try:
        # Use the new word highlighting implementation
        import word_highlight_subtitles
        return word_highlight_subtitles.create_word_highlight_subtitles_from_file(subtitle_path, video_size)
    except ImportError:
        print("Warning: word_highlight_subtitles module not found, using fallback")
        # Fallback to basic implementation
        return create_enhanced_subtitle_clip_fallback(subtitle_path, video_size)
    except Exception as e:
        print(f"Error creating enhanced subtitle clip: {e}")
        # Create a transparent empty clip instead of empty composite
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)


def create_enhanced_subtitle_clip_fallback(
    subtitle_path: str,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Fallback implementation for enhanced subtitle clip creation.
    """
    # Load subtitle data
    with open(subtitle_path, 'r', encoding='utf-8') as f:
        subtitle_data = json.load(f)
    
    # Reconstruct config
    config_data = subtitle_data.get('config', {})
    config = SubtitleConfig(**config_data)
    
    # Get word timings
    word_timings = subtitle_data.get('word_timings', [])
    
    if not word_timings:
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
    
    # Create word clips
    clips = create_word_clips(word_timings, config, video_size)
    
    if not clips:
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
    
    # Combine all clips
    try:
        final_clip = CompositeVideoClip(clips)
        return final_clip
    except Exception as e:
        print(f"Error creating final subtitle clip: {e}")
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)


# Utility functions for integration

def create_tiktok_style_config(
    font_family: str = "Arial-Bold",
    font_size: int = 48,
    default_color: str = "#FFFFFF",
    highlight_color: str = "#FFFF00",
    position: str = "center,bottom",
    **kwargs
) -> SubtitleConfig:
    """Create a TikTok-style subtitle configuration with custom parameters."""
    return SubtitleConfig(
        font_family=font_family,
        font_size=font_size,
        default_color=default_color,
        highlight_color=highlight_color,
        position=position,
        **kwargs
    )


def is_enhanced_subtitle_file(subtitle_path: str) -> bool:
    """Check if a subtitle file is in enhanced format."""
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('type') == 'tiktok_enhanced'
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return False
