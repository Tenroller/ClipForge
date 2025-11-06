"""
Adapter to access backend cache utilities from video-processor.

This module handles the import path resolution to access backend modules
from the video-processor context.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to Python path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def check_cache(video_id: str) -> Optional[Dict[str, Any]]:
    """Check if a video exists in cache."""
    try:
        from backend.utils.youtube_cache import check_cache as _check_cache
        return _check_cache(video_id)
    except Exception:
        return None


def update_usage(video_id: str) -> bool:
    """Update cache usage statistics."""
    try:
        from backend.utils.youtube_cache import update_usage as _update_usage
        return _update_usage(video_id)
    except Exception:
        return False


def store_in_cache(video_id: str, video_url: str, file_path: str,
                   title: str, duration: Optional[float] = None,
                   width: Optional[int] = None, height: Optional[int] = None,
                   calculate_hash: bool = False) -> bool:
    """Store a video in cache."""
    try:
        from backend.utils.youtube_cache import store_in_cache as _store_in_cache
        return _store_in_cache(
            video_id=video_id,
            video_url=video_url,
            file_path=file_path,
            title=title,
            duration=duration,
            width=width,
            height=height,
            calculate_hash=calculate_hash
        )
    except Exception:
        return False


def get_youtube_cache_dir() -> Optional[Path]:
    """Get the YouTube cache directory."""
    try:
        from backend.utils.paths import get_youtube_cache_dir as _get_cache_dir
        return _get_cache_dir()
    except Exception:
        return None
