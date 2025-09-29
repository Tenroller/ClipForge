"""
Intelligent caching system for VideoHelper.

This module provides intelligent caching for expensive operations like:
- Video downloads
- AI text generation
- Subtitle processing
- TTS audio generation
- Video processing results
"""

import os
import time
import hashlib
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Callable
from dataclasses import dataclass, asdict, field
from ..logging_config import get_logger

logger = get_logger("cache_manager")


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    data: Any
    created_at: float
    expires_at: Optional[float]
    access_count: int = 0
    last_accessed: float = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.last_accessed:
            self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'key': self.key,
            'data': self.data,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed,
            'size_bytes': self.size_bytes,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary."""
        return cls(
            key=data['key'],
            data=data['data'],
            created_at=data['created_at'],
            expires_at=data.get('expires_at'),
            access_count=data.get('access_count', 0),
            last_accessed=data.get('last_accessed', data['created_at']),
            size_bytes=data.get('size_bytes', 0),
            metadata=data.get('metadata', {})
        )


class CacheManager:
    """
    Intelligent cache manager with multiple cache types and strategies.

    Features:
    - Memory and disk caching
    - TTL (time-to-live) support
    - LRU (least recently used) eviction
    - Size-based eviction
    - Cache hit/miss statistics
    - Automatic cleanup
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_memory_mb: int = 100,
                 max_disk_mb: int = 1000, default_ttl_hours: int = 24):
        self.cache_dir = cache_dir or Path("cache")
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_disk_bytes = max_disk_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_hours * 3600
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_memory': 0,
            'size_disk': 0
        }

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing cache from disk
        self._load_cache_from_disk()

        # Start cleanup thread
        self.cleanup_interval = 3600  # 1 hour
        self._start_cleanup_thread()

        logger.info(f"Cache manager initialized: memory={max_memory_mb}MB, disk={max_disk_mb}MB")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        # Try memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired():
                entry.access_count += 1
                entry.last_accessed = time.time()
                self.stats['hits'] += 1
                return entry.data
            else:
                # Remove expired entry
                del self.memory_cache[key]

        # Try disk cache
        disk_entry = self._load_from_disk(key)
        if disk_entry and not disk_entry.is_expired():
            # Move to memory cache if there's space
            if self._can_fit_in_memory(disk_entry.size_bytes):
                self.memory_cache[key] = disk_entry
                self.stats['size_memory'] += disk_entry.size_bytes
                disk_entry.access_count += 1
                disk_entry.last_accessed = time.time()

            self.stats['hits'] += 1
            return disk_entry.data

        self.stats['misses'] += 1
        return default

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None,
            metadata: Dict[str, Any] = {}) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata

        Returns:
            True if successfully cached
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds

        expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None

        # Estimate size
        size_bytes = self._estimate_size(value)

        # Create cache entry
        entry = CacheEntry(
            key=key,
            data=value,
            created_at=time.time(),
            expires_at=expires_at,
            size_bytes=size_bytes,
            metadata=metadata or {}
        )

        # Try to store in memory first
        if self._can_fit_in_memory(size_bytes):
            self.memory_cache[key] = entry
            self.stats['size_memory'] += size_bytes

            # Also save to disk for persistence
            self._save_to_disk(entry)
            return True

        # Store on disk only
        return self._save_to_disk(entry)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        deleted = False

        # Remove from memory
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            self.stats['size_memory'] -= entry.size_bytes
            del self.memory_cache[key]
            deleted = True

        # Remove from disk
        if self._delete_from_disk(key):
            deleted = True

        if deleted:
            logger.debug(f"Deleted cache entry: {key}")

        return deleted

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        memory_count = len(self.memory_cache)
        self.memory_cache.clear()
        self.stats['size_memory'] = 0

        disk_count = self._clear_disk_cache()

        total_cleared = memory_count + disk_count
        logger.info(f"Cleared {total_cleared} cache entries ({memory_count} memory, {disk_count} disk)")

        return total_cleared

    def cleanup(self, force: bool = False) -> Dict[str, int]:
        """
        Clean up expired and excess cache entries.

        Args:
            force: Force cleanup regardless of timing

        Returns:
            Cleanup statistics
        """
        logger.info("Starting cache cleanup")

        expired_count = 0
        evicted_count = 0

        # Clean up expired entries
        current_time = time.time()

        # Memory cache
        expired_keys = []
        for key, entry in self.memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            entry = self.memory_cache[key]
            self.stats['size_memory'] -= entry.size_bytes
            del self.memory_cache[key]
            expired_count += 1

        # Disk cache
        expired_count += self._cleanup_disk_cache()

        # Evict least recently used if over limit
        if self.stats['size_memory'] > self.max_memory_bytes * 0.9:  # 90% threshold
            evicted_count = self._evict_lru_memory()

        result = {
            'expired_removed': expired_count,
            'evicted': evicted_count,
            'memory_entries': len(self.memory_cache),
            'memory_size_mb': self.stats['size_memory'] / (1024 * 1024)
        }

        logger.info(f"Cache cleanup completed: {result}")
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            'memory_entries': len(self.memory_cache),
            'memory_size_mb': round(self.stats['size_memory'] / (1024 * 1024), 2),
            'max_memory_mb': round(self.max_memory_bytes / (1024 * 1024), 2),
            'disk_size_mb': round(self.stats['size_disk'] / (1024 * 1024), 2),
            'max_disk_mb': round(self.max_disk_bytes / (1024 * 1024), 2),
            'hit_rate_percent': round(hit_rate, 2),
            'total_hits': self.stats['hits'],
            'total_misses': self.stats['misses'],
            'total_requests': total_requests,
            'evictions': self.stats['evictions']
        }

    def generate_key(self, *args, **kwargs) -> str:
        """
        Generate a cache key from arguments.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create a deterministic string from arguments
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _can_fit_in_memory(self, size_bytes: int) -> bool:
        """Check if entry can fit in memory cache."""
        return (self.stats['size_memory'] + size_bytes) <= self.max_memory_bytes

    def _estimate_size(self, obj: Any) -> int:
        """Estimate size of object in bytes."""
        try:
            # Try JSON serialization for size estimation
            if isinstance(obj, (dict, list, str, int, float, bool)):
                json_str = json.dumps(obj, default=str)
                return len(json_str.encode('utf-8'))
            else:
                # Fallback: assume 1KB per complex object
                return 1024
        except Exception:
            return 1024

    def _save_to_disk(self, entry: CacheEntry) -> bool:
        """Save cache entry to disk."""
        try:
            cache_file = self.cache_dir / f"{entry.key}.cache"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, default=str)

            self.stats['size_disk'] += entry.size_bytes
            return True
        except Exception as e:
            logger.warning(f"Failed to save cache entry to disk: {e}")
            return False

    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """Load cache entry from disk."""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entry = CacheEntry.from_dict(data)
            return entry
        except Exception as e:
            logger.warning(f"Failed to load cache entry from disk: {e}")
            return None

    def _delete_from_disk(self, key: str) -> bool:
        """Delete cache entry from disk."""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            if cache_file.exists():
                size = cache_file.stat().st_size
                cache_file.unlink()
                self.stats['size_disk'] -= size
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete cache entry from disk: {e}")
            return False

    def _load_cache_from_disk(self):
        """Load all cache entries from disk on startup."""
        if not self.cache_dir.exists():
            return

        loaded_count = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                entry = CacheEntry.from_dict(data)
                if not entry.is_expired():
                    # Only load if it fits in memory
                    if self._can_fit_in_memory(entry.size_bytes):
                        self.memory_cache[entry.key] = entry
                        self.stats['size_memory'] += entry.size_bytes
                        loaded_count += 1
                    else:
                        self.stats['size_disk'] += entry.size_bytes

            except Exception as e:
                logger.warning(f"Failed to load cache file {cache_file}: {e}")

        logger.info(f"Loaded {loaded_count} cache entries from disk")

    def _clear_disk_cache(self) -> int:
        """Clear all disk cache files."""
        cleared = 0
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
                cleared += 1
            self.stats['size_disk'] = 0
        except Exception as e:
            logger.warning(f"Failed to clear disk cache: {e}")

        return cleared

    def _cleanup_disk_cache(self) -> int:
        """Clean up expired disk cache files."""
        expired_count = 0
        current_time = time.time()

        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    expires_at = data.get('expires_at')
                    if expires_at and current_time > expires_at:
                        cache_file.unlink()
                        expired_count += 1
                        self.stats['size_disk'] -= data.get('size_bytes', 0)

                except Exception:
                    # Remove corrupted cache files
                    cache_file.unlink()
                    expired_count += 1

        except Exception as e:
            logger.warning(f"Failed to cleanup disk cache: {e}")

        return expired_count

    def _evict_lru_memory(self) -> int:
        """Evict least recently used entries from memory cache."""
        evicted = 0
        target_size = int(self.max_memory_bytes * 0.8)  # Target 80% of max

        # Sort by last accessed time (oldest first)
        entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].last_accessed
        )

        for key, entry in entries:
            if self.stats['size_memory'] <= target_size:
                break

            self.stats['size_memory'] -= entry.size_bytes
            del self.memory_cache[key]
            evicted += 1

        if evicted > 0:
            self.stats['evictions'] += evicted
            logger.info(f"Evicted {evicted} LRU cache entries")

        return evicted

    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        import threading

        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self.cleanup()
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")

        thread = threading.Thread(target=cleanup_worker, daemon=True, name="cache-cleanup")
        thread.start()
        logger.debug("Cache cleanup thread started")


# Specialized cache functions for VideoHelper
class VideoCacheManager:
    """Specialized cache manager for video processing operations."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    def cache_video_download(self, video_url: str, local_path: str, ttl_hours: int = 168) -> bool:
        """Cache video download information."""
        key = self.cache.generate_key("video_download", video_url)
        return self.cache.set(key, {
            'url': video_url,
            'local_path': local_path,
            'downloaded_at': time.time()
        }, ttl_seconds=ttl_hours * 3600, metadata={'type': 'video_download'})

    def get_cached_video(self, video_url: str) -> Optional[str]:
        """Get cached video path if available."""
        key = self.cache.generate_key("video_download", video_url)
        cached = self.cache.get(key)
        return cached['local_path'] if cached else None

    def cache_ai_generation(self, prompt: str, model: str, result: str, ttl_hours: int = 24) -> bool:
        """Cache AI text generation results."""
        key = self.cache.generate_key("ai_generation", prompt, model)
        return self.cache.set(key, {
            'prompt': prompt,
            'model': model,
            'result': result,
            'generated_at': time.time()
        }, ttl_seconds=ttl_hours * 3600, metadata={'type': 'ai_generation'})

    def get_cached_generation(self, prompt: str, model: str) -> Optional[str]:
        """Get cached AI generation result."""
        key = self.cache.generate_key("ai_generation", prompt, model)
        cached = self.cache.get(key)
        return cached['result'] if cached else None

    def cache_subtitle_processing(self, video_path: str, subtitle_data: Dict, ttl_hours: int = 48) -> bool:
        """Cache subtitle processing results."""
        key = self.cache.generate_key("subtitle_processing", video_path)
        return self.cache.set(key, {
            'video_path': video_path,
            'subtitle_data': subtitle_data,
            'processed_at': time.time()
        }, ttl_seconds=ttl_hours * 3600, metadata={'type': 'subtitle_processing'})

    def get_cached_subtitles(self, video_path: str) -> Optional[Dict]:
        """Get cached subtitle processing results."""
        key = self.cache.generate_key("subtitle_processing", video_path)
        cached = self.cache.get(key)
        return cached['subtitle_data'] if cached else None


# Global instances
_cache_manager: Optional[CacheManager] = None
_video_cache_manager: Optional[VideoCacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def get_video_cache_manager() -> VideoCacheManager:
    """Get or create the global video cache manager instance."""
    global _video_cache_manager
    if _video_cache_manager is None:
        _video_cache_manager = VideoCacheManager(get_cache_manager())
    return _video_cache_manager


def init_cache_manager():
    """Initialize the cache management system."""
    cache_manager = get_cache_manager()
    video_cache = get_video_cache_manager()

    logger.info("Cache management system initialized")


def cleanup_cache():
    """Clean up expired cache entries."""
    cache_manager = get_cache_manager()
    return cache_manager.cleanup(force=True)


# Initialize cache system when module is imported
try:
    init_cache_manager()
except Exception as e:
    logger.error(f"Failed to initialize cache system: {e}")
