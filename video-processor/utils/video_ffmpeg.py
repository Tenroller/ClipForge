"""
FFmpeg utilities for video processing with subtitles
Provides functions for subtitle burning and video info extraction
"""
import subprocess
import json
import os
from typing import Tuple, Optional
from loguru import logger


def get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using ffprobe
    
    Args:
        video_path: Path to video file
        
    Returns:
        Duration in seconds
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to get video duration: {e}")


def get_video_dimensions(video_path: str) -> Tuple[int, int]:
    """
    Get video dimensions (width, height) using ffprobe
    
    Args:
        video_path: Path to video file
        
    Returns:
        Tuple of (width, height)
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "v:0",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError, IndexError) as e:
        # Default to 1080p if detection fails
        logger.warning(f"Failed to get video dimensions, defaulting to 1920x1080: {e}")
        return 1920, 1080


def burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    use_gpu: bool = False,
    preset: str = "fast",
    crf: int = 23
) -> bool:
    """
    Burn ASS subtitles into video using FFmpeg
    
    Args:
        video_path: Path to input video
        subtitle_path: Path to ASS subtitle file
        output_path: Path for output video
        use_gpu: Use GPU acceleration (NVENC) if available
        preset: Encoding preset (ultrafast, fast, medium, slow)
        crf: Quality level (lower = better, 18-28 is reasonable range)
    
    Returns:
        True if successful, False otherwise
    """
    # Escape special characters in subtitle path for FFmpeg filter
    # FFmpeg filter syntax requires escaping colons, backslashes, etc.
    escaped_subtitle_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
    
    # Build FFmpeg command
    if use_gpu:
        # Try NVENC GPU encoding
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-hwaccel", "cuda",
            "-i", video_path,
            "-vf", f"ass='{escaped_subtitle_path}'",
            "-c:a", "copy",  # Copy audio without re-encoding
            "-c:v", "h264_nvenc",  # NVIDIA GPU encoder
            "-preset", preset,
            "-cq", str(crf),  # NVENC uses -cq instead of -crf
            output_path
        ]
    else:
        # CPU encoding with libx264
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", video_path,
            "-vf", f"ass='{escaped_subtitle_path}'",
            "-c:a", "copy",  # Copy audio without re-encoding
            "-c:v", "libx264",  # Re-encode video with x264
            "-preset", preset,  # Balance between speed and quality
            "-crf", str(crf),  # Good quality (lower = better)
            output_path
        ]
    
    try:
        logger.info(f"Burning subtitles: {subtitle_path} -> {output_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Subtitle burning completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        # If GPU failed, try CPU fallback
        if use_gpu:
            logger.warning(f"GPU encoding failed, falling back to CPU: {e.stderr}")
            return burn_subtitles(video_path, subtitle_path, output_path, 
                                  use_gpu=False, preset=preset, crf=crf)
        else:
            logger.error(f"FFmpeg subtitle burning failed: {e.stderr}")
            return False


def extract_audio(video_path: str, audio_path: str, sample_rate: int = 16000) -> bool:
    """
    Extract audio from video for transcription
    
    Args:
        video_path: Path to input video
        audio_path: Path for output audio (WAV format recommended)
        sample_rate: Sample rate in Hz (16000 is optimal for Whisper)
    
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # WAV format
        "-ar", str(sample_rate),  # Sample rate
        "-ac", "1",  # Mono
        audio_path
    ]
    
    try:
        logger.info(f"Extracting audio: {video_path} -> {audio_path}")
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("Audio extraction completed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Audio extraction failed: {e.stderr}")
        return False


def burn_subtitles_to_clip(
    clip_path: str,
    word_timings: list,
    output_path: str,
    style: str = "yellow_highlight",
    display_mode: str = "word",
    position: str = "bottom",
    text_color: Optional[str] = None,
    highlight_color: Optional[str] = None,
    temp_dir: Optional[str] = None,
    use_gpu: bool = False
) -> bool:
    """
    High-level function to generate subtitles and burn them into a video clip.
    
    Args:
        clip_path: Path to input video clip
        word_timings: List of word timing dicts from Whisper
        output_path: Path for output video with subtitles
        style: Subtitle style (yellow_highlight, multicolor_pop, clean_outline)
        display_mode: word or sentence
        position: top, center, or bottom
        text_color: Custom text color in hex (#FFFFFF)
        highlight_color: Custom highlight color in hex (#FFD700)
        temp_dir: Directory for temporary ASS file
        use_gpu: Use GPU acceleration
    
    Returns:
        True if successful, False otherwise
    """
    from utils.subtitle_generator import (
        SubtitleGenerator, SubtitleStyle, DisplayMode, Position,
        word_timings_to_segments
    )
    
    # Get video dimensions
    width, height = get_video_dimensions(clip_path)
    
    # Convert word timings to segments
    segments = word_timings_to_segments(word_timings)
    
    if not segments:
        logger.warning("No segments generated from word timings")
        return False
    
    # Create subtitle generator
    try:
        subtitle_style = SubtitleStyle(style)
        subtitle_display_mode = DisplayMode(display_mode)
        subtitle_position = Position(position)
    except ValueError as e:
        logger.error(f"Invalid subtitle option: {e}")
        return False
    
    generator = SubtitleGenerator(
        style=subtitle_style,
        display_mode=subtitle_display_mode,
        position=subtitle_position,
        text_color=text_color,
        highlight_color=highlight_color
    )
    
    # Generate ASS file
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        ass_path = os.path.join(temp_dir, "subtitles.ass")
    else:
        ass_path = output_path.replace(".mp4", ".ass")
    
    generator.generate(segments, ass_path, width, height)
    logger.info(f"Generated ASS subtitle file: {ass_path}")
    
    # Burn subtitles
    success = burn_subtitles(clip_path, ass_path, output_path, use_gpu=use_gpu)
    
    # Cleanup temp ASS file if using temp dir
    if temp_dir and os.path.exists(ass_path):
        try:
            os.remove(ass_path)
        except OSError:
            pass
    
    return success
