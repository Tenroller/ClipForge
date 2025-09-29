"""
Centralized font management utilities.

This module provides standardized font detection, loading, and management
functions used throughout the VideoHelper application.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union
from ..logging_config import get_logger

logger = get_logger("font_utils")


class FontManager:
    """Centralized font management system."""

    def __init__(self):
        self.system_font_paths: List[Path] = []
        self.custom_font_paths: List[Path] = []
        self._font_cache: Dict[str, Path] = {}
        self._fallback_fonts: List[str] = []
        self._scan_system_fonts()

    def _scan_system_fonts(self):
        """Scan for system fonts."""
        system_font_dirs = []

        # Windows font directories
        if sys.platform == "win32":
            system_font_dirs = [
                Path("C:/Windows/Fonts"),
                Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
            ]

        # macOS font directories
        elif sys.platform == "darwin":
            system_font_dirs = [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts",
            ]

        # Linux font directories
        else:
            system_font_dirs = [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
            ]

        # Scan font directories
        for font_dir in system_font_dirs:
            if font_dir.exists():
                self.system_font_paths.append(font_dir)
                self._scan_font_directory(font_dir)

        logger.info(f"Scanned {len(self.system_font_paths)} system font directories")

    def _scan_font_directory(self, font_dir: Path):
        """Scan a font directory for font files."""
        font_extensions = {'.ttf', '.otf', '.woff', '.woff2'}

        try:
            for font_file in font_dir.rglob("*"):
                if font_file.is_file() and font_file.suffix.lower() in font_extensions:
                    font_name = font_file.stem
                    if font_name not in self._font_cache:
                        self._font_cache[font_name] = font_file
        except Exception as e:
            logger.warning(f"Error scanning font directory {font_dir}: {e}")

    def add_custom_font_path(self, font_path: Union[str, Path]):
        """Add a custom font path."""
        path = Path(font_path)
        if path.exists():
            if path.is_file():
                self.custom_font_paths.append(path.parent)
                font_name = path.stem
                self._font_cache[font_name] = path
            elif path.is_dir():
                self.custom_font_paths.append(path)
                self._scan_font_directory(path)

            logger.info(f"Added custom font path: {path}")

    def get_font_path(self, font_name: str) -> Optional[Path]:
        """
        Get the path to a font file.

        Args:
            font_name: Name of the font (without extension)

        Returns:
            Path to font file or None if not found
        """
        # Check cache first
        if font_name in self._font_cache:
            return self._font_cache[font_name]

        # Search for font
        font_extensions = ['.ttf', '.otf', '.woff', '.woff2']

        # Search custom font paths first
        for font_dir in self.custom_font_paths:
            for ext in font_extensions:
                font_path = font_dir / f"{font_name}{ext}"
                if font_path.exists():
                    self._font_cache[font_name] = font_path
                    return font_path

        # Search system font paths
        for font_dir in self.system_font_paths:
            for ext in font_extensions:
                font_path = font_dir / f"{font_name}{ext}"
                if font_path.exists():
                    self._font_cache[font_name] = font_path
                    return font_path

        return None

    def get_fallback_font_list(self) -> List[str]:
        """
        Get a list of fallback fonts for the current system.

        Returns:
            List of font names in order of preference
        """
        if self._fallback_fonts:
            return self._fallback_fonts.copy()

        # Define fallback fonts by platform
        if sys.platform == "win32":
            fallbacks = [
                "Arial", "Arial-Bold", "Arial-Black",
                "Calibri", "Calibri-Bold",
                "Segoe UI", "Segoe UI Bold",
                "Tahoma", "Tahoma Bold",
                "Verdana", "Verdana Bold"
            ]
        elif sys.platform == "darwin":
            fallbacks = [
                "Helvetica", "Helvetica-Bold",
                "System Font", "System Font Bold",
                "San Francisco", "San Francisco Bold",
                "Arial", "Arial-Bold"
            ]
        else:  # Linux and others
            fallbacks = [
                "DejaVu Sans", "DejaVu Sans Bold",
                "Liberation Sans", "Liberation Sans Bold",
                "Ubuntu", "Ubuntu Bold",
                "Arial", "Arial-Bold"
            ]

        # Filter to only fonts that exist on this system
        available_fallbacks = []
        for font_name in fallbacks:
            if self.get_font_path(font_name):
                available_fallbacks.append(font_name)

        # Add generic fallbacks if no specific fonts found
        if not available_fallbacks:
            available_fallbacks = ["sans-serif", "serif", "monospace"]

        self._fallback_fonts = available_fallbacks
        return available_fallbacks.copy()

    def validate_font(self, font_name: str) -> Tuple[bool, str]:
        """
        Validate if a font is available.

        Args:
            font_name: Font name to validate

        Returns:
            Tuple of (is_valid, actual_font_name)
        """
        font_path = self.get_font_path(font_name)
        if font_path:
            return True, font_name

        # Try to find a similar font
        fallback_fonts = self.get_fallback_font_list()
        if fallback_fonts:
            logger.warning(f"Font '{font_name}' not found, using fallback '{fallback_fonts[0]}'")
            return False, fallback_fonts[0]

        logger.warning(f"Font '{font_name}' not found and no fallbacks available")
        return False, "sans-serif"

    def get_font_info(self, font_name: str) -> Optional[Dict]:
        """
        Get information about a font.

        Args:
            font_name: Font name

        Returns:
            Dictionary with font information or None if not found
        """
        font_path = self.get_font_path(font_name)
        if not font_path:
            return None

        try:
            stat = font_path.stat()
            return {
                'name': font_name,
                'path': str(font_path),
                'size_bytes': stat.st_size,
                'modified': stat.st_mtime,
                'exists': True
            }
        except Exception:
            return None

    def list_available_fonts(self, limit: int = 50) -> List[Dict]:
        """
        List available fonts.

        Args:
            limit: Maximum number of fonts to return

        Returns:
            List of font information dictionaries
        """
        fonts = []
        for font_name, font_path in list(self._font_cache.items())[:limit]:
            info = self.get_font_info(font_name)
            if info:
                fonts.append(info)

        return fonts

    def clear_cache(self):
        """Clear the font cache."""
        self._font_cache.clear()
        self._fallback_fonts.clear()
        logger.info("Font cache cleared")


# Global font manager instance
_font_manager: Optional[FontManager] = None


def get_font_manager() -> FontManager:
    """Get or create the global font manager."""
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager


def init_font_manager():
    """Initialize the font manager."""
    manager = get_font_manager()

    # Add VideoHelper-specific font directories
    videhelper_fonts = Path(__file__).resolve().parent.parent / "vendors" / "fonts"
    if videhelper_fonts.exists():
        manager.add_custom_font_path(videhelper_fonts)

    logger.info("Font manager initialized")


def get_font_fallback_list() -> List[str]:
    """
    Get the system font fallback list.

    This is a convenience function for backward compatibility.
    """
    return get_font_manager().get_fallback_font_list()


def validate_font_name(font_name: str) -> str:
    """
    Validate and get the actual font name to use.

    Args:
        font_name: Requested font name

    Returns:
        Actual font name that should be used
    """
    is_valid, actual_font = get_font_manager().validate_font(font_name)
    return actual_font


def get_font_path(font_name: str) -> Optional[Path]:
    """
    Get the path to a font file.

    Args:
        font_name: Font name

    Returns:
        Path to font file or None if not found
    """
    return get_font_manager().get_font_path(font_name)


def setup_moviepy_fonts():
    """Setup MoviePy with proper font paths."""
    try:
        # Get the primary font path
        fallback_fonts = get_font_fallback_list()
        if fallback_fonts:
            primary_font = fallback_fonts[0]
            font_path = get_font_path(primary_font)

            if font_path:
                # Set environment variable for MoviePy
                os.environ['MOVIEPY_FONT'] = str(font_path)
                logger.info(f"Set MoviePy font to: {font_path}")

                # Also try to set ImageMagick font path if available
                try:
                    from PIL import ImageFont
                    ImageFont.truetype(str(font_path))
                    logger.info("PIL ImageFont can load the font successfully")
                except Exception as e:
                    logger.warning(f"PIL ImageFont cannot load font: {e}")

    except Exception as e:
        logger.warning(f"Failed to setup MoviePy fonts: {e}")


# Initialize font manager when module is imported
try:
    init_font_manager()
    setup_moviepy_fonts()
except Exception as e:
    logger.error(f"Failed to initialize font system: {e}")
