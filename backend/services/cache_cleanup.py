"""
Cache cleanup service for automatic YouTube video cache management.

Provides scheduled cleanup of old cached videos to prevent unlimited storage growth.
"""

import schedule
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any

from backend.logging_config import get_logger
from backend.utils.youtube_cache import cleanup_old_cache, get_cache_stats

logger = get_logger("cache_cleanup")


class CacheCleanupService:
    """Service for managing YouTube cache cleanup on a schedule."""

    def __init__(self, cleanup_days: int = 30, schedule_time: str = "02:00"):
        """
        Initialize cache cleanup service.

        Args:
            cleanup_days: Delete videos unused for this many days
            schedule_time: Time to run cleanup (HH:MM format)
        """
        self.cleanup_days = cleanup_days
        self.schedule_time = schedule_time
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_cleanup: Optional[datetime] = None
        self.last_cleanup_stats: Optional[Dict[str, Any]] = None

    def cleanup_task(self):
        """Run the cache cleanup task."""
        try:
            logger.info(f"Starting scheduled cache cleanup (removing videos unused for {self.cleanup_days}+ days)")

            # Get stats before cleanup
            stats_before = get_cache_stats()
            logger.info(f"Cache stats before cleanup: {stats_before.get('total_videos', 0)} videos, "
                       f"{stats_before.get('total_size_mb', 0):.2f} MB")

            # Run cleanup
            result = cleanup_old_cache(days=self.cleanup_days, dry_run=False)

            # Get stats after cleanup
            stats_after = get_cache_stats()

            self.last_cleanup = datetime.now()
            self.last_cleanup_stats = {
                "timestamp": self.last_cleanup.isoformat(),
                "deleted_count": result["deleted_count"],
                "deleted_size_mb": result["deleted_size_mb"],
                "errors": result["errors"],
                "videos_before": stats_before.get("total_videos", 0),
                "videos_after": stats_after.get("total_videos", 0),
                "size_before_mb": stats_before.get("total_size_mb", 0),
                "size_after_mb": stats_after.get("total_size_mb", 0)
            }

            logger.info(f"Cache cleanup completed: deleted {result['deleted_count']} videos ({result['deleted_size_mb']} MB)")

            if result["errors"]:
                logger.warning(f"Cleanup completed with {len(result['errors'])} errors")

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            self.last_cleanup_stats = {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }

    def _schedule_loop(self):
        """Run the schedule loop in a background thread."""
        logger.info(f"Cache cleanup service started (scheduled for {self.schedule_time} daily)")

        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in cleanup schedule loop: {e}")
                time.sleep(60)

        logger.info("Cache cleanup service stopped")

    def start(self):
        """Start the cache cleanup service."""
        if self.is_running:
            logger.warning("Cache cleanup service is already running")
            return

        self.is_running = True

        # Schedule daily cleanup at specified time
        schedule.every().day.at(self.schedule_time).do(self.cleanup_task)

        # Start background thread
        self.thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.thread.start()

        logger.info(f"Cache cleanup service started successfully (daily at {self.schedule_time})")

    def stop(self):
        """Stop the cache cleanup service."""
        if not self.is_running:
            logger.warning("Cache cleanup service is not running")
            return

        self.is_running = False

        # Clear schedule
        schedule.clear()

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("Cache cleanup service stopped")

    def run_now(self) -> Dict[str, Any]:
        """
        Run cleanup immediately (outside of schedule).

        Returns:
            Cleanup statistics
        """
        logger.info("Running manual cache cleanup")
        self.cleanup_task()
        return self.last_cleanup_stats or {"error": "Cleanup task did not produce stats"}

    def get_status(self) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Dictionary with service status information
        """
        return {
            "is_running": self.is_running,
            "schedule_time": self.schedule_time,
            "cleanup_days": self.cleanup_days,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "last_cleanup_stats": self.last_cleanup_stats,
            "next_run": schedule.next_run().isoformat() if schedule.jobs else None
        }


# Global service instance
_cleanup_service: Optional[CacheCleanupService] = None


def get_cleanup_service() -> CacheCleanupService:
    """Get or create the global cache cleanup service instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CacheCleanupService()
    return _cleanup_service


def start_cleanup_service():
    """Start the cache cleanup service."""
    service = get_cleanup_service()
    service.start()


def stop_cleanup_service():
    """Stop the cache cleanup service."""
    service = get_cleanup_service()
    service.stop()
