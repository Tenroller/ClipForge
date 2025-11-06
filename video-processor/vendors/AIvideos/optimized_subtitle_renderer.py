"""
Optimized subtitle renderer using pre-rendered frames strategy.

This implementation follows the research recommendations for maximum performance:
1. Pre-renders each frame as a static image using Pillow/PIL
2. Creates a single ImageSequenceClip from all frames
3. Final composition is just 2 layers instead of hundreds

This approach eliminates the MoviePy performance bottleneck identified in the research.
"""

import os
import json
import sys
import numpy as np
from typing import List, Dict, Tuple, Any, Optional, Union
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageSequenceClip

# Add path to access video-processor utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import centralized utilities
try:
    from utils.fonts import get_font_manager
    from utils.colors import hex_to_rgb as centralized_hex_to_rgb
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # Fallback implementations
    try:
        from font_detection import get_font_fallback_list
        get_font_manager = lambda: type('MockManager', (), {'get_font_path': lambda self, name: None, 'get_fallback_font_list': get_font_fallback_list})()
    except ImportError:
        get_font_fallback_list = lambda: ['Arial']
        get_font_manager = lambda: type('MockManager', (), {'get_font_path': lambda self, name: None, 'get_fallback_font_list': get_font_fallback_list})()

    def centralized_hex_to_rgb(hex_color):
        """Fallback hex to rgb conversion."""
        if isinstance(hex_color, str) and hex_color.startswith('#'):
            hex_color = hex_color[1:]
        if len(hex_color) != 6:
            return (255, 255, 255)
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except:
            return (255, 255, 255)


class OptimizedSubtitleRenderer:
    """
    High-performance subtitle renderer using pre-rendered frame strategy.
    
    This eliminates the performance bottleneck of compositing hundreds of TextClip objects
    by pre-rendering each frame as a static image and creating a single video clip.
    """
    
    def __init__(self, video_size: Tuple[int, int], fps: float):
        self.video_width, self.video_height = video_size
        self.fps = fps
        
    def create_optimized_subtitle_clip(
        self,
        subtitle_data: Dict[str, Any],
        duration: float
    ) -> ImageSequenceClip:
        """
        Create optimized subtitle clip using pre-rendered frames.
        
        Args:
            subtitle_data: Enhanced subtitle data from JSON file
            duration: Total duration of the video in seconds
            
        Returns:
            ImageSequenceClip with pre-rendered subtitle animation
        """
        # Extract configuration
        config = subtitle_data.get('config', {})
        word_timings = subtitle_data.get('word_timings', [])
        
        if not word_timings:
            # Return transparent clip if no words
            return self._create_empty_clip(duration)
        
        print(f"Pre-rendering {int(duration * self.fps)} subtitle frames...")
        
        # Pre-render all frames
        subtitle_frames = []
        total_frames = int(duration * self.fps)
        
        # Load font once for efficiency
        font = self._load_font(config)

        # Try to get system fonts if centralized manager is available
        try:
            font_manager = get_font_manager()
            fallback_fonts = font_manager.get_fallback_font_list()  # type: ignore
            if fallback_fonts:
                print(f"Available system fonts: {', '.join(fallback_fonts[:5])}...")
        except Exception:
            pass
        
        # Group words by sentences for better organization
        sentences_map = self._group_words_by_sentences(word_timings)
        
        for frame_number in range(total_frames):
            current_time = frame_number / self.fps
            
            # Create transparent frame
            frame = self._create_frame_image(
                current_time=current_time,
                word_timings=word_timings,
                sentences_map=sentences_map,
                config=config,
                font=font
            )
            
            subtitle_frames.append(np.array(frame))
            
            # Progress indicator
            if frame_number % (total_frames // 20) == 0:
                progress = (frame_number / total_frames) * 100
                print(f"  Progress: {progress:.1f}%")
        
        print("✅ Frame pre-rendering complete. Creating video clip...")
        
        # Create single video clip from all pre-rendered frames
        return ImageSequenceClip(subtitle_frames, fps=self.fps)
    
    def _create_frame_image(
        self,
        current_time: float,
        word_timings: List[Dict[str, Any]],
        sentences_map: Dict[int, List[Dict[str, Any]]],
        config: Dict[str, Any],
        font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
    ) -> Image.Image:
        """Create a single frame image with appropriate word highlighting."""
        
        # Create transparent image
        img = Image.new('RGBA', (self.video_width, self.video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Find active sentence and words at current time
        active_words = self._find_active_words_at_time(current_time, word_timings)
        
        if not active_words:
            return img
        
        # Create 3-word window around the currently spoken word
        window_words = self._create_smart_window(active_words, current_time)
        
        if not window_words:
            return img
        
        # Draw the word window
        self._draw_word_window(
            draw=draw,
            window_words=window_words,
            current_time=current_time,
            config=config,
            font=font,
            img_size=(self.video_width, self.video_height)
        )
        
        return img
    
    def _find_active_words_at_time(
        self,
        current_time: float,
        word_timings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find all words that should be visible at the current time."""
        
        active_words = []
        
        # Find the currently spoken word and surrounding context
        current_word = None
        current_sentence_idx = None
        
        for word in word_timings:
            if word['start_time'] <= current_time < word['end_time']:
                current_word = word
                current_sentence_idx = word.get('sentence_index', 0)
                break
        
        if not current_word:
            return []
        
        # Get all words from the same sentence for context
        sentence_words = [
            w for w in word_timings 
            if w.get('sentence_index', 0) == current_sentence_idx
        ]
        
        return sentence_words
    
    def _create_smart_window(
        self,
        sentence_words: List[Dict[str, Any]],
        current_time: float
    ) -> List[Dict[str, Any]]:
        """Create a smart 3-word window similar to the current implementation."""
        
        if not sentence_words:
            return []
        
        # Find the currently spoken word in the sentence
        current_idx = -1
        for i, word in enumerate(sentence_words):
            if word['start_time'] <= current_time < word['end_time']:
                current_idx = i
                break
        
        if current_idx == -1:
            return []
        
        sentence_length = len(sentence_words)
        
        # Use the same smart windowing logic from word_highlight_subtitles.py
        if sentence_length <= 3:
            return sentence_words
        
        if current_idx == 0:
            # Beginning of sentence
            return sentence_words[0:min(sentence_length, 3)]
        elif current_idx == sentence_length - 1:
            # End of sentence
            return sentence_words[max(0, sentence_length - 3):sentence_length]
        else:
            # Middle of sentence - center the current word
            start_idx = max(0, current_idx - 1)
            end_idx = min(sentence_length, start_idx + 3)
            if end_idx - start_idx < 3:
                start_idx = max(0, end_idx - 3)
            return sentence_words[start_idx:end_idx]
    
    def _draw_word_window(
        self,
        draw: ImageDraw.ImageDraw,
        window_words: List[Dict[str, Any]],
        current_time: float,
        config: Dict[str, Any],
        font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
        img_size: Tuple[int, int]
    ):
        """Draw the word window onto the frame image."""
        
        if not window_words:
            return
        
        # Configuration
        default_color = config.get('default_color', '#FFFFFF')
        highlight_color = config.get('highlight_color', '#FF0000')
        stroke_color = config.get('stroke_color', '#000000')
        stroke_width = config.get('stroke_width', 2)
        background_color = config.get('background_color', '#000000')
        background_opacity = config.get('background_opacity', 0.0)
        padding_x = config.get('padding_x', 16)
        padding_y = config.get('padding_y', 12)
        position = config.get('position', 'center,bottom')
        
        # Calculate text layout
        word_spacing = 10
        word_infos = []
        total_width = 0
        max_height = 0
        
        # First pass: measure all words
        for word_data in window_words:
            word_text = word_data['word'].strip()
            is_highlighted = (word_data['start_time'] <= current_time < word_data['end_time'])
            color = highlight_color if is_highlighted else default_color
            
            # Get text dimensions
            try:
                bbox = draw.textbbox((0, 0), word_text, font=font)
                word_width = bbox[2] - bbox[0]
                word_height = bbox[3] - bbox[1]
            except AttributeError:
                # Fallback for older Pillow versions
                try:
                    textsize_result = getattr(draw, 'textsize', None)
                    if textsize_result:
                        word_width, word_height = textsize_result(word_text, font=font)
                    else:
                        raise AttributeError("textsize not available")
                except AttributeError:
                    # Ultimate fallback - rough estimation
                    font_size = getattr(font, 'size', 20)
                    word_width = len(word_text) * (font_size * 0.6)
                    word_height = font_size
            
            word_infos.append({
                'text': word_text,
                'width': word_width,
                'height': word_height,
                'color': color,
                'is_highlighted': is_highlighted
            })
            
            total_width += word_width
            max_height = max(max_height, word_height)
        
        # Add spacing between words
        total_width += word_spacing * max(0, len(word_infos) - 1)
        
        # Draw background if needed
        if background_opacity > 0:
            bg_width = total_width + 2 * padding_x
            bg_height = max_height + 2 * padding_y
            
            # Calculate background position
            bg_x, bg_y = self._calculate_position(
                position, img_size, (bg_width, bg_height)
            )
            
            # Create background with transparency
            bg_color = self._hex_to_rgba(background_color, background_opacity)
            
            # Draw background rectangle
            draw.rectangle(
                [(bg_x, bg_y), (bg_x + bg_width, bg_y + bg_height)],
                fill=bg_color
            )
            
            # Text starts inside the background
            text_start_x = bg_x + padding_x
            text_start_y = bg_y + padding_y
        else:
            # No background - center text directly
            text_start_x, text_start_y = self._calculate_position(
                position, img_size, (int(total_width), int(max_height))
            )
        
        # Draw words
        current_x = text_start_x
        for word_info in word_infos:
            # Draw text with stroke if needed
            if stroke_width > 0:
                # Draw stroke
                stroke_rgb = self._hex_to_rgb(stroke_color)
                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text(
                                (current_x + dx, text_start_y + dy),
                                word_info['text'],
                                font=font,
                                fill=stroke_rgb
                            )
            
            # Draw main text
            main_color = self._hex_to_rgb(word_info['color'])
            draw.text(
                (current_x, text_start_y),
                word_info['text'],
                font=font,
                fill=main_color
            )
            
            current_x += word_info['width'] + word_spacing
    
    def _calculate_position(
        self,
        position: str,
        img_size: Tuple[int, int],
        content_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Calculate position based on position string."""
        
        img_width, img_height = img_size
        content_width, content_height = content_size
        
        try:
            parts = [p.strip().lower() for p in position.split(',')]
            horizontal = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom') else 'bottom'
            
            # Calculate horizontal position
            if horizontal == 'left':
                x = int(0.10 * img_width) - (content_width // 2)
            elif horizontal == 'right':
                x = int(0.90 * img_width) - (content_width // 2)
            else:  # center
                x = (img_width - content_width) // 2
            
            # Calculate vertical position
            if vertical == 'top':
                y = int(0.15 * img_height) - (content_height // 2)
            elif vertical == 'center':
                y = (img_height - content_height) // 2
            else:  # bottom
                y = int(0.85 * img_height) - content_height
            
            # Ensure within bounds
            x = max(0, min(x, img_width - content_width))
            y = max(0, min(y, img_height - content_height))
            
            return (x, y)
            
        except Exception as e:
            print(f"Position calculation error: {e}")
            # Default to center-bottom
            return (
                (img_width - content_width) // 2,
                int(0.85 * img_height) - content_height
            )
    
    def _load_font(self, config: Dict[str, Any]) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """Load font for text rendering using centralized font utility."""

        font_size = max(24, int(self.video_height * (config.get('font_size', 48) / 1000)))

        # Use centralized font fallback list
        font_fallback_list = get_font_fallback_list()

        for font_path in font_fallback_list:
            try:
                if font_path is None:
                    return ImageFont.load_default()
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                continue

        # Fallback to default font
        return ImageFont.load_default()
    

    
    def _group_words_by_sentences(
        self,
        word_timings: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Group words by sentence index."""
        
        sentences = {}
        for word in word_timings:
            sentence_idx = word.get('sentence_index', 0)
            if sentence_idx not in sentences:
                sentences[sentence_idx] = []
            sentences[sentence_idx].append(word)
        
        return sentences
    
    def _create_empty_clip(self, duration: float) -> ImageSequenceClip:
        """Create an empty transparent clip."""
        
        frames = []
        total_frames = max(1, int(duration * self.fps))
        
        empty_frame = Image.new('RGBA', (self.video_width, self.video_height), (0, 0, 0, 0))
        empty_array = np.array(empty_frame)
        
        for _ in range(total_frames):
            frames.append(empty_array.copy())
        
        return ImageSequenceClip(frames, fps=self.fps)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (255, 255, 255)  # Default to white
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except ValueError:
            return (255, 255, 255)
    
    def _hex_to_rgba(self, hex_color: str, opacity: float) -> Tuple[int, int, int, int]:
        """Convert hex color to RGBA tuple with opacity."""
        r, g, b = self._hex_to_rgb(hex_color)
        alpha = int(opacity * 255)
        return (r, g, b, alpha)


def create_optimized_subtitle_clip_from_file(
    subtitle_path: str,
    video_size: Tuple[int, int],
    fps: float,
    duration: float
) -> ImageSequenceClip:
    """
    Create optimized subtitle clip from enhanced subtitle file.
    
    Args:
        subtitle_path: Path to the enhanced subtitle JSON file
        video_size: Video dimensions (width, height)
        fps: Video frame rate
        duration: Total video duration in seconds
        
    Returns:
        ImageSequenceClip with pre-rendered subtitle animation
    """
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            subtitle_data = json.load(f)
        
        renderer = OptimizedSubtitleRenderer(video_size, fps)
        return renderer.create_optimized_subtitle_clip(subtitle_data, duration)
        
    except Exception as e:
        print(f"Error creating optimized subtitles: {e}")
        # Return empty clip on error
        renderer = OptimizedSubtitleRenderer(video_size, fps)
        return renderer._create_empty_clip(duration)
