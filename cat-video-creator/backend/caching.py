"""
Advanced caching strategies for the AI Video Generator.
"""

import os
import json
import hashlib
import pickle
import time
import threading
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Callable, Union
from pathlib import Path
from functools import wraps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from logging_config import get_logger

logger = get_logger("caching")


class CacheBackend:
    """Abstract base class for cache backends."""
    
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    def clear(self) -> bool:
        raise NotImplementedError
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """In-memory cache with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.access_times: Dict[str, float] = {}
    
    def _is_expired(self, key: str) -> bool:
        """Check if a cache entry is expired."""
        if key not in self.cache:
            return True
        
        entry = self.cache[key]
        if entry.get('ttl') is None:
            return False
        
        return time.time() > entry['created_at'] + entry['ttl']
    
    def _evict_if_needed(self):
        """Evict old entries if cache is full."""
        if len(self.cache) <= self.max_size:
            return
        
        # Remove expired entries first
        expired_keys = [k for k in self.cache.keys() if self._is_expired(k)]
        for key in expired_keys:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
        
        # If still over limit, remove least recently used
        while len(self.cache) > self.max_size:
            if not self.access_times:
                break
            
            lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            self.cache.pop(lru_key, None)
            self.access_times.pop(lru_key, None)
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if self._is_expired(key):
                self.cache.pop(key, None)
                self.access_times.pop(key, None)
                return None
            
            if key in self.cache:
                self.access_times[key] = time.time()
                return self.cache[key]['value']
            
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self.lock:
            self._evict_if_needed()
            
            self.cache[key] = {
                'value': value,
                'created_at': time.time(),
                'ttl': ttl or self.default_ttl
            }
            self.access_times[key] = time.time()
            return True
    
    def delete(self, key: str) -> bool:
        with self.lock:
            deleted = key in self.cache
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
            return deleted
    
    def clear(self) -> bool:
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            return True
    
    def exists(self, key: str) -> bool:
        with self.lock:
            return key in self.cache and not self._is_expired(key)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            expired_count = sum(1 for k in self.cache.keys() if self._is_expired(k))
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'expired_entries': expired_count,
                'hit_rate': getattr(self, '_hit_rate', 0.0)
            }


class RedisCache(CacheBackend):
    """Redis-based cache backend."""
    
    def __init__(self, redis_url: Optional[str] = None, key_prefix: str = "videogen:"):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/1")
        self.key_prefix = key_prefix
        self.client = None
        self.enabled = False
        
        if REDIS_AVAILABLE:
            try:
                self.client = redis.from_url(self.redis_url)
                self.client.ping()
                self.enabled = True
                logger.info(f"✅ Redis cache initialized: {self.redis_url}")
            except Exception as e:
                logger.error(f"Redis cache connection failed: {e}")
    
    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.key_prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        
        try:
            data = self.client.get(self._make_key(key))
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Redis cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.enabled:
            return False
        
        try:
            data = pickle.dumps(value)
            if ttl:
                return self.client.setex(self._make_key(key), ttl, data)
            else:
                return self.client.set(self._make_key(key), data)
        except Exception as e:
            logger.error(f"Redis cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        if not self.enabled:
            return False
        
        try:
            return bool(self.client.delete(self._make_key(key)))
        except Exception as e:
            logger.error(f"Redis cache delete error: {e}")
            return False
    
    def clear(self) -> bool:
        if not self.enabled:
            return False
        
        try:
            keys = self.client.keys(f"{self.key_prefix}*")
            if keys:
                return bool(self.client.delete(*keys))
            return True
        except Exception as e:
            logger.error(f"Redis cache clear error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        if not self.enabled:
            return False
        
        try:
            return bool(self.client.exists(self._make_key(key)))
        except Exception as e:
            logger.error(f"Redis cache exists error: {e}")
            return False


class FileCache(CacheBackend):
    """File-based cache for large objects like video files."""
    
    def __init__(self, cache_dir: str = "cache", max_size_gb: float = 10.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
        self.lock = threading.RLock()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception:
                pass
        return {}
    
    def _save_metadata(self):
        """Save cache metadata."""
        try:
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2))
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        # Use hash of key to avoid filesystem issues
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _cleanup_if_needed(self):
        """Remove old files if cache is too large."""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.iterdir() if f.is_file())
            
            if total_size <= self.max_size_bytes:
                return
            
            # Sort files by access time
            files_with_times = []
            for key, meta in self.metadata.items():
                cache_file = self._get_cache_file(key)
                if cache_file.exists():
                    files_with_times.append((
                        cache_file,
                        meta.get('last_accessed', 0),
                        cache_file.stat().st_size
                    ))
            
            files_with_times.sort(key=lambda x: x[1])  # Sort by access time
            
            # Remove oldest files until under limit
            for cache_file, _, size in files_with_times:
                if total_size <= self.max_size_bytes:
                    break
                
                try:
                    cache_file.unlink()
                    total_size -= size
                    # Remove from metadata
                    key_to_remove = None
                    for k, meta in self.metadata.items():
                        if self._get_cache_file(k) == cache_file:
                            key_to_remove = k
                            break
                    if key_to_remove:
                        self.metadata.pop(key_to_remove, None)
                except Exception as e:
                    logger.error(f"Failed to remove cache file {cache_file}: {e}")
            
            self._save_metadata()
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            cache_file = self._get_cache_file(key)
            
            if not cache_file.exists():
                return None
            
            # Check TTL
            if key in self.metadata:
                meta = self.metadata[key]
                if meta.get('ttl') and time.time() > meta['created_at'] + meta['ttl']:
                    self.delete(key)
                    return None
                
                # Update access time
                meta['last_accessed'] = time.time()
                self._save_metadata()
            
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache file {cache_file}: {e}")
                self.delete(key)
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self.lock:
            self._cleanup_if_needed()
            
            cache_file = self._get_cache_file(key)
            
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(value, f)
                
                self.metadata[key] = {
                    'created_at': time.time(),
                    'last_accessed': time.time(),
                    'ttl': ttl,
                    'size': cache_file.stat().st_size
                }
                self._save_metadata()
                return True
                
            except Exception as e:
                logger.error(f"Failed to save cache file {cache_file}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        with self.lock:
            cache_file = self._get_cache_file(key)
            deleted = False
            
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to delete cache file {cache_file}: {e}")
            
            if key in self.metadata:
                self.metadata.pop(key)
                self._save_metadata()
                deleted = True
            
            return deleted
    
    def clear(self) -> bool:
        with self.lock:
            try:
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink()
                
                self.metadata.clear()
                self._save_metadata()
                return True
                
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
                return False
    
    def exists(self, key: str) -> bool:
        with self.lock:
            cache_file = self._get_cache_file(key)
            return cache_file.exists() and key in self.metadata


class MultiLevelCache:
    """Multi-level cache with L1 (memory), L2 (Redis), L3 (file) levels."""
    
    def __init__(self, 
                 memory_cache: Optional[MemoryCache] = None,
                 redis_cache: Optional[RedisCache] = None,
                 file_cache: Optional[FileCache] = None):
        self.l1 = memory_cache or MemoryCache(max_size=500, default_ttl=300)  # 5 min
        self.l2 = redis_cache or RedisCache() if REDIS_AVAILABLE else None
        self.l3 = file_cache or FileCache()
        
        self.hit_stats = {
            'l1_hits': 0,
            'l2_hits': 0, 
            'l3_hits': 0,
            'misses': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, checking L1 -> L2 -> L3."""
        # Try L1 (memory)
        value = self.l1.get(key)
        if value is not None:
            self.hit_stats['l1_hits'] += 1
            return value
        
        # Try L2 (Redis)
        if self.l2 and self.l2.enabled:
            value = self.l2.get(key)
            if value is not None:
                self.hit_stats['l2_hits'] += 1
                # Promote to L1
                self.l1.set(key, value, ttl=300)
                return value
        
        # Try L3 (File)
        value = self.l3.get(key)
        if value is not None:
            self.hit_stats['l3_hits'] += 1
            # Promote to L1 and L2
            self.l1.set(key, value, ttl=300)
            if self.l2 and self.l2.enabled:
                self.l2.set(key, value, ttl=3600)
            return value
        
        self.hit_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
            levels: str = "all") -> bool:
        """Set value in cache levels."""
        success = True
        
        if levels in ("all", "l1"):
            success &= self.l1.set(key, value, ttl=min(ttl or 300, 300))
        
        if levels in ("all", "l2") and self.l2 and self.l2.enabled:
            success &= self.l2.set(key, value, ttl=ttl or 3600)
        
        if levels in ("all", "l3"):
            success &= self.l3.set(key, value, ttl=ttl)
        
        return success
    
    def delete(self, key: str) -> bool:
        """Delete from all cache levels."""
        results = [
            self.l1.delete(key),
            self.l2.delete(key) if self.l2 and self.l2.enabled else True,
            self.l3.delete(key)
        ]
        return any(results)
    
    def clear(self, levels: str = "all") -> bool:
        """Clear cache levels."""
        success = True
        
        if levels in ("all", "l1"):
            success &= self.l1.clear()
        
        if levels in ("all", "l2") and self.l2 and self.l2.enabled:
            success &= self.l2.clear()
        
        if levels in ("all", "l3"):
            success &= self.l3.clear()
        
        return success
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = sum(self.hit_stats.values())
        hit_rate = (total_requests - self.hit_stats['misses']) / max(total_requests, 1)
        
        return {
            'hit_stats': self.hit_stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'l1_stats': self.l1.stats() if hasattr(self.l1, 'stats') else {},
            'redis_available': self.l2.enabled if self.l2 else False
        }


# Cache decorators
def cached(ttl: int = 3600, key_func: Optional[Callable] = None, 
          cache_instance: Optional[MultiLevelCache] = None):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = cache_instance or get_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key based on function name and arguments
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        wrapper._cached = True
        wrapper._cache_ttl = ttl
        return wrapper
    return decorator


def cache_key(*key_parts):
    """Generate a cache key from parts."""
    return hashlib.md5(":".join(str(part) for part in key_parts).encode()).hexdigest()


# Global cache instance
_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = MultiLevelCache()
        logger.info("✅ Multi-level cache initialized")
    return _cache


def invalidate_cache_pattern(pattern: str):
    """Invalidate cache entries matching a pattern (Redis only)."""
    cache = get_cache()
    if cache.l2 and cache.l2.enabled:
        try:
            keys = cache.l2.client.keys(f"{cache.l2.key_prefix}{pattern}")
            if keys:
                cache.l2.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries matching '{pattern}'")
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern '{pattern}': {e}")


def warm_cache(cache_warmers: List[Callable]):
    """Warm up the cache by pre-loading data."""
    cache = get_cache()
    
    for warmer in cache_warmers:
        try:
            warmer()
            logger.info(f"Cache warmed by {warmer.__name__}")
        except Exception as e:
            logger.error(f"Cache warmer {warmer.__name__} failed: {e}")
