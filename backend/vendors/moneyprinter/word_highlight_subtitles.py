"""
Proper word-by-word highlighting subtitle implementation for TikTok-style videos.

This module provides true word-level highlighting by creating individual text clips
for each word and precisely timing their color changes.
"""

import re
import json
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
from pathlib import Path


@dataclass
class WordHighlightConfig:
    """Configuration for word-by-word highlighting subtitles."""
    font_family: str = "Arial"  # Changed to Arial since it's working reliably
    font_size: int = 28
    default_color: str = "#FFFFFF"      # Color for unspoken words
    highlight_color: str = "#FFFF00"    # Color for currently spoken word
    stroke_color: str = "#000000"       # Text outline color
    background_color: str = "#000000"   # Background color
    stroke_width: int = 2
    background_opacity: float = 0.0
    padding_x: int = 16
    padding_y: int = 12
    position: str = "center,bottom"


def create_word_highlight_subtitle_clip(
    subtitle_data: Dict[str, Any],
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create a subtitle clip with true word-by-word highlighting using 3-word chunks.
    
    This creates 3-word sliding windows where only the current word is highlighted,
    providing a more focused and readable TikTok-style subtitle experience.
    
    Args:
        subtitle_data: Enhanced subtitle data from JSON file
        video_size: (width, height) of the video
        
    Returns:
        CompositeVideoClip with word-by-word highlighting
    """
    # Extract configuration
    config_data = subtitle_data.get('config', {})
    config = WordHighlightConfig(
        font_family=config_data.get('font_family', 'Arial'),
        font_size=config_data.get('font_size', 28),
        default_color=config_data.get('default_color', '#FFFFFF'),
        highlight_color=config_data.get('highlight_color', '#7AC6FF'),  # Use user's highlight color
        stroke_color=config_data.get('stroke_color', '#000000'),
        background_color=config_data.get('background_color', '#000000'),
        stroke_width=config_data.get('stroke_width', 0),  # Use user's stroke width
        background_opacity=config_data.get('background_opacity', 0.0),
        padding_x=config_data.get('padding_x', 20),  # Use user's padding
        padding_y=config_data.get('padding_y', 16),
        position=config_data.get('position', 'center,bottom')
    )
    
    # Extract word timings
    word_timings = subtitle_data.get('word_timings', [])
    
    if not word_timings:
        # Return an empty clip with zero duration
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
    
    video_width, video_height = video_size
    
    # Create 3-word sliding windows with individual word highlighting
    return create_sliding_word_windows(word_timings, config, video_size)


def create_sliding_word_windows(
    word_timings: List[Dict[str, Any]],
    config: WordHighlightConfig,
    video_size: Tuple[int, int]
) -> CompositeVideoClip:
    """
    Create sliding word windows with sentence-aware logic.
    
    Instead of rigid 3-word windows, this creates flexible windows that:
    1. Respect sentence boundaries (never mix words from different sentences)
    2. Show 1-3 words depending on context and sentence structure
    3. Provide smooth transitions within sentences
    """
    video_width, video_height = video_size
    
    if not word_timings:
        # Return an empty clip with zero duration
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
    
    # Sort word timings by start time
    word_timings = sorted(word_timings, key=lambda x: x['start_time'])
    
    # Group words by sentence to respect boundaries
    sentences = {}
    for word in word_timings:
        sentence_idx = word.get('sentence_index', 0)
        if sentence_idx not in sentences:
            sentences[sentence_idx] = []
        sentences[sentence_idx].append(word)
    
    # Create sliding windows within each sentence
    all_window_clips = []
    
    for sentence_idx in sorted(sentences.keys()):
        sentence_words = sentences[sentence_idx]
        
        # Create windows within this sentence
        for i, current_word in enumerate(sentence_words):
            # Create sentence-aware window
            window_words = create_sentence_aware_window(
                sentence_words, i, max_window_size=3
            )
            
            if not window_words:
                continue
            
            # Find the index of the highlighted word in the window
            highlighted_idx = None
            for j, word in enumerate(window_words):
                if (word['start_time'] == current_word['start_time'] and 
                    word['end_time'] == current_word['end_time']):
                    highlighted_idx = j
                    break
            
            if highlighted_idx is None:
                continue
            
            # Create window clip for this word's timing
            window_clip = create_3_word_window_clip(
                window_words=window_words,
                highlighted_word_idx=highlighted_idx,
                config=config,
                video_size=video_size,
                start_time=current_word['start_time'],
                end_time=current_word['end_time']
            )
            
            if window_clip:
                all_window_clips.append(window_clip)
    
    if not all_window_clips:
        # Return an empty clip with zero duration instead of empty CompositeVideoClip
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
    
    # Create composite with natural sizing to prevent broadcasting errors
    return CompositeVideoClip(all_window_clips)


def create_sentence_aware_window(
    sentence_words: List[Dict[str, Any]], 
    current_word_idx: int, 
    max_window_size: int = 3
) -> List[Dict[str, Any]]:
    """
    Create a smart window that respects sentence flow and readability.
    
    Args:
        sentence_words: All words in the current sentence
        current_word_idx: Index of the word being highlighted
        max_window_size: Maximum number of words to show (default: 3)
        
    Returns:
        List of words to display in this window
    """
    if not sentence_words or current_word_idx >= len(sentence_words):
        return []
    
    sentence_length = len(sentence_words)
    current_word = sentence_words[current_word_idx]
    
    # For short sentences (3 words or less), show all words
    if sentence_length <= max_window_size:
        return sentence_words
    
    # Smart windowing logic based on position in sentence
    if current_word_idx == 0:
        # Beginning of sentence: show current + next 1-2 words
        window_end = min(sentence_length, max_window_size)
        return sentence_words[0:window_end]
    
    elif current_word_idx == sentence_length - 1:
        # End of sentence: show previous 1-2 words + current
        window_start = max(0, sentence_length - max_window_size)
        return sentence_words[window_start:sentence_length]
    
    else:
        # Middle of sentence: try to center the current word
        # Prefer showing: [previous word] [CURRENT] [next word]
        ideal_start = max(0, current_word_idx - 1)
        ideal_end = min(sentence_length, ideal_start + max_window_size)
        
        # Adjust start if we can't get max_window_size words
        if ideal_end - ideal_start < max_window_size:
            ideal_start = max(0, ideal_end - max_window_size)
        
        return sentence_words[ideal_start:ideal_end]


def create_3_word_window_clip(
    window_words: List[Dict[str, Any]],
    highlighted_word_idx: int,
    config: WordHighlightConfig,
    video_size: Tuple[int, int],
    start_time: float,
    end_time: float
) -> Optional[CompositeVideoClip]:
    """
    Create a clip showing up to 3 words with one highlighted.
    
    Args:
        window_words: List of 1-3 word timing dictionaries
        highlighted_word_idx: Index of the word to highlight (0-2)
        config: Styling configuration
        video_size: Video dimensions
        start_time: When this window should start appearing
        end_time: When this window should stop appearing
    """
    video_width, video_height = video_size
    duration = end_time - start_time
    
    # Debug logging to confirm function is called
    debug_msg = f"DEBUG: create_3_word_window_clip called with {len(window_words)} words: {[w['word'] for w in window_words]}"
    print(debug_msg)
    
    if duration <= 0.05:  # Skip very short durations
        return None
    
    # Calculate font size based on video dimensions
    font_size = max(24, int(video_height * (config.font_size / 1000)))
    
    # Create individual word clips
    word_clips = []
    word_spacing = 10  # Space between words in pixels
    
    # Font choices for fallback - comprehensive list of cross-platform fonts
    font_choices = get_font_fallback_list(config.font_family)
    
    # First pass: create all word clips to measure total width
    individual_word_clips = []
    total_text_width = 0
    max_text_height = 0
    
    for idx, word_data in enumerate(window_words):
        word = word_data['word']

        # Skip empty or whitespace words BEFORE creating TextClip
        if not word or word.strip() == '':
            error_msg = f"VALIDATION: Skipping empty or whitespace word at index {idx}: '{word}'"
            print(error_msg)
            # Insert a transparent placeholder for empty/whitespace word
            placeholder = ColorClip(size=(20, 20), color=(0,0,0,0)).with_opacity(0).with_duration(duration)
            individual_word_clips.append(placeholder)
            total_text_width += 20
            max_text_height = max(max_text_height, 20)
            if idx < len(window_words) - 1:
                total_text_width += word_spacing
            continue

        # Skip problematic single characters that cause dimension issues
        if len(word) == 1 and word not in ['I', 'a', 'A']:
            print(f"VALIDATION: Skipping problematic single character word at index {idx}: '{word}'")
            continue
        
        is_highlighted = (idx == highlighted_word_idx)
        word_color = config.highlight_color if is_highlighted else config.default_color
        
        print(f"DEBUG: Creating TextClip for word {idx}: '{word}' (highlighted: {is_highlighted})")
        print(f"DEBUG: Word color: {word_color} (highlighted: {is_highlighted})")
        print(f"DEBUG: Config colors - default: {config.default_color}, highlight: {config.highlight_color}")
        
        # Create word clip with robust font fallback
        word_clip = None
        font_used = None
        
        # Get font choices with fallbacks
        font_choices = get_font_fallback_list(config.font_family)
        
        try:
            for font_choice in font_choices:
                try:
                    # Prepare TextClip parameters based on stroke settings
                    clip_params = {
                        'text': word,
                        'font_size': font_size,
                        'color': word_color
                    }
                    
                    # Only add stroke if stroke_width > 0
                    if config.stroke_width > 0:
                        clip_params['stroke_color'] = config.stroke_color
                        clip_params['stroke_width'] = config.stroke_width
                    
                    # Add font if specified
                    if font_choice is not None:
                        clip_params['font'] = font_choice
                    
                    word_clip = TextClip(**clip_params)
                    
                    # Test if the clip was created successfully
                    if word_clip and hasattr(word_clip, 'w') and hasattr(word_clip, 'h'):
                        clip_w = getattr(word_clip, 'w', 0) or 0
                        clip_h = getattr(word_clip, 'h', 0) or 0
                        if clip_w > 0 and clip_h > 0:
                            # Ensure minimum height for consistency
                            if clip_h < 50:
                                # Scale up small clips to maintain consistent height
                                scale_factor = 50.0 / clip_h
                                try:
                                    word_clip = word_clip.resized(scale_factor)
                                    clip_w = int(clip_w * scale_factor)
                                    clip_h = int(clip_h * scale_factor)
                                    print(f"DEBUG: Scaled up small word clip '{word}' to maintain height: {clip_h}")
                                except AttributeError:
                                    # Fallback for older MoviePy versions - recreate with larger font
                                    print(f"DEBUG: Resize not available, recreating '{word}' with larger font for height consistency")
                                    try:
                                        larger_font_size = int(font_size * (50.0 / clip_h))
                                        larger_clip_params = {
                                            'text': word,
                                            'font_size': larger_font_size,
                                            'color': word_color
                                        }
                                        if config.stroke_width > 0:
                                            larger_clip_params['stroke_color'] = config.stroke_color
                                            larger_clip_params['stroke_width'] = config.stroke_width
                                        if font_choice is not None:
                                            larger_clip_params['font'] = font_choice
                                        
                                        word_clip = TextClip(**larger_clip_params)
                                        clip_w = getattr(word_clip, 'w', 0) or 0
                                        clip_h = getattr(word_clip, 'h', 0) or 0
                                        print(f"DEBUG: Recreated '{word}' with font size {larger_font_size}: w={clip_w}, h={clip_h}")
                                    except Exception as recreate_error:
                                        print(f"DEBUG: Failed to recreate '{word}' with larger font: {recreate_error}")
                        
                        # Simplified approach: just validate dimensions without resizing
                        # Resizing can cause dimension inconsistencies in composites
                        print(f"DEBUG: Word clip '{word}' created with dimensions: {clip_w}x{clip_h}")
                        
                        font_used = font_choice
                        print(f"DEBUG: Successfully created word clip for '{word}' with font '{font_choice}': w={clip_w}, h={clip_h}")
                        print(f"DEBUG: Color used: {word_color} (RGB: {hex_to_rgb(word_color)})")
                        break
                    else:
                        word_clip = None
                        continue
                            
                except Exception as e:
                    print(f"DEBUG: Font '{font_choice}' failed for '{word}': {e}")
                    word_clip = None
                    continue
        except Exception as e:
            print(f"DEBUG: Font fallback system failed for '{word}': {e}")
            word_clip = None
        
        # Final fallback with minimal parameters if all fonts failed
        if word_clip is None:
            try:
                word_clip = TextClip(
                    text=word,
                    font_size=font_size,
                    color=word_color
                )
                font_used = "default"
                print(f"DEBUG: Using default font fallback for '{word}'")
            except Exception as e:
                print(f"ERROR: Failed to create word clip for '{word}' with all fonts: {e}")
                # Create a placeholder clip to prevent complete failure
                placeholder = ColorClip(size=(50, 30), color=(255,255,255)).with_duration(duration)
                individual_word_clips.append(placeholder)
                total_text_width += 50
                max_text_height = max(max_text_height, 30)
                if idx < len(window_words) - 1:
                    total_text_width += word_spacing
                continue
        
        # Validate clip dimensions to prevent broadcasting errors
        if word_clip is None or not hasattr(word_clip, 'w') or not hasattr(word_clip, 'h'):
            print(f"VALIDATION ERROR: Skipping invalid word clip for '{word}': clip has no dimensions")
            continue
            
        clip_width = getattr(word_clip, 'w', 0) or 0
        clip_height = getattr(word_clip, 'h', 0) or 0
        
        if clip_width <= 0 or clip_height <= 0:
            print(f"VALIDATION ERROR: Skipping zero-dimension word clip for '{word}': w={clip_width}, h={clip_height}")
            continue
            
        # Additional safeguard: ensure minimum dimensions (at least 10 pixels each)
        # This prevents broadcasting errors in MoviePy composite operations
        clip_w = getattr(word_clip, 'w', 0)
        clip_h = getattr(word_clip, 'h', 0)
        if clip_w < 10 or clip_h < 10:
            print(f"VALIDATION ERROR: Word clip for '{word}' has insufficient dimensions (w={clip_w}, h={clip_h}), skipping")
            continue

        print(f"DEBUG: Successfully created word clip for '{word}': w={clip_w}, h={clip_h}")
        
        individual_word_clips.append(word_clip)
        total_text_width += clip_width
        max_text_height = max(max_text_height, clip_height)
        
        # Add spacing except for last word
        if idx < len(window_words) - 1:
            total_text_width += word_spacing
    
    if not individual_word_clips:
        print(f"VALIDATION ERROR: No valid word clips created for window")
        return None
    
    # Additional validation: ensure we have enough content for a meaningful subtitle
    if total_text_width < 20 or max_text_height < 20:
        print(f"VALIDATION ERROR: Window has insufficient content: w={total_text_width}, h={max_text_height}")
        return None
    
    # Create background only if opacity > 0
    if config.background_opacity > 0:
        bg_width = total_text_width + 2 * config.padding_x
        bg_height = max_text_height + 2 * config.padding_y
        
        background = ColorClip(
            size=(bg_width, bg_height),
            color=hex_to_rgb(config.background_color)
        ).with_opacity(config.background_opacity).with_duration(duration)
        
        # Position individual word clips horizontally
        current_x = config.padding_x
        positioned_word_clips = []
        
        for word_clip in individual_word_clips:
            # Center vertically within the background
            word_y = config.padding_y + (max_text_height - word_clip.h) // 2
            positioned_word_clip = word_clip.with_position((current_x, word_y)).with_duration(duration)
            positioned_word_clips.append(positioned_word_clip)
            current_x += word_clip.w + word_spacing
        
        # Combine background and words
        all_elements = [background] + positioned_word_clips
    else:
        # No background - just position text clips without padding
        current_x = 0
        positioned_word_clips = []
        
        for word_clip in individual_word_clips:
            # Center vertically without background padding
            word_y = (max_text_height - word_clip.h) // 2
            positioned_word_clip = word_clip.with_position((current_x, word_y)).with_duration(duration)
            positioned_word_clips.append(positioned_word_clip)
            current_x += word_clip.w + word_spacing
        
        # Only text clips, no background
        all_elements = positioned_word_clips
    
    # Final validation: check all clips have valid dimensions before creating composite
    valid_elements = []
    for i, element in enumerate(all_elements):
        if hasattr(element, 'w') and hasattr(element, 'h'):
            if element.w > 0 and element.h > 0:
                # Additional check: ensure minimum dimensions to prevent broadcasting errors
                if element.w >= 5 and element.h >= 5:
                    valid_elements.append(element)
                else:
                    error_msg = f"FINAL VALIDATION: Dropping element {i} with insufficient dimensions: w={element.w}, h={element.h}"
                    print(error_msg)
            else:
                error_msg = f"FINAL VALIDATION: Dropping element {i} with zero dimensions: w={element.w}, h={element.h}"
                print(error_msg)
        else:
            error_msg = f"FINAL VALIDATION: Dropping element {i} without dimension attributes"
            print(error_msg)
    
    if not valid_elements:
        error_msg = "FINAL VALIDATION: No valid elements remain, returning None"
        print(error_msg)
        return None
    
    try:
        # Create composite WITHOUT forcing video size - let it size based on content
        # This allows proper positioning calculations
        window_clip = CompositeVideoClip(valid_elements).with_start(start_time)
        
        # Validate the composite clip dimensions
        if hasattr(window_clip, 'w') and hasattr(window_clip, 'h'):
            if window_clip.w <= 0 or window_clip.h <= 0:
                print(f"ERROR: Composite clip has invalid dimensions: w={window_clip.w}, h={window_clip.h}")
                return None
            
            print(f"DEBUG: Composite clip created with natural dimensions: {window_clip.w}x{window_clip.h}")
        else:
            print(f"ERROR: Composite clip missing dimension attributes")
            return None
        
        # Position the entire window on screen
        print(f"DEBUG: About to position subtitle clip with position: '{config.position}'")
        positioned_window = position_subtitle_clip(window_clip, config.position, video_size)

        if positioned_window:
            # Debug: check the final position
            try:
                final_x = getattr(positioned_window, 'x', 'unknown')
                final_y = getattr(positioned_window, 'y', 'unknown')
                print(f"DEBUG: Final positioned window - x: {final_x}, y: {final_y}")
            except Exception as pos_debug_error:
                print(f"DEBUG: Could not get final position: {pos_debug_error}")

            # Remove mask from positioned clip to prevent broadcasting errors
            # Subtitles are text overlays and don't need transparency masking
            try:
                if hasattr(positioned_window, 'mask') and positioned_window.mask is not None:
                    # Remove the mask by setting it to None
                    positioned_window = positioned_window.without_mask()
                    print(f"DEBUG: Removed mask from positioned clip to prevent broadcasting errors")
                else:
                    print(f"DEBUG: Positioned clip has no mask (which is fine)")
            except Exception as mask_error:
                print(f"DEBUG: Could not remove mask from positioned clip: {mask_error}")

        return positioned_window
        
    except Exception as e:
        print(f"Error creating 3-word window clip: {e}")
        return None


def position_subtitle_clip(clip: CompositeVideoClip, position: str, video_size: Tuple[int, int]) -> CompositeVideoClip:
    """Position subtitle clip based on position string."""
    video_width, video_height = video_size
    
    try:
        raw_pos = position.strip().lower()
        print(f"DEBUG: Positioning subtitle clip with position: '{raw_pos}' for video size: {video_size}")
        
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
                
                print(f"DEBUG: Percentage positioning - x_pct: {x_pct}, y_pct: {y_pct}, final: ({left}, {top})")
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
                
                print(f"DEBUG: Pixel positioning - x_px: {x_px}, y_px: {y_px}, final: ({left}, {top})")
                return clip.with_position((left, top))
        
        else:
            # Grid positioning - use consistent coordinate system
            parts = [p.strip() for p in raw_pos.split(',')]
            horizontal = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom') else 'bottom'
            
            print(f"DEBUG: Grid positioning - horizontal: {horizontal}, vertical: {vertical}")
            
            # Get clip dimensions
            clip_w = getattr(clip, 'w', 0) or 0
            clip_h = getattr(clip, 'h', 0) or 0
            
            print(f"DEBUG: Clip dimensions: {clip_w}x{clip_h}, Video dimensions: {video_width}x{video_height}")
            
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
            
            print(f"DEBUG: Final grid position: ({x}, {y})")
            return clip.with_position((x, y))
    
    except Exception as e:
        print(f"ERROR: Error positioning clip: {e}")
        # Default to center-bottom with fallback positioning
        try:
            clip_w = getattr(clip, 'w', 0) or 0
            clip_h = getattr(clip, 'h', 0) or 0
            x = (video_width - clip_w) // 2
            y = int(0.85 * video_height) - clip_h
            print(f"DEBUG: Fallback positioning: ({x}, {y})")
            return clip.with_position((x, y))
        except Exception as fallback_error:
            print(f"ERROR: Fallback positioning also failed: {fallback_error}")
            return clip
    
    return clip


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (0, 0, 0)  # Default to black
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (0, 0, 0)


def get_font_fallback_list(primary_font: str) -> List[Optional[str]]:
    """
    Get a comprehensive list of font fallbacks for cross-platform compatibility.
    
    Args:
        primary_font: The primary font to try first
        
    Returns:
        List of font names to try, with None as final fallback
    """
    fallback_fonts = [primary_font] if primary_font else []
    
    # Font mapping for common variations
    font_mappings = {
        # Arial variations
        "Arial": ["Arial", "Arial.ttf", "arial.ttf", "Liberation Sans", "Helvetica", "DejaVu Sans"],
        "Arial-Bold": ["Arial-Bold", "Arial Bold", "ArialBold", "arial-bold.ttf", "arialbold.ttf", "Arial", "Liberation Sans Bold", "DejaVu Sans Bold"],
        
        # Helvetica variations  
        "Helvetica": ["Helvetica", "Helvetica.ttf", "helvetica.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Helvetica-Bold": ["Helvetica-Bold", "Helvetica Bold", "HelveticaBold", "helvetica-bold.ttf", "helveticabold.ttf", "Arial-Bold", "Liberation Sans Bold", "DejaVu Sans Bold"],
        
        # Impact variations
        "Impact": ["Impact", "Impact.ttf", "impact.ttf", "Arial-Bold", "Oswald", "Liberation Sans Bold", "DejaVu Sans Bold"],
        
        # Times variations
        "Times": ["Times", "Times New Roman", "times.ttf", "Liberation Serif", "DejaVu Serif"],
        "Times-Bold": ["Times-Bold", "Times Bold", "TimesBold", "Times New Roman Bold", "times-bold.ttf", "Liberation Serif Bold", "DejaVu Serif Bold"],
        
        # Comic Sans variations
        "Comic-Sans-MS": ["Comic Sans MS", "ComicSansMS", "comic.ttf", "comicsans.ttf", "Arial", "DejaVu Sans"],
        "Comic Sans MS": ["Comic Sans MS", "ComicSansMS", "comic.ttf", "comicsans.ttf", "Arial", "DejaVu Sans"],
        
        # Modern fonts
        "Montserrat": ["Montserrat", "montserrat.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Roboto": ["Roboto", "roboto.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Open Sans": ["Open Sans", "OpenSans", "opensans.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Poppins": ["Poppins", "poppins.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Nunito": ["Nunito", "nunito.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        "Source Sans Pro": ["Source Sans Pro", "SourceSansPro", "sourcesanspro.ttf", "Arial", "Liberation Sans", "DejaVu Sans"],
        
        # System fonts
        "System": ["System", ".AppleSystemUIFont", "Segoe UI", "Roboto", "Arial", "DejaVu Sans"],
        "SF Pro Display": ["SF Pro Display", ".SF Pro Display", "Segoe UI", "Roboto", "Arial", "DejaVu Sans"],
        "Segoe UI": ["Segoe UI", "segoeui.ttf", "Arial", "Liberation Sans", "DejaVu Sans"]
    }
    
    # Add specific mappings for the chosen font
    if primary_font in font_mappings:
        fallback_fonts.extend(font_mappings[primary_font])
    
    # Add universal fallbacks for different platforms
    universal_fallbacks = [
        # Cross-platform sans-serif fonts
        "Arial", "Helvetica", "Liberation Sans", "FreeSans", "Nimbus Sans L",
        "DejaVu Sans", "Bitstream Vera Sans", "Lucida Grande", "Segoe UI",
        
        # System fonts
        ".AppleSystemUIFont", "System", "-apple-system", "BlinkMacSystemFont",
        
        # Serif fallbacks
        "Times New Roman", "Times", "Liberation Serif", "FreeSerif", 
        "Nimbus Roman No9 L", "DejaVu Serif", "Bitstream Vera Serif",
        
        # Monospace fallbacks  
        "Courier New", "Courier", "Liberation Mono", "FreeMono",
        "DejaVu Sans Mono", "Bitstream Vera Sans Mono",
        
        # Final fallback (let MoviePy handle)
        None
    ]
    
    # Add universal fallbacks, avoiding duplicates
    for font in universal_fallbacks:
        if font not in fallback_fonts:
            fallback_fonts.append(font)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_fallbacks = []
    for font in fallback_fonts:
        if font not in seen:
            seen.add(font)
            unique_fallbacks.append(font)
    
    return unique_fallbacks


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
        # Return an empty transparent clip instead of empty composite
        from moviepy import ColorClip
        return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)
