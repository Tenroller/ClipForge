"""
FFmpeg utilities for cross-platform compatibility.
"""
import os
import platform
import shutil
from loguru import logger

# Bind logger with context for this module
logger = logger.bind(name="utils.ffmpeg")

def setup_ffmpeg_environment():
    """
    Set up FFmpeg and FFprobe environment variables for cross-platform compatibility.
    
    This function:
    1. Tries to find ffmpeg/ffprobe in system PATH first
    2. Falls back to Windows-specific paths on Windows
    3. Uses system commands on Unix-like systems
    
    Returns:
        tuple: (ffmpeg_path, ffprobe_path) or (None, None) if not found
    """
    ffmpeg_path = None
    ffprobe_path = None
    
    # Set up FFmpeg binary
    if "FFMPEG_BINARY" not in os.environ:
        # Try to find ffmpeg in system PATH first
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            os.environ["FFMPEG_BINARY"] = ffmpeg_path
            logger.info(f"Found FFmpeg at: {ffmpeg_path}")
        elif platform.system() == "Windows":
            os.environ["FFMPEG_BINARY"] = r'C:\ffmpeg\bin\ffmpeg.exe'
            logger.info("Using Windows FFmpeg path: C:\\ffmpeg\\bin\\ffmpeg.exe")
        else:
            # Default to system command for Unix-like systems
            os.environ["FFMPEG_BINARY"] = "ffmpeg"
            logger.info("Using system FFmpeg command")
    else:
        ffmpeg_path = os.environ["FFMPEG_BINARY"]
        logger.info(f"Using existing FFmpeg path: {ffmpeg_path}")
    
    # Set up FFprobe binary
    if "FFPROBE_BINARY" not in os.environ:
        # Try to find ffprobe in system PATH first
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            os.environ["FFPROBE_BINARY"] = ffprobe_path
            logger.info(f"Found FFprobe at: {ffprobe_path}")
        elif platform.system() == "Windows":
            os.environ["FFPROBE_BINARY"] = r'C:\ffmpeg\bin\ffprobe.exe'
            logger.info("Using Windows FFprobe path: C:\\ffmpeg\\bin\\ffprobe.exe")
        else:
            # Default to system command for Unix-like systems
            os.environ["FFPROBE_BINARY"] = "ffprobe"
            logger.info("Using system FFprobe command")
    else:
        ffprobe_path = os.environ["FFPROBE_BINARY"]
        logger.info(f"Using existing FFprobe path: {ffprobe_path}")
    
    # Set FFmpeg 7+ compatibility flags
    os.environ["FFMPEG_7_COMPAT"] = "1"
    os.environ["FFMPEG_DISABLE_SHOW_FORMAT"] = "1"
    
    return ffmpeg_path, ffprobe_path

def verify_ffmpeg_installation():
    """
    Verify that FFmpeg and FFprobe are properly installed and accessible.
    
    Returns:
        dict: Status of FFmpeg and FFprobe availability
    """
    status = {
        "ffmpeg_available": False,
        "ffprobe_available": False,
        "ffmpeg_path": None,
        "ffprobe_path": None,
        "error": None
    }
    
    try:
        # Check FFmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            status["ffmpeg_available"] = True
            status["ffmpeg_path"] = ffmpeg_path
        
        # Check FFprobe
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            status["ffprobe_available"] = True
            status["ffprobe_path"] = ffprobe_path
            
        if not status["ffmpeg_available"] or not status["ffprobe_available"]:
            missing = []
            if not status["ffmpeg_available"]:
                missing.append("ffmpeg")
            if not status["ffprobe_available"]:
                missing.append("ffprobe")
            status["error"] = f"Missing: {', '.join(missing)}"
            
    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Error verifying FFmpeg installation: {e}")
    
    return status
