"""
AIvideos GPT stub module.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def generate_script(subject: str, paragraph_number: int, ai_model: str, voice: str, custom_prompt: str = "") -> Optional[str]:
    """
    Stub for script generation functionality.
    
    Args:
        subject: Video subject
        paragraph_number: Number of paragraphs
        ai_model: AI model to use
        voice: Voice for TTS
        custom_prompt: Custom prompt for generation
        
    Returns:
        Generated script or None if failed
    """
    logger.warning("generate_script stub called - should be handled by video-processor service")
    return f"This is a stub script about {subject} with {paragraph_number} paragraphs."


def get_search_terms(script: str) -> List[str]:
    """
    Stub for search terms generation.
    
    Args:
        script: Script text to analyze
        
    Returns:
        List of search terms
    """
    logger.warning("get_search_terms stub called - should be handled by video-processor service")
    return ["stub", "search", "terms"]