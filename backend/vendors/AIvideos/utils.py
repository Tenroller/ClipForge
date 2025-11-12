"""
AIvideos utils stub module.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def fetch_songs(zip_url: str) -> bool:
    """
    Stub for song fetching functionality.
    
    Args:
        zip_url: URL to zip file containing songs
        
    Returns:
        True if successful, False otherwise
    """
    logger.warning("fetch_songs stub called - should be handled by video-processor service")
    return True


def check_env_vars() -> None:
    """
    Stub for environment variable checking.
    
    Raises:
        SystemExit: If required environment variables are missing
    """
    logger.warning("check_env_vars stub called - should be handled by video-processor service")
    # For now, don't raise errors to allow backend to start
    pass