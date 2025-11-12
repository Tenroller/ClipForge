"""
AIvideos search stub module.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def search_for_stock_videos(search_terms: List[str], video_count: int = 5) -> List[Dict[str, Any]]:
    """
    Stub for stock video search functionality.
    
    Args:
        search_terms: List of search terms
        video_count: Number of videos to find
        
    Returns:
        List of video metadata dictionaries
    """
    logger.warning("search_for_stock_videos stub called - should be handled by video-processor service")
    return [
        {
            "id": f"stub_video_{i}",
            "url": f"https://example.com/video_{i}.mp4",
            "duration": 10,
            "title": f"Stub video {i}"
        }
        for i in range(video_count)
    ]