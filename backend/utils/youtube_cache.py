"""
YouTube video caching utilities.

Provides functions for caching downloaded YouTube videos across jobs
to avoid redundant downloads.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, urlunparse

from backend.database import get_job_store
from backend.logging_config import get_logger
from backend.utils.paths import get_youtube_cache_dir

logger = get_logger("youtube_cache")


def normalize_youtube_url(url: str) -> str:
    """
    Normalize a YouTube URL to a standard format.

    Args:
        url: YouTube URL (any format)

    Returns:
        Normalized URL in format: https://www.youtube.com/watch?v=VIDEO_ID
    """
    from backend.utils.youtube import extract_video_id

    video_id = extract_video_id(url)
    if not video_id:
        return url

    return f"https://www.youtube.com/watch?v={video_id}"


def get_video_file_hash(file_path: str) -> Optional[str]:
    """
    Calculate SHA256 hash of a video file.

    Args:
        file_path: Path to video file

    Returns:
        SHA256 hash string or None on error
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 8MB chunks to handle large files
            for byte_block in iter(lambda: f.read(8 * 1024 * 1024), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_path}: {e}")
        return None


def check_cache(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a video exists in the cache.

    Args:
        video_id: YouTube video ID

    Returns:
        Cached video metadata dict or None if not cached
    """
    try:
        job_store = get_job_store()
        cached_video = job_store.get_youtube_video(video_id)

        if not cached_video:
            logger.debug(f"Cache miss for video {video_id}")
            # Record cache miss metric
            try:
                from backend.metrics import get_metrics_collector
                metrics = get_metrics_collector()
                metrics.youtube_cache_misses_total.inc()
            except Exception:
                pass
            return None

        # Verify file still exists
        file_path = cached_video.get("file_path")
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Cache entry exists but file missing: {video_id} at {file_path}")
            # Clean up stale cache entry
            job_store.delete_youtube_video(video_id)
            # Count as cache miss since file is missing
            try:
                from backend.metrics import get_metrics_collector
                metrics = get_metrics_collector()
                metrics.youtube_cache_misses_total.inc()
            except Exception:
                pass
            return None

        logger.info(f"Cache hit for video {video_id}")
        # Record cache hit metric
        try:
            from backend.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.youtube_cache_hits_total.inc()
        except Exception:
            pass
        return cached_video

    except Exception as e:
        logger.error(f"Error checking cache for video {video_id}: {e}")
        return None


def store_in_cache(video_id: str, video_url: str, file_path: str,
                   title: str, duration: Optional[float] = None,
                   width: Optional[int] = None, height: Optional[int] = None,
                   calculate_hash: bool = False) -> bool:
    """
    Store a downloaded video in the cache.

    Args:
        video_id: YouTube video ID
        video_url: Original video URL
        file_path: Path to downloaded video file
        title: Video title
        duration: Video duration in seconds
        width: Video width in pixels
        height: Video height in pixels
        calculate_hash: Whether to calculate file hash (slow for large files)

    Returns:
        True if successfully stored, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Cannot cache non-existent file: {file_path}")
            return False

        # Calculate file size
        file_size = os.path.getsize(file_path)

        # Calculate hash if requested
        file_hash = None
        if calculate_hash:
            file_hash = get_video_file_hash(file_path)

        # Normalize URL
        normalized_url = normalize_youtube_url(video_url)

        # Store in database (check if exists first)
        job_store = get_job_store()

        # Check if video already exists in cache
        existing_video = job_store.get_youtube_video(video_id)

        if existing_video:
            # Video already exists, just update usage stats
            logger.info(f"Video {video_id} already cached, updating usage")
            job_store.update_youtube_video_usage(video_id)
        else:
            # Create new cache entry
            job_store.create_youtube_video(
                video_id=video_id,
                normalized_url=normalized_url,
                file_path=file_path,
                title=title,
                duration_seconds=duration,
                width=width,
                height=height,
                file_size_bytes=file_size,
                file_hash=file_hash
            )
            logger.info(f"Cached video {video_id} ({title}) - {file_size / (1024*1024):.2f} MB")

            # Record download metric (only for new videos)
            try:
                from backend.metrics import get_metrics_collector
                metrics = get_metrics_collector()
                metrics.youtube_cache_downloads_total.inc()
                # Update cache size gauge
                stats = job_store.get_youtube_cache_stats()
                metrics.youtube_cache_size_bytes.set(stats.get("total_size_bytes", 0))
                metrics.youtube_cache_videos_count.set(stats.get("total_videos", 0))
            except Exception:
                pass

        return True

    except Exception as e:
        logger.error(f"Failed to store video {video_id} in cache: {e}")
        return False


def update_usage(video_id: str) -> bool:
    """
    Update last_used_at and increment download_count for a cached video.

    Args:
        video_id: YouTube video ID

    Returns:
        True if successfully updated, False otherwise
    """
    try:
        job_store = get_job_store()
        success = job_store.update_youtube_video_usage(video_id)

        if success:
            logger.debug(f"Updated usage for cached video {video_id}")
        else:
            logger.warning(f"Failed to update usage for video {video_id} (not found)")

        return success

    except Exception as e:
        logger.error(f"Error updating usage for video {video_id}: {e}")
        return False


def get_cached_path(video_id: str) -> Optional[str]:
    """
    Get the file path for a cached video.

    Args:
        video_id: YouTube video ID

    Returns:
        File path or None if not cached
    """
    cached_video = check_cache(video_id)
    if cached_video:
        return cached_video.get("file_path")
    return None


def verify_file_integrity(video_id: str) -> bool:
    """
    Verify the integrity of a cached video file.

    Args:
        video_id: YouTube video ID

    Returns:
        True if file is valid, False otherwise
    """
    try:
        job_store = get_job_store()
        cached_video = job_store.get_youtube_video(video_id)

        if not cached_video:
            return False

        file_path = cached_video.get("file_path")
        if not file_path or not os.path.exists(file_path):
            return False

        # Check file size
        expected_size = cached_video.get("file_size_bytes")
        if expected_size:
            actual_size = os.path.getsize(file_path)
            if actual_size != expected_size:
                logger.warning(f"File size mismatch for {video_id}: expected {expected_size}, got {actual_size}")
                return False

        # Verify hash if available
        stored_hash = cached_video.get("file_hash")
        if stored_hash:
            actual_hash = get_video_file_hash(file_path)
            if actual_hash != stored_hash:
                logger.warning(f"Hash mismatch for {video_id}")
                return False

        return True

    except Exception as e:
        logger.error(f"Error verifying integrity for video {video_id}: {e}")
        return False


def cleanup_old_cache(days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
    """
    Clean up videos not used in the specified number of days.

    Args:
        days: Number of days of inactivity before deletion
        dry_run: If True, don't actually delete files

    Returns:
        Dictionary with cleanup statistics
    """
    try:
        job_store = get_job_store()

        # Get list of videos to delete
        videos_to_delete = []
        all_videos = job_store.list_youtube_videos(limit=10000, order_by="last_used_at")

        from datetime import datetime, timedelta, timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        for video in all_videos:
            last_used_str = video.get("last_used_at")
            if not last_used_str:
                continue

            last_used = datetime.fromisoformat(last_used_str.replace('Z', '+00:00'))
            if last_used < cutoff_date:
                videos_to_delete.append(video)

        deleted_count = 0
        deleted_size = 0
        errors = []

        for video in videos_to_delete:
            video_id = video["video_id"]
            file_path = video.get("file_path")
            file_size = video.get("file_size_bytes", 0)

            try:
                if not dry_run:
                    # Delete file
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        logger.debug(f"Deleted cache file: {file_path}")

                    # Delete database entry
                    job_store.delete_youtube_video(video_id)

                deleted_count += 1
                deleted_size += file_size

            except Exception as e:
                error_msg = f"Failed to delete {video_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        result = {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
            "errors": errors,
            "dry_run": dry_run
        }

        if dry_run:
            logger.info(f"Cleanup dry run: would delete {deleted_count} videos ({result['deleted_size_mb']} MB)")
        else:
            logger.info(f"Cleaned up {deleted_count} old cached videos ({result['deleted_size_mb']} MB)")

        # Record cleanup metrics
        try:
            from backend.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            status = "success" if not errors else "partial_failure"
            metrics.youtube_cache_cleanups_total.labels(status=status).inc()
            if not dry_run:
                metrics.youtube_cache_videos_removed.inc(deleted_count)
                # Update cache size gauge
                stats = job_store.get_youtube_cache_stats()
                metrics.youtube_cache_size_bytes.set(stats.get("total_size_bytes", 0))
                metrics.youtube_cache_videos_count.set(stats.get("total_videos", 0))
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")
        return {
            "deleted_count": 0,
            "deleted_size_bytes": 0,
            "deleted_size_mb": 0,
            "errors": [str(e)],
            "dry_run": dry_run
        }


def get_cache_stats() -> Dict[str, Any]:
    """
    Get YouTube cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    try:
        job_store = get_job_store()
        stats = job_store.get_youtube_cache_stats()

        # Add directory statistics
        cache_dir = get_youtube_cache_dir()
        from backend.utils.paths import get_path_manager
        dir_stats = get_path_manager().get_directory_stats(cache_dir)

        stats["cache_directory"] = {
            "path": str(cache_dir),
            "file_count": dir_stats.get("file_count", 0),
            "total_size_mb": dir_stats.get("total_size_mb", 0)
        }

        return stats

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {
            "error": str(e),
            "total_videos": 0,
            "total_size_mb": 0
        }


def move_to_cache(source_path: str, video_id: str) -> Optional[str]:
    """
    Move a downloaded video file to the cache directory.

    Args:
        source_path: Current path of video file
        video_id: YouTube video ID

    Returns:
        New path in cache or None on error
    """
    try:
        import shutil

        cache_dir = get_youtube_cache_dir()

        # Get file extension
        ext = os.path.splitext(source_path)[1] or ".mp4"

        # Target path in cache
        target_path = cache_dir / f"{video_id}{ext}"

        # Move file
        shutil.move(source_path, target_path)

        logger.debug(f"Moved video to cache: {target_path}")
        return str(target_path)

    except Exception as e:
        logger.error(f"Failed to move video to cache: {e}")
        return None
