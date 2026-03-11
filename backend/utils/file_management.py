"""
File management utilities for automatic cleanup and temporary file handling.
"""

import os
import time
import shutil
import threading
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime, timedelta
import psutil
from ..logging_config import get_logger

logger = get_logger("file_management")


class TempFileManager:
    """Manages temporary files with automatic cleanup and retention policies."""

    def __init__(self, base_temp_dir: Optional[Path] = None):
        self.base_temp_dir = base_temp_dir or Path("temp")
        self.temp_dirs: Dict[str, Path] = {}
        self.retention_policies: Dict[str, Dict] = {}
        self.cleanup_thread: Optional[threading.Thread] = None
        self.running = False

        # Register cleanup on exit
        atexit.register(self.cleanup_all)

        # Start background cleanup thread
        self.start_background_cleanup()

    def register_temp_dir(self, name: str, path: Path, retention_hours: int = 24,
                         max_size_mb: int = 500, cleanup_interval_minutes: int = 30):
        """Register a temporary directory with cleanup policy."""
        self.temp_dirs[name] = path
        self.retention_policies[name] = {
            'retention_hours': retention_hours,
            'max_size_mb': max_size_mb,
            'cleanup_interval_minutes': cleanup_interval_minutes,
            'last_cleanup': datetime.now()
        }

        # Ensure directory exists
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Registered temp directory: {name} -> {path}")

    def create_temp_file(self, prefix: str = "tmp", suffix: str = "", dir_name: str = "default") -> Path:
        """Create a temporary file with automatic cleanup tracking."""
        if dir_name not in self.temp_dirs:
            raise ValueError(f"Temp directory '{dir_name}' not registered")

        temp_dir = self.temp_dirs[dir_name]
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}_{os.getpid()}{suffix}"
        temp_path = temp_dir / filename

        # Mark file for cleanup by adding creation timestamp
        temp_path.touch()

        return temp_path

    def cleanup_temp_dir(self, dir_name: str, force: bool = False) -> Dict[str, Any]:
        """Clean up a specific temporary directory based on retention policy."""
        if dir_name not in self.temp_dirs:
            return {'error': f"Directory '{dir_name}' not registered"}

        temp_dir = self.temp_dirs[dir_name]
        policy = self.retention_policies[dir_name]

        if not temp_dir.exists():
            return {'files_removed': 0, 'space_freed_mb': 0}

        # Check if cleanup is due
        if not force:
            time_since_last = datetime.now() - policy['last_cleanup']
            if time_since_last.total_seconds() < policy['cleanup_interval_minutes'] * 60:
                return {'files_removed': 0, 'space_freed_mb': 0, 'skipped': 'not_due'}

        files_removed = 0
        space_freed = 0
        errors = []

        try:
            # Get all files in directory
            all_files = []
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    all_files.append(file_path)

            # Sort by modification time (oldest first)
            all_files.sort(key=lambda x: x.stat().st_mtime)

            # Clean up based on retention policy
            cutoff_time = time.time() - (policy['retention_hours'] * 3600)

            for file_path in all_files:
                try:
                    stat = file_path.stat()
                    file_age = stat.st_mtime

                    # Remove if older than retention period
                    if file_age < cutoff_time:
                        space_freed += stat.st_size
                        file_path.unlink()
                        files_removed += 1
                        logger.debug(f"Cleaned old temp file: {file_path}")

                except Exception as e:
                    error_msg = f"Failed to clean {file_path}: {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg)

            # Check directory size and clean oldest files if over limit
            dir_size_mb = self._get_dir_size_mb(temp_dir)
            if dir_size_mb > policy['max_size_mb']:
                remaining_files = []
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        remaining_files.append(file_path)

                remaining_files.sort(key=lambda x: x.stat().st_mtime)

                for file_path in remaining_files:
                    if dir_size_mb <= policy['max_size_mb']:
                        break

                    try:
                        stat = file_path.stat()
                        space_freed += stat.st_size
                        dir_size_mb -= (stat.st_size / (1024 * 1024))
                        file_path.unlink()
                        files_removed += 1
                        logger.debug(f"Cleaned oversized temp file: {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to clean oversized file {file_path}: {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg)

        except Exception as e:
            error_msg = f"Failed to cleanup directory {temp_dir}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)

        # Update last cleanup time
        policy['last_cleanup'] = datetime.now()

        result = {
            'files_removed': files_removed,
            'space_freed_mb': round(space_freed / (1024 * 1024), 2),
            'errors': errors
        }

        if files_removed > 0:
            logger.info(f"Cleaned {dir_name}: {files_removed} files, {result['space_freed_mb']:.2f} MB freed")

        return result

    def cleanup_all(self, force: bool = False) -> Dict[str, Dict]:
        """Clean up all registered temporary directories."""
        logger.info("Starting comprehensive temp file cleanup")
        results = {}

        for dir_name in self.temp_dirs.keys():
            results[dir_name] = self.cleanup_temp_dir(dir_name, force)

        total_files = sum(r.get('files_removed', 0) for r in results.values())
        total_space = sum(r.get('space_freed_mb', 0) for r in results.values())

        logger.info(f"Cleanup completed: {total_files} files removed, {total_space:.2f} MB freed")

        return results

    def start_background_cleanup(self):
        """Start background cleanup thread."""
        if self.running:
            return

        self.running = True
        self.cleanup_thread = threading.Thread(target=self._background_cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("Background cleanup thread started")

    def stop_background_cleanup(self):
        """Stop background cleanup thread."""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)

    def _background_cleanup_worker(self):
        """Background cleanup worker thread."""
        while self.running:
            try:
                # Run cleanup for all directories
                self.cleanup_all()

                # Sleep for 30 minutes
                time.sleep(30 * 60)

            except Exception as e:
                logger.error(f"Background cleanup error: {e}")
                time.sleep(5 * 60)  # Wait 5 minutes before retrying

    def _get_dir_size_mb(self, path: Path) -> float:
        """Get directory size in MB."""
        total_size = 0
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception:
            pass
        return total_size / (1024 * 1024)

    def get_stats(self) -> Dict[str, Dict]:
        """Get statistics for all temp directories."""
        stats = {}
        for dir_name, temp_dir in self.temp_dirs.items():
            policy = self.retention_policies[dir_name]
            dir_stats = {
                'path': str(temp_dir),
                'exists': temp_dir.exists(),
                'retention_hours': policy['retention_hours'],
                'max_size_mb': policy['max_size_mb'],
                'last_cleanup': policy['last_cleanup'].isoformat(),
            }

            if temp_dir.exists():
                try:
                    files = list(temp_dir.rglob("*"))
                    file_count = len([f for f in files if f.is_file()])
                    dir_size_mb = self._get_dir_size_mb(temp_dir)

                    dir_stats.update({
                        'file_count': file_count,
                        'total_size_mb': round(dir_size_mb, 2),
                        'oldest_file_age_hours': self._get_oldest_file_age(temp_dir)
                    })
                except Exception as e:
                    dir_stats['error'] = str(e)

            stats[dir_name] = dir_stats

        return stats

    def _get_oldest_file_age(self, path: Path) -> Optional[float]:
        """Get age of oldest file in directory in hours."""
        try:
            oldest_time = float('inf')
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    oldest_time = min(oldest_time, file_path.stat().st_mtime)

            if oldest_time != float('inf'):
                return (time.time() - oldest_time) / 3600
        except Exception:
            pass
        return None


# Global instance
_temp_manager: Optional[TempFileManager] = None


def get_temp_manager() -> TempFileManager:
    """Get or create the global temp file manager."""
    global _temp_manager
    if _temp_manager is None:
        _temp_manager = TempFileManager()
    return _temp_manager


def init_temp_manager():
    """Initialize the temp file manager with default directories."""
    manager = get_temp_manager()

    # Define standard temp directories
    temp_dirs = [
        ("default", Path("temp"), 24, 500),  # 24 hours, 500MB max
        ("video_temp", Path("temp") / "videos", 6, 1000),  # 6 hours, 1GB max
        ("audio_temp", Path("temp") / "audio", 12, 200),  # 12 hours, 200MB max
        ("subtitles_temp", Path("temp") / "subtitles", 48, 100),  # 48 hours, 100MB max
    ]

    for name, path, retention, max_size in temp_dirs:
        manager.register_temp_dir(name, path, retention, max_size)

    logger.info("Temp file manager initialized with default directories")


def cleanup_temp_files_on_startup():
    """Clean up temp files on application startup."""
    try:
        manager = get_temp_manager()
        results = manager.cleanup_all(force=True)

        total_files = sum(r.get('files_removed', 0) for r in results.values())
        total_space = sum(r.get('space_freed_mb', 0) for r in results.values())

        logger.info(f"Startup cleanup: {total_files} files removed, {total_space:.2f} MB freed")

    except Exception as e:
        logger.error(f"Failed to cleanup temp files on startup: {e}")
