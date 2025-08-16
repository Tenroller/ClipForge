"""
Improved word-by-word highlighting for TikTok-style subtitles.

This module provides a better implementation of word-level highlighting
by creating precise word masks and overlays.
"""

import re
from typing import List, Dict, Tuple, Any
from moviepy import TextClip, CompositeVideoClip, ColorClip


def create_word_mask_clip(
    sentence_text: str,
    target_word: str,
    word_index: int,
    font_size: int,
    font_choices: List[str],
    text_size: Tuple[int, int],
    highlight_color: str,
    stroke_color: str = "#000000",
    stroke_width: int = 2
) -> TextClip:
    """
    Create a text clip that highlights only the target word.
    
    This creates a full sentence text clip but with only the target word
    in the highlight color, and all other words transparent or in a different color.
    """
    
    # Split sentence into words
    words = re.findall(r'\S+', sentence_text)  # Keep punctuation attached to words
    
    if word_index >= len(words):
        # Fallback: create empty transparent clip
        return TextClip("", font_size=font_size, color="transparent", size=text_size)
    
    # Create a version of the sentence where only the target word is visible/highlighted
    # We'll use spaces to maintain word positions but make non-target words transparent
    highlighted_words = []
    for i, word in enumerate(words):
        if i == word_index:
            highlighted_words.append(word)  # Keep target word as-is
        else:
            # Replace other words with spaces to maintain positioning
            highlighted_words.append(' ' * len(word))
    
    highlighted_sentence = ' '.join(highlighted_words)
    
    # Create the highlight clip
    for font_choice in font_choices:
        try:
            clip = TextClip(
                text=highlighted_sentence,
                font_size=font_size,
                color=highlight_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                method='caption',
                font=font_choice,
                size=text_size
            )
            return clip
        except Exception:
            continue
    
    # Fallback without stroke
    try:
        return TextClip(
            text=highlighted_sentence,
            font_size=font_size,
            color=highlight_color,
            size=text_size
        )
    except Exception:
        # Final fallback: empty clip
        return TextClip("", font_size=font_size, color="transparent", size=text_size)


def create_precise_word_highlighting(
    sentence_text: str,
    sentence_start: float,
    sentence_end: float,
    word_timings: List[Dict[str, Any]],
    config,  # WordHighlightConfig
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create precise word-by-word highlighting using word masks.
    """
    video_width, video_height = video_size
    sentence_duration = sentence_end - sentence_start
    
    if sentence_duration <= 0:
        return CompositeVideoClip([])
    
    # Calculate font size
    font_size = max(20, int(video_height * (config.font_size / 1000)))
    text_size = (int(video_width * 0.85), int(video_height * 0.2))
    
    # Font choices
    font_choices = [config.font_family, "Arial-Bold", "arial.ttf", "Arial", None]
    font_choices = [f for f in font_choices if f is not None]
    
    # Create base text clip (all words in default color)
    base_text = None
    for font_choice in font_choices:
        try:
            base_text = TextClip(
                text=sentence_text,
                font_size=font_size,
                color=config.default_color,
                stroke_color=config.stroke_color,
                stroke_width=config.stroke_width,
                method='caption',
                font=font_choice,
                size=text_size
            )
            break
        except Exception:
            continue
    
    if base_text is None:
        try:
            base_text = TextClip(
                text=sentence_text,
                font_size=font_size,
                color=config.default_color,
                size=text_size
            )
        except Exception:
            return CompositeVideoClip([])
    
    # Create background
    bg_width = base_text.w + 2 * config.padding_x
    bg_height = base_text.h + 2 * config.padding_y
    
    background = ColorClip(
        size=(bg_width, bg_height),
        color=hex_to_rgb(config.background_color)
    ).with_opacity(config.background_opacity).with_duration(sentence_duration)
    
    # Position base text
    base_text_positioned = base_text.with_position((config.padding_x, config.padding_y)).with_duration(sentence_duration)
    
    # Create word highlight clips
    highlight_clips = []
    sentence_words = re.findall(r'\S+', sentence_text)  # All tokens including punctuation
    
    # Sort word timings by start time
    word_timings_sorted = sorted(word_timings, key=lambda x: x['start_time'])
    
    for word_timing in word_timings_sorted:
        word = word_timing['word']
        word_index = word_timing.get('word_index', -1)
        
        # Find the word in the sentence
        if word_index < 0 or word_index >= len(sentence_words):
            # Try to find by matching the word text
            for i, sentence_word in enumerate(sentence_words):
                if word.lower() in sentence_word.lower():
                    word_index = i
                    break
        
        if word_index < 0 or word_index >= len(sentence_words):
            print(f"Could not find word '{word}' in sentence '{sentence_text}'")
            continue
        
        # Calculate timing
        word_start_in_sentence = word_timing['start_time'] - sentence_start
        word_duration = word_timing['end_time'] - word_timing['start_time']
        
        # Ensure timing is within bounds
        word_start_in_sentence = max(0, word_start_in_sentence)
        if word_start_in_sentence >= sentence_duration:
            continue
            
        word_duration = min(word_duration, sentence_duration - word_start_in_sentence)
        if word_duration <= 0:
            continue
        
        # Create word mask clip
        try:
            word_mask = create_word_mask_clip(
                sentence_text=sentence_text,
                target_word=word,
                word_index=word_index,
                font_size=font_size,
                font_choices=font_choices,
                text_size=text_size,
                highlight_color=config.highlight_color,
                stroke_color=config.stroke_color,
                stroke_width=config.stroke_width
            )
            
            # Position and time the mask
            word_mask_positioned = word_mask.with_position((config.padding_x, config.padding_y))
            word_mask_timed = word_mask_positioned.with_start(word_start_in_sentence).with_duration(word_duration)
            
            highlight_clips.append(word_mask_timed)
            
        except Exception as e:
            print(f"Error creating word mask for '{word}': {e}")
            continue
    
    # Combine all elements
    all_elements = [background, base_text_positioned] + highlight_clips
    
    try:
        sentence_clip = CompositeVideoClip(all_elements).with_start(sentence_start)
        return sentence_clip
    except Exception as e:
        print(f"Error creating precise word highlighting composite: {e}")
        return CompositeVideoClip([])


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (0, 0, 0)
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (0, 0, 0)
