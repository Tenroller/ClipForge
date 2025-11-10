"""Unified YouTube helper utilities.

Goals:
- Single place for video ID extraction & normalization
- Thin wrapper around yt_dlp for downloading highest reasonable quality
- Reduce dozens of rarely-used yt_dlp flags in existing code to a curated, stable set
- Provide clear exceptions & structured return data

Design principles:
1. Safe defaults (mp4 merge, best up to 1080p to avoid huge 4K downloads by default)
2. Small public surface: extract_video_id, normalize_url, download_video
3. Explicit typed return object for download (path, title, duration, resolution)
4. Central retry logic

NOTE: Existing processors/generators can progressively migrate to this module.
"""
from __future__ import annotations

import os
import re
import time
import glob
import subprocess
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


@dataclass
class DownloadResult:
    video_path: str
    title: str
    duration: Optional[int]
    width: Optional[int]
    height: Optional[int]
    video_id: str

    @property
    def resolution(self) -> Optional[Tuple[int, int]]:
        if self.width and self.height:
            return (self.width, self.height)
        return None


class YouTubeDownloadError(RuntimeError):
    pass


def update_yt_dlp() -> bool:
    """Update yt-dlp to the latest version.

    Returns True if update succeeded, False otherwise.
    """
    try:
        import yt_dlp
        # Use yt-dlp's built-in update mechanism
        # This works for pip-installed versions
        result = subprocess.run(
            [
                "pip", "install", "--upgrade",
                "yt-dlp @ git+https://github.com/yt-dlp/yt-dlp.git@master"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            logger.info("Successfully updated yt-dlp")
            return True
        else:
            logger.warning(f"yt-dlp update failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error updating yt-dlp: {e}")
        return False


def check_yt_dlp_version() -> Optional[str]:
    """Get the current yt-dlp version.

    Returns version string or None if not installed.
    """
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception as e:
        logger.warning(f"Could not get yt-dlp version: {e}")
        return None


def _build_default_ydl_opts(output_template: str) -> Dict[str, Any]:  # separated for testability
    return {
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"  # merged 1080p
            "bestvideo[height<=1080]+bestaudio/"                    # any container 1080p
            "best[height<=1080]/"                                   # single file <=1080p
            "best"                                                  # fallback anything
        ),
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 10,  # Increased fragment retries
        "ignoreerrors": False,
        # Add postprocessor options for better error handling
        "postprocessor_args": {
            "ffmpeg": [
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts",
                "-err_detect", "ignore_err"  # Ignore minor errors in input
            ]
        },
        # Clean up partial downloads on failure
        "keepvideo": False,
        "embed_chapters": False,
        "writeinfojson": False,
    }


def _build_alternative_hq_ydl_opts(output_template: str) -> Dict[str, Any]:
    """Alternative high-quality download with different format priorities"""
    return {
        "format": (
            "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/"  # webm container
            "bestvideo[height<=1080][ext=mkv]+bestaudio/"             # mkv container
            "bestvideo[height<=1080]+bestaudio[ext=webm]/"            # different audio
            "best[height<=1080][ext=webm]/"                          # single webm
            "best[height<=1080][ext=mkv]/"                           # single mkv
            "best[height<=1080]"                                     # any 1080p
        ),
        "merge_output_format": "mkv",  # Different container
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 15,
        "ignoreerrors": False,
        "postprocessor_args": {
            "ffmpeg": [
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts+igndts",
                "-err_detect", "ignore_err",
                "-max_muxing_queue_size", "1024"
            ]
        },
        "keepvideo": False,
        "embed_chapters": False,
        "writeinfojson": False,
    }


def _build_robust_hq_ydl_opts(output_template: str) -> Dict[str, Any]:
    """High-quality download with maximum error tolerance"""
    return {
        "format": (
            "best[height<=1080]/"                                    # Single file 1080p (no merge needed)
            "bestvideo[height<=1080]+worst[acodec=none]/"            # Video only if audio fails
            "best[height<=720]/"                                     # Fallback to 720p
            "best"                                                   # Last resort
        ),
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 20,
        "ignoreerrors": True,  # More tolerant
        "postprocessor_args": {
            "ffmpeg": [
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts+igndts+discardcorrupt",
                "-err_detect", "ignore_err",
                "-max_muxing_queue_size", "2048",
                "-analyzeduration", "10000000",
                "-probesize", "10000000"
            ]
        },
        "keepvideo": False,
        "embed_chapters": False,
        "writeinfojson": False,
    }


def _build_fallback_ydl_opts(output_template: str) -> Dict[str, Any]:
    """Medium quality fallback with different approach"""
    return {
        "format": (
            "best[height<=720][ext=mp4]/"                           # Single file 720p
            "bestvideo[height<=720]+bestaudio/"                     # Merged 720p
            "best[height<=720]/"                                    # Any 720p format
            "best[height<=480]/"                                    # 480p fallback
            "worst"                                                 # Last resort
        ),
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 15,
        "ignoreerrors": True,  # More tolerant of errors
        "postprocessor_args": {
            "ffmpeg": [
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts+igndts",  # Ignore DTS errors
                "-err_detect", "ignore_err",
                "-max_muxing_queue_size", "1024",  # Larger muxing queue
                "-f", "mp4"
            ]
        },
        "keepvideo": False,
        "embed_chapters": False,
        "writeinfojson": False,
        # Skip postprocessing if it fails
        "postprocessors": [],
    }


def _build_emergency_ydl_opts(output_template: str) -> Dict[str, Any]:
    """Emergency fallback with minimal processing - download any available format"""
    return {
        "format": "worst",  # Just get any format that works
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 20,
        "ignoreerrors": True,
        "extract_flat": False,
        "no_check_certificate": True,
        # Minimal processing to avoid postprocessing errors
        "skip_download": False,
        "writeinfojson": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writethumbnail": False,
        "postprocessors": [],  # No postprocessing at all
    }


def download_video(url: str, output_dir: str, max_retries: int = 3, sleep_seconds: float = 1.5, use_cache: bool = True) -> DownloadResult:
    """Download a YouTube video returning structured metadata.

    Uses progressive quality-preserving fallback strategies for maximum reliability:
    1. Default HQ: Standard 1080p with optimal MP4/M4A merge
    2. Alternative HQ: 1080p with different containers (WebM, MKV)
    3. Robust HQ: 1080p single file (no merge complexity)
    4. Medium Quality: 720p with error tolerance
    5. Emergency: Any available format with minimal processing

    Prioritizes maintaining quality while handling postprocessing errors intelligently.

    Args:
        url: YouTube video URL
        output_dir: Directory to save video (ignored if using cache)
        max_retries: Maximum number of download attempts
        sleep_seconds: Seconds to wait between retries
        use_cache: Whether to use the shared video cache (default: True)

    Returns:
        DownloadResult with video path and metadata
    """
    try:
        import yt_dlp  # local import so environments without it fail lazily
    except ImportError as e:
        raise YouTubeDownloadError("yt_dlp is not installed. pip install yt-dlp") from e

    video_id = extract_video_id(url)

    # Check cache first if enabled
    if use_cache:
        try:
            from backend.utils.youtube_cache import check_cache, update_usage
            cached_video = check_cache(video_id)

            if cached_video:
                logger.info(f"Using cached video for {video_id}")
                # Update usage statistics
                update_usage(video_id)

                # Return cached result
                return DownloadResult(
                    video_path=cached_video["file_path"],
                    title=cached_video["title"],
                    duration=int(cached_video["duration_seconds"]) if cached_video.get("duration_seconds") else None,
                    width=cached_video.get("width"),
                    height=cached_video.get("height"),
                    video_id=video_id,
                )
        except Exception as cache_error:
            logger.warning(f"Cache check failed for {video_id}: {cache_error}, proceeding with download")

    # Determine download directory
    if use_cache:
        try:
            from backend.utils.paths import get_youtube_cache_dir
            output_dir = str(get_youtube_cache_dir())
        except Exception as e:
            logger.warning(f"Failed to get cache directory: {e}, using provided output_dir")

    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    
    # Clean up any existing partial files
    base_path = os.path.join(output_dir, video_id)
    cleanup_patterns = [
        f"{base_path}.*",
        f"{base_path}.part*",
        f"{base_path}.ytdl*",
        f"{base_path}.temp*"
    ]
    
    import glob
    for pattern in cleanup_patterns:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
                logger.debug(f"Cleaned up partial file: {file}")
            except OSError:
                pass  # File might not exist or be in use

    # Strategy 1: Default high-quality download (1080p with optimal settings)
    # Strategy 2: Alternative high-quality (1080p with different containers/codecs)
    # Strategy 3: Robust high-quality (1080p single file, no merge complexity)
    # Strategy 4: Medium quality fallback (720p)
    # Strategy 5: Emergency fallback with minimal processing
    ydl_opts_strategies = [
        ("default_hq", _build_default_ydl_opts(output_template)),
        ("alternative_hq", _build_alternative_hq_ydl_opts(output_template)),
        ("robust_hq", _build_robust_hq_ydl_opts(output_template)),
        ("medium_quality", _build_fallback_ydl_opts(output_template)),
        ("emergency", _build_emergency_ydl_opts(output_template))
    ]

    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        for strategy_name, ydl_opts in ydl_opts_strategies:
            try:
                logger.info(f"Attempt {attempt}/{max_retries} using {strategy_name} strategy for {video_id}")
                
                # Pylance may not understand dynamic dict; ignore for typing
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
                    info: Dict[str, Any] = ydl.extract_info(url, download=True)  # type: ignore[assignment]

                # Determine actual path (mp4 preferred)
                candidates = [
                    f"{base_path}.mp4",
                    f"{base_path}.mkv",
                    f"{base_path}.webm",
                    f"{base_path}.mov",
                    f"{base_path}.flv",
                ]
                video_path = next((p for p in candidates if os.path.exists(p) and os.path.getsize(p) > 0), None)
                if not video_path:
                    raise YouTubeDownloadError("Download reported success but file not found or empty")

                # Verify file integrity
                try:
                    # Quick check if file can be opened by ffmpeg
                    result = subprocess.run([
                        "ffprobe", "-v", "quiet", "-show_entries", "format=duration", 
                        "-of", "csv=p=0", video_path
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode != 0:
                        logger.warning(f"Downloaded file {video_path} failed ffprobe check: {result.stderr}")
                        os.remove(video_path)
                        raise YouTubeDownloadError("Downloaded file appears corrupted")
                        
                except (subprocess.TimeoutExpired, FileNotFoundError, ImportError):
                    # ffprobe not available or timeout, accept the file
                    logger.warning("Could not verify file integrity (ffprobe unavailable or timeout)")
                except Exception as verify_error:
                    logger.warning(f"File verification failed: {verify_error}")
                    # Continue anyway, file might still be usable

                title = info.get("title") or video_id
                width_val = info.get("width")
                height_val = info.get("height")
                duration_val = info.get("duration")
                
                # Log quality information
                quality_info = f"{width_val}x{height_val}" if width_val and height_val else "unknown resolution"
                file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
                logger.info(f"Successfully downloaded {video_id} using {strategy_name} strategy: {quality_info}, {file_size:.1f}MB")

                # Store in cache if enabled and not already in cache directory
                if use_cache:
                    try:
                        from backend.utils.youtube_cache import store_in_cache
                        from backend.utils.paths import get_youtube_cache_dir

                        cache_dir = str(get_youtube_cache_dir())
                        # Only store if not already in cache directory
                        if not video_path.startswith(cache_dir):
                            logger.debug(f"Video downloaded to temp location, will be referenced from {video_path}")
                            # Note: We don't move the file since it might be used immediately
                            # The cache stores the current path

                        # Store metadata in cache database
                        store_in_cache(
                            video_id=video_id,
                            video_url=url,
                            file_path=video_path,
                            title=str(title),
                            duration=duration_val if isinstance(duration_val, (int, float)) else None,
                            width=int(width_val) if isinstance(width_val, (int, float)) else None,
                            height=int(height_val) if isinstance(height_val, (int, float)) else None,
                            calculate_hash=False  # Skip hash calculation for speed
                        )
                        logger.info(f"Stored video {video_id} in cache")
                    except Exception as cache_store_error:
                        logger.warning(f"Failed to store video in cache: {cache_store_error}")

                return DownloadResult(
                    video_path=video_path,
                    title=str(title),
                    duration=int(duration_val) if isinstance(duration_val, (int, float)) else None,
                    width=int(width_val) if isinstance(width_val, (int, float)) else None,
                    height=int(height_val) if isinstance(height_val, (int, float)) else None,
                    video_id=video_id,
                )
                
            except Exception as e:  # broad: yt_dlp raises various custom exceptions
                last_err = e
                error_msg = str(e).lower()
                
                # Classify error types for better handling
                if any(keyword in error_msg for keyword in ["postprocessing", "invalid data found", "ffmpeg"]):
                    logger.warning(f"Postprocessing error with {strategy_name} strategy for {video_id}: {e}")
                    # Clean up any partial files before trying next strategy
                    for pattern in cleanup_patterns:
                        for file in glob.glob(pattern):
                            try:
                                os.remove(file)
                            except OSError:
                                pass
                    # Try next strategy immediately for postprocessing errors
                    continue
                elif any(keyword in error_msg for keyword in ["network", "connection", "timeout", "http error 5"]):
                    logger.warning(f"Network error with {strategy_name} strategy for {video_id}: {e}")
                    # For network errors, wait and try next strategy (might be server-side issue)
                    time.sleep(1)
                    continue
                elif any(keyword in error_msg for keyword in ["403", "404", "private", "unavailable", "removed"]):
                    logger.error(f"Video access error with {strategy_name} strategy for {video_id}: {e}")
                    # For access errors, skip remaining strategies in this attempt
                    break
                elif any(keyword in error_msg for keyword in ["format", "codec", "not available", "no such format"]):
                    logger.warning(f"Format error with {strategy_name} strategy for {video_id}: {e}")
                    # Try next strategy for format errors
                    continue
                else:
                    logger.warning(f"Unknown error with {strategy_name} strategy for {video_id}: {e}")
                    # For unknown errors, try next strategy
                    continue
        
        # Sleep between full retry attempts (after trying all strategies)
        if attempt < max_retries:
            time.sleep(sleep_seconds * attempt)  # Progressive backoff

    raise YouTubeDownloadError(f"Failed to download {video_id} after {max_retries} attempts with all strategies: {last_err}")


__all__ = [
    "extract_video_id",
    "normalize_url",
    "download_video",
    "DownloadResult",
    "YouTubeDownloadError",
    "update_yt_dlp",
    "check_yt_dlp_version",
]
