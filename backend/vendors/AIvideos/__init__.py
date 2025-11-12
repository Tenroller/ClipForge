"""
AIvideos compatibility module for backend.

This module provides stub implementations for AIvideos functions
that should be handled by the video-processor service in a proper
microservice architecture.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def fetch_songs(zip_url: str) -> bool:
    """
    Stub for song fetching functionality.
    
    In a proper implementation, this should be handled by the video-processor service.
    """
    logger.warning("fetch_songs called on backend stub - should delegate to video-processor")
    return True


def check_env_vars() -> None:
    """
    Stub for environment validation.
    
    In a proper implementation, this should be handled by the video-processor service.
    """
    logger.warning("check_env_vars called on backend stub - should delegate to video-processor")
    pass