#!/usr/bin/env python3
"""
Caching System for TikYou Video Generator

This module provides a comprehensive caching system for expensive operations
like video analysis, clip conversion, and metadata extraction to improve
performance and reduce redundant processing.
"""

import os
import pickle
import json
import hashlib
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import weakref

from .data_models import CacheEntry, VideoMetadata, VideoAnalysis, ClipInfo
from .exceptions import FileSystemError, TikYouException
from .logging_config import get_logger

logger = get_logger()


class CacheManager:
    """Main cache manager for video processing operations"""
    
    def __init__(self, cache_dir: str = None, max_size_mb: int = 1000,
                 default_ttl_hours: int = 24):
        if cache_dir is None:
            cache_dir = os.path.join(os.getenv("TEMP_DIR", "/app/temp"), "cache")
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self.default_ttl_hours = default_ttl_hours
        self.cache_entries: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_mb': 0.0,
            'oldest_entry': None,
            'newest_entry': None
        }
        
        # Load existing cache entries
        self._load_cache_index()
        
        # Clean up expired entries
        self._cleanup_expired_entries()
        
        logger.info(f"Cache manager initialized: {self.cache_dir}, max_size: {max_size_mb}MB")
    
    def _generate_cache_key(self, operation: str, *args, **kwargs) -> str:
        """Generate a unique cache key for an operation"""
        # Create a deterministic string representation
        key_data = {
            'operation': operation,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        
        # Convert to string and hash
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry"""
        return self.cache_dir / f"{cache_key}.cache"
    
    def _load_cache_index(self):
        """Load cache index from disk"""
        index_file = self.cache_dir / "cache_index.json"
        
        if not index_file.exists():
            return
        
        try:
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            
            for key, entry_data in index_data.items():
                # Convert datetime strings back to datetime objects with error handling
                try:
                    created_at = datetime.fromisoformat(entry_data.get('created_at', '1970-01-01T00:00:00'))
                    last_accessed = datetime.fromisoformat(entry_data.get('last_accessed', entry_data.get('created_at', '1970-01-01T00:00:00')))
                except (ValueError, TypeError):
                    created_at = datetime.now()
                    last_accessed = created_at
                    
                expires_at = None
                if entry_data.get('expires_at'):
                    try:
                        expires_at = datetime.fromisoformat(entry_data['expires_at'])
                    except (ValueError, TypeError):
                        expires_at = None
                
                cache_entry = CacheEntry(
                    key=key,
                    value=None,  # Will be loaded on demand
                    created_at=created_at,
                    last_accessed=last_accessed,
                    access_count=entry_data.get('access_count', 0),
                    expires_at=expires_at
                )
                
                self.cache_entries[key] = cache_entry
            
            logger.info(f"Loaded {len(self.cache_entries)} cache entries from index")
            
        except Exception as e:
            logger.warning(f"Failed to load cache index: {e}")
    
    def _save_cache_index(self):
        """Save cache index to disk"""
        index_file = self.cache_dir / "cache_index.json"
        
        try:
            index_data = {}
            for key, entry in self.cache_entries.items():
                index_data[key] = {
                    'created_at': entry.created_at.isoformat(),
                    'last_accessed': entry.last_accessed.isoformat(),
                    'access_count': entry.access_count,
                    'expires_at': entry.expires_at.isoformat() if entry.expires_at else None
                }
            
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
            
            logger.debug(f"Saved cache index with {len(index_data)} entries")
            
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def _load_cache_value(self, cache_key: str) -> Any:
        """Load cache value from disk"""
        cache_file = self._get_cache_file_path(cache_key)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache value for {cache_key}: {e}")
            return None
    
    def _save_cache_value(self, cache_key: str, value: Any):
        """Save cache value to disk"""
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            
            logger.debug(f"Saved cache value for {cache_key}")
            
        except Exception as e:
            logger.error(f"Failed to save cache value for {cache_key}: {e}")
    
    def _cleanup_expired_entries(self):
        """Remove expired cache entries"""
        with self.lock:
            expired_keys = []
            
            for key, entry in self.cache_entries.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_cache_entry(key)
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _remove_cache_entry(self, cache_key: str):
        """Remove a cache entry completely"""
        if cache_key in self.cache_entries:
            del self.cache_entries[cache_key]
        
        # Remove cache file
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")
    
    def _evict_lru_entries(self, target_size_mb: float):
        """Evict least recently used entries to reach target size"""
        with self.lock:
            # Sort entries by last access time
            sorted_entries = sorted(
                self.cache_entries.items(),
                key=lambda x: x[1].last_accessed
            )
            
            current_size = self._calculate_cache_size()
            evicted_count = 0
            
            for key, entry in sorted_entries:
                if current_size <= target_size_mb:
                    break
                
                self._remove_cache_entry(key)
                evicted_count += 1
                current_size = self._calculate_cache_size()
            
            self.stats['evictions'] += evicted_count
            
            if evicted_count > 0:
                logger.info(f"Evicted {evicted_count} cache entries to free space")
    
    def _calculate_cache_size(self) -> float:
        """Calculate total cache size in MB"""
        total_size = 0
        
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                total_size += cache_file.stat().st_size
            except OSError:
                continue
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def _update_stats(self):
        """Update cache statistics"""
        self.stats['size_mb'] = self._calculate_cache_size()
        
        if self.cache_entries:
            oldest_entry = min(self.cache_entries.values(), key=lambda x: x.created_at)
            newest_entry = max(self.cache_entries.values(), key=lambda x: x.created_at)
            self.stats['oldest_entry'] = oldest_entry.created_at
            self.stats['newest_entry'] = newest_entry.created_at
        else:
            self.stats['oldest_entry'] = None
            self.stats['newest_entry'] = None
    
    def get(self, operation: str, *args, **kwargs) -> Optional[Any]:
        """Get cached value for an operation"""
        cache_key = self._generate_cache_key(operation, *args, **kwargs)
        
        with self.lock:
            if cache_key not in self.cache_entries:
                self.stats['misses'] += 1
                return None
            
            entry = self.cache_entries[cache_key]
            
            # Check if expired
            if entry.is_expired():
                self._remove_cache_entry(cache_key)
                self.stats['misses'] += 1
                return None
            
            # Load value if not in memory
            if entry.value is None:
                entry.value = self._load_cache_value(cache_key)
                if entry.value is None:
                    self._remove_cache_entry(cache_key)
                    self.stats['misses'] += 1
                    return None
            
            # Update access statistics
            cached_value = entry.access()
            self.stats['hits'] += 1
            
            logger.debug(f"Cache hit for {operation}: {cache_key}")
            return cached_value
    
    def set(self, operation: str, value: Any, ttl_hours: Optional[int] = None, 
            *args, **kwargs):
        """Set cached value for an operation"""
        cache_key = self._generate_cache_key(operation, *args, **kwargs)
        ttl_hours = ttl_hours or self.default_ttl_hours
        
        # Calculate expiration time
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        with self.lock:
            # Create cache entry
            entry = CacheEntry(
                key=cache_key,
                value=value,
                expires_at=expires_at
            )
            
            # Save to disk
            self._save_cache_value(cache_key, value)
            
            # Add to memory cache
            self.cache_entries[cache_key] = entry
            
            # Check if we need to evict entries
            current_size = self._calculate_cache_size()
            if current_size > self.max_size_mb:
                self._evict_lru_entries(self.max_size_mb * 0.8)  # Evict to 80% of max size
            
            # Save index
            self._save_cache_index()
            
            logger.debug(f"Cache set for {operation}: {cache_key}")
    
    def invalidate(self, operation: str, *args, **kwargs):
        """Invalidate cached value for an operation"""
        cache_key = self._generate_cache_key(operation, *args, **kwargs)
        
        with self.lock:
            if cache_key in self.cache_entries:
                self._remove_cache_entry(cache_key)
                self._save_cache_index()
                logger.debug(f"Cache invalidated for {operation}: {cache_key}")
    
    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")
            
            # Clear memory cache
            self.cache_entries.clear()
            
            # Remove index file
            index_file = self.cache_dir / "cache_index.json"
            if index_file.exists():
                try:
                    index_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to remove cache index: {e}")
            
            # Reset statistics
            self.stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0,
                'size_mb': 0.0,
                'oldest_entry': None,
                'newest_entry': None
            }
            
            logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            self._update_stats()
            
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                **self.stats,
                'total_entries': len(self.cache_entries),
                'hit_rate_percent': hit_rate,
                'cache_dir': str(self.cache_dir),
                'max_size_mb': self.max_size_mb
            }
    
    def cleanup(self):
        """Perform cache cleanup and maintenance"""
        with self.lock:
            # Remove expired entries
            self._cleanup_expired_entries()
            
            # Check size and evict if necessary
            current_size = self._calculate_cache_size()
            if current_size > self.max_size_mb:
                self._evict_lru_entries(self.max_size_mb * 0.8)
            
            # Save index
            self._save_cache_index()
            
            logger.info("Cache cleanup completed")


class VideoAnalysisCache:
    """Specialized cache for video analysis results"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.operation_prefix = "video_analysis"
    
    def get_analysis(self, video_path: str, sensitivity: float) -> Optional[VideoAnalysis]:
        """Get cached video analysis"""
        # Include file modification time in cache key for invalidation
        try:
            mtime = os.path.getmtime(video_path)
        except OSError:
            mtime = 0
        
        return self.cache_manager.get(
            self.operation_prefix,
            video_path=video_path,
            sensitivity=sensitivity,
            mtime=mtime
        )
    
    def set_analysis(self, video_path: str, sensitivity: float, 
                    analysis: VideoAnalysis, ttl_hours: int = 48):
        """Cache video analysis results"""
        try:
            mtime = os.path.getmtime(video_path)
        except OSError:
            mtime = 0
        
        self.cache_manager.set(
            self.operation_prefix,
            analysis,
            ttl_hours=ttl_hours,
            video_path=video_path,
            sensitivity=sensitivity,
            mtime=mtime
        )
    
    def invalidate_analysis(self, video_path: str, sensitivity: float):
        """Invalidate cached video analysis"""
        try:
            mtime = os.path.getmtime(video_path)
        except OSError:
            mtime = 0
        
        self.cache_manager.invalidate(
            self.operation_prefix,
            video_path=video_path,
            sensitivity=sensitivity,
            mtime=mtime
        )


class VideoMetadataCache:
    """Specialized cache for video metadata"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.operation_prefix = "video_metadata"
    
    def get_metadata(self, video_path: str) -> Optional[VideoMetadata]:
        """Get cached video metadata"""
        try:
            mtime = os.path.getmtime(video_path)
            file_size = os.path.getsize(video_path)
        except OSError:
            return None
        
        return self.cache_manager.get(
            self.operation_prefix,
            video_path=video_path,
            mtime=mtime,
            file_size=file_size
        )
    
    def set_metadata(self, video_path: str, metadata: VideoMetadata, 
                    ttl_hours: int = 168):  # 1 week
        """Cache video metadata"""
        try:
            mtime = os.path.getmtime(video_path)
            file_size = os.path.getsize(video_path)
        except OSError:
            return
        
        self.cache_manager.set(
            self.operation_prefix,
            metadata,
            ttl_hours=ttl_hours,
            video_path=video_path,
            mtime=mtime,
            file_size=file_size
        )


class ConvertedClipCache:
    """Specialized cache for converted clips"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.operation_prefix = "converted_clip"
    
    def get_converted_clip(self, source_path: str, target_resolution: tuple) -> Optional[str]:
        """Get cached converted clip path"""
        try:
            mtime = os.path.getmtime(source_path)
        except OSError:
            return None
        
        return self.cache_manager.get(
            self.operation_prefix,
            source_path=source_path,
            target_resolution=target_resolution,
            mtime=mtime
        )
    
    def set_converted_clip(self, source_path: str, target_resolution: tuple, 
                          output_path: str, ttl_hours: int = 72):  # 3 days
        """Cache converted clip path"""
        try:
            mtime = os.path.getmtime(source_path)
        except OSError:
            return
        
        self.cache_manager.set(
            self.operation_prefix,
            output_path,
            ttl_hours=ttl_hours,
            source_path=source_path,
            target_resolution=target_resolution,
            mtime=mtime
        )


class MemoryCache:
    """In-memory cache for frequently accessed data"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_order: List[str] = []
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache"""
        with self.lock:
            if key in self.cache:
                # Update access order (LRU)
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            return None
    
    def set(self, key: str, value: Any):
        """Set value in memory cache"""
        with self.lock:
            if key in self.cache:
                # Update existing
                self.access_order.remove(key)
            elif len(self.cache) >= self.max_size:
                # Evict least recently used
                lru_key = self.access_order.pop(0)
                del self.cache[lru_key]
            
            self.cache[key] = value
            self.access_order.append(key)
    
    def clear(self):
        """Clear memory cache"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


# Global cache instances
_global_cache_manager = None
_global_video_analysis_cache = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    return _global_cache_manager


def get_video_analysis_cache() -> VideoAnalysisCache:
    """Get global video analysis cache instance"""
    global _global_video_analysis_cache
    if _global_video_analysis_cache is None:
        _global_video_analysis_cache = VideoAnalysisCache(get_cache_manager())
    return _global_video_analysis_cache