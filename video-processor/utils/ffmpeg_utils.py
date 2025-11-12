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
    2. Checks common installation locations (Homebrew, apt, etc.)
    3. Falls back to Windows-specific paths on Windows
    4. Adds FFmpeg directory to PATH if found

    Returns:
        tuple: (ffmpeg_path, ffprobe_path) or (None, None) if not found
    """
    ffmpeg_path = None
    ffprobe_path = None

    # Common FFmpeg installation paths to check
    common_paths = [
        "/opt/homebrew/bin",  # Homebrew on Apple Silicon
        "/usr/local/bin",     # Homebrew on Intel Mac, Linux
        "/usr/bin",           # System package managers
        "/bin",               # Some Linux distros
    ]

    # Set up FFmpeg binary
    if "FFMPEG_BINARY" not in os.environ:
        # Try to find ffmpeg in system PATH first
        ffmpeg_path = shutil.which("ffmpeg")

        # If not in PATH, check common installation locations
        if not ffmpeg_path:
            for common_path in common_paths:
                candidate = os.path.join(common_path, "ffmpeg")
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffmpeg_path = candidate
                    logger.info(f"Found FFmpeg in common location: {ffmpeg_path}")
                    break

        if ffmpeg_path:
            os.environ["FFMPEG_BINARY"] = ffmpeg_path
            logger.info(f"Using FFmpeg at: {ffmpeg_path}")

            # Add FFmpeg directory to PATH if not already there
            # This ensures libraries like stable-ts can find ffmpeg
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
                logger.info(f"Added {ffmpeg_dir} to PATH")
        elif platform.system() == "Windows":
            os.environ["FFMPEG_BINARY"] = r'C:\ffmpeg\bin\ffmpeg.exe'
            logger.info("Using Windows FFmpeg path: C:\\ffmpeg\\bin\\ffmpeg.exe")
            # Add Windows ffmpeg to PATH
            ffmpeg_dir = r'C:\ffmpeg\bin'
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
        else:
            logger.warning("FFmpeg not found in PATH or common locations")
    else:
        ffmpeg_path = os.environ["FFMPEG_BINARY"]
        logger.info(f"Using existing FFmpeg path: {ffmpeg_path}")
    
    # Set up FFprobe binary
    if "FFPROBE_BINARY" not in os.environ:
        # Try to find ffprobe in system PATH first
        ffprobe_path = shutil.which("ffprobe")

        # If not in PATH, check common installation locations
        if not ffprobe_path:
            for common_path in common_paths:
                candidate = os.path.join(common_path, "ffprobe")
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffprobe_path = candidate
                    logger.info(f"Found FFprobe in common location: {ffprobe_path}")
                    break

        if ffprobe_path:
            os.environ["FFPROBE_BINARY"] = ffprobe_path
            logger.info(f"Using FFprobe at: {ffprobe_path}")

            # Add FFprobe directory to PATH if not already there
            ffprobe_dir = os.path.dirname(ffprobe_path)
            current_path = os.environ.get("PATH", "")
            if ffprobe_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = f"{ffprobe_dir}{os.pathsep}{current_path}"
                logger.info(f"Added {ffprobe_dir} to PATH")
        elif platform.system() == "Windows":
            os.environ["FFPROBE_BINARY"] = r'C:\ffmpeg\bin\ffprobe.exe'
            logger.info("Using Windows FFprobe path: C:\\ffmpeg\\bin\\ffprobe.exe")
        else:
            logger.warning("FFprobe not found in PATH or common locations")
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
        # Check FFmpeg - first try PATH, then check environment variable
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path and "FFMPEG_BINARY" in os.environ:
            # Check if the environment variable points to a valid file
            candidate = os.environ["FFMPEG_BINARY"]
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                ffmpeg_path = candidate

        if ffmpeg_path:
            status["ffmpeg_available"] = True
            status["ffmpeg_path"] = ffmpeg_path

        # Check FFprobe - first try PATH, then check environment variable
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path and "FFPROBE_BINARY" in os.environ:
            # Check if the environment variable points to a valid file
            candidate = os.environ["FFPROBE_BINARY"]
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                ffprobe_path = candidate

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
