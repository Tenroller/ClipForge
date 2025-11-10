
"""
Font detection utility for cross-platform font availability.
"""

import os
import platform
from pathlib import Path
from typing import List, Set, Optional, Union
try:
    from .logging_config import get_logger
except ImportError:
    # Fallback logger if logging_config is not available
    from loguru import logger as fallback_logger
    def get_logger(name):
        return fallback_logger.bind(name=name)

logger = get_logger("font_detection")

# Centralized font configuration
DEFAULT_FONT_PATH = Path(__file__).resolve().parent / "vendors" / "fonts" / "EpundaSlab-VariableFont_wght.ttf"
DEFAULT_FONT_SIZE = 48


def get_system_fonts() -> List[str]:
    """
    Get a list of available fonts on the current system.
    
    Returns:
        List of font names/paths available on the system
    """
    available_fonts = set()
    system = platform.system().lower()
    
    # Common font directories by platform
    font_dirs = []
    
    if system == "darwin":  # macOS
        font_dirs = [
            "/System/Library/Fonts",
            "/Library/Fonts", 
            "~/Library/Fonts",
            "/System/Library/Assets/com_apple_MobileAsset_Font6"
        ]
    elif system == "windows":  # Windows
        font_dirs = [
            "C:/Windows/Fonts",
            "C:/Windows/System32/Fonts",
            os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
            os.path.expanduser("~/AppData/Roaming/Microsoft/Windows/Fonts")
        ]
    elif system == "linux":  # Linux
        font_dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "~/.local/share/fonts",
            "~/.fonts",
            "/usr/X11R6/lib/X11/fonts"
        ]
    
    # Scan font directories
    for font_dir in font_dirs:
        font_path = Path(font_dir).expanduser()
        if font_path.exists():
            for font_file in font_path.rglob("*"):
                if font_file.is_file() and font_file.suffix.lower() in ['.ttf', '.otf', '.ttc']:
                    # Extract font name from filename
                    font_name = font_file.stem
                    available_fonts.add(font_name)
    
    # Add common system font names
    common_fonts = {
        "Arial", "Arial-Bold", "Arial Bold", "Helvetica", "Helvetica-Bold", 
        "Times", "Times-Bold", "Times New Roman", "Courier", "Courier New",
        "Impact", "Comic Sans MS", "Verdana", "Georgia", "Tahoma",
        "Trebuchet MS", "Palatino", "Garamond", "Bookman", "Avant Garde"
    }
    
    # Add platform-specific system fonts
    if system == "darwin":  # macOS
        common_fonts.update({
            "SF Pro Display", "SF Pro Text", ".SF NS Display", ".AppleSystemUIFont",
            "Helvetica Neue", "Lucida Grande", "Monaco", "Menlo", "Avenir",
            "Optima", "Gill Sans", "Futura", "Baskerville"
        })
    elif system == "windows":  # Windows  
        common_fonts.update({
            "Segoe UI", "Calibri", "Cambria", "Consolas", "Corbel", "Franklin Gothic",
            "Lucida Console", "Microsoft Sans Serif", "MS Gothic", "MS Sans Serif"
        })
    elif system == "linux":  # Linux
        common_fonts.update({
            "Liberation Sans", "Liberation Serif", "Liberation Mono",
            "DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono",
            "Ubuntu", "Ubuntu Mono", "Droid Sans", "Noto Sans",
            "FreeSans", "FreeSerif", "FreeMono"
        })
    
    available_fonts.update(common_fonts)
    
    return sorted(list(available_fonts))


def test_font_availability(font_list: List[str]) -> List[str]:
    """
    Test which fonts from a list are actually working with MoviePy.
    
    Args:
        font_list: List of font names to test
        
    Returns:
        List of fonts that work with MoviePy
    """
    working_fonts = []
    
    # Try to import MoviePy
    try:
        from moviepy import TextClip
    except ImportError:
        logger.warning("MoviePy not available for font testing")
        return font_list
    # Test each font by attempting to create a small TextClip
    for font in font_list:
        try:
            test_clip = TextClip("Test", font=font, font_size=20)
            working_fonts.append(font)
            logger.info(f"✅ Font '{font}' works")
        except Exception as e:
            logger.error(f"❌ Font '{font}' failed: {e}")
    return working_fonts


if __name__ == "__main__":
    logger.info("=== System Font Detection ===")
    fonts = get_system_fonts()
    logger.info(f"Found {len(fonts)} potential fonts on system:")
    for font in fonts[:20]:  # Show first 20
        logger.info(f"  - {font}")
    if len(fonts) > 20:
        logger.info(f"  ... and {len(fonts) - 20} more")
    # Test common subtitle fonts
    logger.info("\n=== Testing Common Subtitle Fonts ===")
    common_subtitle_fonts = [
        "Arial-Bold", "Arial", "Helvetica-Bold", "Impact", 
        "Times-Bold", "Comic Sans MS", "Montserrat", "Roboto"
    ]
    working = test_font_availability(common_subtitle_fonts)
    logger.info(f"\n✅ {len(working)} out of {len(common_subtitle_fonts)} common fonts work:")
    for font in working:
        logger.info(f"  - {font}")


def get_default_font_path() -> Optional[str]:
    """
    Get the path to the default font file.

    Returns:
        Path to the default font file, or None if not found
    """
    if DEFAULT_FONT_PATH.exists():
        return str(DEFAULT_FONT_PATH)
    else:
        logger.warning(f"Default font file not found at {DEFAULT_FONT_PATH}")
        return None


def get_font_fallback_list() -> List[Optional[str]]:
    """
    Get the complete font fallback list, prioritizing the default font.

    Returns:
        List of font paths/names to try, with None as final fallback
    """
    fallback_list = []

    # Try the default font first
    default_font_path = get_default_font_path()
    if default_font_path:
        fallback_list.append(default_font_path)
        logger.info(f"✅ Using default font: {default_font_path}")

    # System font fallbacks
    system_fallbacks = [
        "EpundaSlab-VariableFont_wght.ttf",  # Direct filename
        "EpundaSlab.ttf",  # Alternative name
        "Arial-Bold",
        "Arial",
        "Helvetica-Bold",
        "Helvetica",
        "Liberation Sans Bold",
        "DejaVu Sans Bold",
        None  # MoviePy default
    ]

    fallback_list.extend(system_fallbacks)
    return fallback_list


def get_font_for_textclip() -> Optional[str]:
    """
    Get the font to use for TextClip creation, prioritizing the default font.

    Returns:
        Font name/path for TextClip, or None for default
    """
    default_font_path = get_default_font_path()
    if default_font_path:
        return default_font_path

    # Fallback to system fonts
    return "Arial-Bold"
