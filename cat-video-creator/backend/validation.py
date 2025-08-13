"""
Input validation and sanitization utilities.
"""

import re
import urllib.parse
from typing import Optional
from fastapi import HTTPException


def validate_youtube_url(url: str) -> str:
    """Validate and normalize YouTube URL."""
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="YouTube URL is required")
    
    url = url.strip()
    
    # Basic URL validation patterns
    youtube_patterns = [
        r'^https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'^https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'^https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'^https?://(?:m\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in youtube_patterns:
        match = re.match(pattern, url)
        if match:
            video_id = match.group(1)
            # Return normalized URL
            return f"https://www.youtube.com/watch?v={video_id}"
    
    raise HTTPException(
        status_code=400, 
        detail="Invalid YouTube URL format"
    )


def validate_subject(subject: str) -> str:
    """Validate and sanitize video subject."""
    if not subject or not isinstance(subject, str):
        raise HTTPException(status_code=400, detail="Video subject is required")
    
    subject = subject.strip()
    
    if len(subject) < 3:
        raise HTTPException(status_code=400, detail="Subject must be at least 3 characters")
    
    if len(subject) > 500:
        raise HTTPException(status_code=400, detail="Subject must be less than 500 characters")
    
    # Remove potential script injection
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, subject, re.IGNORECASE | re.DOTALL):
            raise HTTPException(status_code=400, detail="Subject contains potentially unsafe content")
    
    return subject


def validate_custom_prompt(prompt: Optional[str]) -> Optional[str]:
    """Validate and sanitize custom prompt."""
    if not prompt:
        return None
    
    if not isinstance(prompt, str):
        return None
    
    prompt = prompt.strip()
    
    if len(prompt) > 2000:
        raise HTTPException(status_code=400, detail="Custom prompt must be less than 2000 characters")
    
    # Similar sanitization as subject
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, prompt, re.IGNORECASE | re.DOTALL):
            raise HTTPException(status_code=400, detail="Custom prompt contains potentially unsafe content")
    
    return prompt


def validate_zip_url(url: Optional[str]) -> Optional[str]:
    """Validate ZIP URL for music downloads."""
    if not url:
        return None
    
    if not isinstance(url, str):
        return None
    
    url = url.strip()
    
    # Basic URL validation
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme in ['http', 'https']:
            raise HTTPException(status_code=400, detail="ZIP URL must use HTTP or HTTPS")
        
        if not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid ZIP URL format")
        
        # Check for suspicious patterns
        if any(pattern in url.lower() for pattern in ['../', 'file://', 'ftp://']):
            raise HTTPException(status_code=400, detail="ZIP URL contains unsafe patterns")
        
        return url
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ZIP URL format")


def validate_color(color: str) -> str:
    """Validate hex color code."""
    if not color or not isinstance(color, str):
        return "#FFFF00"  # Default yellow
    
    color = color.strip()
    
    # Validate hex color format
    if re.match(r'^#[0-9A-Fa-f]{6}$', color):
        return color.upper()
    
    # Try to fix common issues
    if color.startswith('#') and len(color) == 4:
        # Convert #RGB to #RRGGBB
        r, g, b = color[1], color[2], color[3]
        return f"#{r}{r}{g}{g}{b}{b}".upper()
    
    if not color.startswith('#') and len(color) == 6:
        if re.match(r'^[0-9A-Fa-f]{6}$', color):
            return f"#{color.upper()}"
    
    # If all else fails, return default
    return "#FFFF00"


def validate_subtitle_position(position: str) -> str:
    """Validate subtitle position string."""
    if not position or not isinstance(position, str):
        return "center,bottom"
    
    position = position.strip().lower()
    
    # Allow common position formats
    valid_positions = [
        "center,bottom", "center,top", "left,bottom", "right,bottom",
        "left,top", "right,top", "center,center"
    ]
    
    # Allow percentage positions
    if re.match(r'^pct:\d+,\d+$', position):
        return position
    
    # Allow pixel positions
    if re.match(r'^px:\d+,\d+$', position):
        return position
    
    if position in valid_positions:
        return position
    
    # Default fallback
    return "center,bottom"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations."""
    if not filename or not isinstance(filename, str):
        return "output"
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\.\.+', '.', filename)  # Prevent path traversal
    filename = filename.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    # Ensure it's not empty
    if not filename:
        filename = "output"
    
    return filename


def validate_ai_model(model: str) -> str:
    """Validate AI model selection."""
    if not model or not isinstance(model, str):
        return "gemini-2.0-flash"
    
    model = model.strip()
    
    # List of allowed models (should match what's returned by /api/models)
    allowed_models = [
        "gemini-2.0-flash",
        "gemini-2.0-pro-exp", 
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite",
    ]
    
    if model in allowed_models:
        return model
    
    # Default fallback
    return "gemini-2.0-flash"


def validate_voice(voice: str) -> str:
    """Validate voice selection."""
    if not voice or not isinstance(voice, str):
        return "af_bella"
    
    voice = voice.strip()
    
    # Basic validation - actual voice list is dynamic
    # This just ensures it's a reasonable format
    if re.match(r'^[a-z]{2}_[a-z]+\d*$', voice) or voice == "af_bella":
        return voice
    
    return "af_bella"
