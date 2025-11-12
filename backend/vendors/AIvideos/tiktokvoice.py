"""
AIvideos TikTok voice stub module.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


def tts(text: str, voice: str, filename: Optional[str] = None) -> Optional[str]:
    """
    Stub for text-to-speech functionality.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use
        filename: Output filename
        
    Returns:
        Path to generated audio file or None if failed
    """
    logger.warning("tts stub called - should be handled by video-processor service")
    return "/tmp/stub_audio.wav"