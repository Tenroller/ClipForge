"""Unified YouTube helper utilities.

Backend-only subset: URL parsing, metadata extraction, and exception types.
Download/audio extraction logic lives in the video-processor service.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple, Any, Dict

try:
    from ..logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger("utils.youtube")

YOUTUBE_ID_REGEXES = [
    r"(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([A-Za-z0-9_-]{6,})",
    r"youtube\.com.*[?&]v=([A-Za-z0-9_-]{6,})",
]

NORMALIZED_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


def extract_video_id(url: str) -> str:
    """Extract the video ID from a YouTube URL.

    Raises ValueError if not found.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL required to extract video id")
    for pattern in YOUTUBE_ID_REGEXES:
        m = re.search(pattern, url)
        if m:
            vid = m.group(1)
            # Trim potential trailing characters (params) just in case
            return vid.split("?")[0].split("&")[0]
    raise ValueError(f"Could not extract YouTube video ID from: {url}")


def normalize_url(url: str) -> str:
    vid = extract_video_id(url)
    return NORMALIZED_WATCH_URL.format(video_id=vid)


class YouTubeDownloadError(RuntimeError):
    pass


@dataclass
class VideoMetadata:
    """Metadata for a YouTube video without downloading it."""
    video_id: str
    title: str
    channel: str
    channel_url: str
    duration: Optional[int]  # in seconds
    thumbnail_url: str
    description: str
    view_count: Optional[int]
    upload_date: Optional[str]  # YYYYMMDD format
    width: Optional[int]
    height: Optional[int]

    @property
    def resolution(self) -> Optional[Tuple[int, int]]:
        if self.width and self.height:
            return (self.width, self.height)
        return None

    @property
    def duration_formatted(self) -> str:
        """Return duration in HH:MM:SS format."""
        if not self.duration:
            return "Unknown"
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"


def get_video_metadata(url: str) -> VideoMetadata:
    """Extract YouTube video metadata without downloading the video.

    This is useful for previewing video information before starting a download.

    Args:
        url: YouTube video URL

    Returns:
        VideoMetadata with video information

    Raises:
        YouTubeDownloadError: If metadata extraction fails
    """
    try:
        import yt_dlp
    except ImportError as e:
        raise YouTubeDownloadError("yt_dlp is not installed. pip install yt-dlp") from e

    video_id = extract_video_id(url)

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,  # Get full metadata
            "skip_download": True,  # Don't download the video
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info: Dict[str, Any] = ydl.extract_info(url, download=False)

            # Get the best thumbnail (highest resolution)
            thumbnails = info.get("thumbnails", [])
            thumbnail_url = ""
            if thumbnails:
                # Sort by preference: maxresdefault > sddefault > hqdefault > default
                thumbnail_url = thumbnails[-1].get("url", "")
                # Try to get the highest quality thumbnail
                for thumb in thumbnails:
                    if thumb.get("id") == "maxresdefault":
                        thumbnail_url = thumb.get("url", thumbnail_url)
                        break

            return VideoMetadata(
                video_id=video_id,
                title=info.get("title", "Unknown Title"),
                channel=info.get("uploader", info.get("channel", "Unknown Channel")),
                channel_url=info.get("uploader_url", info.get("channel_url", "")),
                duration=int(info.get("duration", 0)) if info.get("duration") else None,
                thumbnail_url=thumbnail_url,
                description=info.get("description", ""),
                view_count=int(info.get("view_count", 0)) if info.get("view_count") else None,
                upload_date=info.get("upload_date"),
                width=info.get("width"),
                height=info.get("height"),
            )

    except Exception as e:
        logger.error(f"Failed to extract metadata for {video_id}: {e}")
        raise YouTubeDownloadError(f"Failed to extract metadata for video {video_id}: {str(e)}") from e


__all__ = [
    "extract_video_id",
    "normalize_url",
    "get_video_metadata",
    "VideoMetadata",
    "YouTubeDownloadError",
]
