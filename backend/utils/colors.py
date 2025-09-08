"""
Centralized color conversion utilities.

This module provides standardized color conversion functions
used throughout the VideoHelper application.
"""

from typing import Tuple, Union, Optional
import re


def hex_to_rgb(hex_color: Union[str, int]) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#FF0000", "FF0000") or integer

    Returns:
        RGB tuple (r, g, b) where each value is 0-255

    Examples:
        >>> hex_to_rgb("#FF0000")
        (255, 0, 0)
        >>> hex_to_rgb("00FF00")
        (0, 255, 0)
        >>> hex_to_rgb(0x0000FF)
        (0, 0, 255)
    """
    if isinstance(hex_color, int):
        # Handle integer color values
        r = (hex_color >> 16) & 0xFF
        g = (hex_color >> 8) & 0xFF
        b = hex_color & 0xFF
        return (r, g, b)

    if not isinstance(hex_color, str):
        return (255, 255, 255)  # Default to white

    # Remove # prefix if present
    hex_color = hex_color.lstrip('#')

    # Handle different hex formats
    if len(hex_color) == 3:
        # Short format like "RGB" -> "RRGGBB"
        hex_color = ''.join(c * 2 for c in hex_color)
    elif len(hex_color) == 6:
        # Standard format "RRGGBB"
        pass
    elif len(hex_color) == 8:
        # With alpha "RRGGBBAA" - ignore alpha
        hex_color = hex_color[:6]
    else:
        return (255, 255, 255)  # Invalid format, return white

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except (ValueError, IndexError):
        return (255, 255, 255)  # Invalid hex, return white


def rgb_to_hex(r: int, g: int, b: int, include_hash: bool = True) -> str:
    """
    Convert RGB values to hex color string.

    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        include_hash: Whether to include # prefix

    Returns:
        Hex color string

    Examples:
        >>> rgb_to_hex(255, 0, 0)
        '#FF0000'
        >>> rgb_to_hex(0, 255, 0, include_hash=False)
        '00FF00'
    """
    # Clamp values to valid range
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    hex_str = f"{r:02X}{g:02X}{b:02X}"
    return f"#{hex_str}" if include_hash else hex_str


def hex_to_ass_color(hex_color: str) -> str:
    """
    Convert hex color to ASS subtitle format (&HAABBGGRR).

    Args:
        hex_color: Hex color string (e.g., "#FF0000")

    Returns:
        ASS color format string

    Examples:
        >>> hex_to_ass_color("#FF0000")
        '&H000000FF'
        >>> hex_to_ass_color("#00FF00")
        '&H0000FF00'
    """
    r, g, b = hex_to_rgb(hex_color)
    # ASS format: &HAABBGGRR (Alpha=00, Blue, Green, Red)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def ass_color_to_hex(ass_color: str) -> str:
    """
    Convert ASS color format to hex.

    Args:
        ass_color: ASS color string (e.g., "&H000000FF")

    Returns:
        Hex color string

    Examples:
        >>> ass_color_to_hex("&H000000FF")
        '#FF0000'
        >>> ass_color_to_hex("&H0000FF00")
        '#00FF00'
    """
    if not ass_color.startswith('&H'):
        return "#FFFFFF"

    # Extract BBGGRR from &HAABBGGRR
    color_part = ass_color[3:]  # Remove &H
    if len(color_part) < 6:
        return "#FFFFFF"

    try:
        # ASS format: AABBGGRR -> extract RRGGBB and convert to RGB
        rr = color_part[-2:]  # Last 2 chars are red
        gg = color_part[-4:-2]  # Next 2 are green
        bb = color_part[-6:-4]  # Next 2 are blue

        r = int(rr, 16)
        g = int(gg, 16)
        b = int(bb, 16)

        return rgb_to_hex(r, g, b)
    except (ValueError, IndexError):
        return "#FFFFFF"


def parse_color_string(color_str: str) -> Tuple[int, int, int]:
    """
    Parse various color string formats to RGB tuple.

    Supports:
    - Hex: #FF0000, FF0000, #RGB, RGB
    - RGB: rgb(255,0,0), rgb(255 0 0)
    - Named colors: red, blue, green, etc.

    Args:
        color_str: Color string in any supported format

    Returns:
        RGB tuple (r, g, b)
    """
    if not color_str:
        return (255, 255, 255)

    color_str = color_str.strip().lower()

    # Handle hex colors
    if color_str.startswith('#') or re.match(r'^[0-9a-f]{3,8}$', color_str):
        return hex_to_rgb(color_str)

    # Handle rgb() format
    rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*[,\s]\s*(\d+)\s*[,\s]\s*(\d+)\s*\)', color_str)
    if rgb_match:
        try:
            r = int(rgb_match.group(1))
            g = int(rgb_match.group(2))
            b = int(rgb_match.group(3))
            return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        except (ValueError, IndexError):
            pass

    # Handle named colors (basic set)
    named_colors = {
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'white': (255, 255, 255),
        'black': (0, 0, 0),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
    }

    return named_colors.get(color_str, (255, 255, 255))


def validate_color(color: str) -> str:
    """
    Validate and normalize color string.

    Args:
        color: Color string to validate

    Returns:
        Normalized hex color string, or default white if invalid

    Raises:
        ValueError: If color format is invalid
    """
    try:
        r, g, b = parse_color_string(color)
        return rgb_to_hex(r, g, b)
    except Exception:
        raise ValueError(f"Invalid color format: {color}")


def blend_colors(color1: str, color2: str, ratio: float = 0.5) -> str:
    """
    Blend two colors together.

    Args:
        color1: First color (hex)
        color2: Second color (hex)
        ratio: Blend ratio (0.0 = 100% color1, 1.0 = 100% color2)

    Returns:
        Blended color as hex string

    Examples:
        >>> blend_colors("#FF0000", "#0000FF", 0.5)
        '#800080'  # Purple (mix of red and blue)
    """
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)

    # Clamp ratio to valid range
    ratio = max(0.0, min(1.0, ratio))

    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)

    return rgb_to_hex(r, g, b)


def adjust_brightness(color: str, factor: float) -> str:
    """
    Adjust color brightness.

    Args:
        color: Hex color string
        factor: Brightness factor (< 1.0 = darker, > 1.0 = brighter)

    Returns:
        Adjusted color as hex string

    Examples:
        >>> adjust_brightness("#FF0000", 0.5)
        '#800000'  # Darker red
        >>> adjust_brightness("#FF0000", 2.0)
        '#FF0000'  # Red (clamped to max)
    """
    r, g, b = hex_to_rgb(color)

    r = int(min(255, max(0, r * factor)))
    g = int(min(255, max(0, g * factor)))
    b = int(min(255, max(0, b * factor)))

    return rgb_to_hex(r, g, b)


def get_contrast_color(background_color: str) -> str:
    """
    Get a contrasting text color for the given background.

    Args:
        background_color: Background color (hex)

    Returns:
        Contrasting text color (black or white)

    Examples:
        >>> get_contrast_color("#FFFFFF")
        '#000000'  # Black text on white background
        >>> get_contrast_color("#000000")
        '#FFFFFF'  # White text on black background
    """
    r, g, b = hex_to_rgb(background_color)

    # Calculate relative luminance
    # Using formula: (0.299*R + 0.587*G + 0.114*B)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

    # Return white text for dark backgrounds, black for light backgrounds
    return "#FFFFFF" if luminance < 0.5 else "#000000"
