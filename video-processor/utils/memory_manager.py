"""
Centralized Memory Manager for Video Processing.

Provides intelligent memory management with automatic cleanup to prevent
OOM errors during intensive video processing operations.

Features:
- Automatic garbage collection under memory pressure
- GPU memory management (CUDA cache clearing)
- Context manager for processing blocks
- Memory monitoring and statistics
"""

import gc
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable

import psutil

from ..logging_config import get_logger

logger = get_logger("memory_manager")


# Try to import torch for GPU memory management
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class MemoryStats:
    """Memory statistics snapshot."""
    total_mb: float
    used_mb: float
    available_mb: float
    percent_used: float
    gpu_used_mb: Optional[float] = None
    gpu_total_mb: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_mb": self.total_mb,
            "used_mb": self.used_mb,
            "available_mb": self.available_mb,
            "percent_used": self.percent_used,
            "gpu_used_mb": self.gpu_used_mb,
            "gpu_total_mb": self.gpu_total_mb
        }


class MemoryManager:
    """
    Centralized memory manager for video processing workflows.
    
    Provides automatic cleanup under memory pressure and a context manager
    for processing blocks that ensures cleanup on exit.
    
    Usage:
        manager = get_memory_manager()
        
        with manager.managed_processing("video_encoding"):
            # Memory-intensive operation
            encode_video(...)
        
        # Cleanup happens automatically on context exit
    """
    
    _instance: Optional["MemoryManager"] = None
    _lock = threading.Lock()
    
    # Memory thresholds
    WARNING_THRESHOLD_PERCENT = 80.0
    CRITICAL_THRESHOLD_PERCENT = 90.0
    
    def __new__(cls) -> "MemoryManager":
        """Singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._cleanup_count = 0
        self._last_cleanup_time = 0.0
        self._min_cleanup_interval = 5.0  # Seconds between cleanups
        self._callbacks: list[Callable] = []
        self._initialized = True
        
        logger.info("MemoryManager initialized")
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        mem = psutil.virtual_memory()
        
        stats = MemoryStats(
            total_mb=mem.total / (1024 * 1024),
            used_mb=mem.used / (1024 * 1024),
            available_mb=mem.available / (1024 * 1024),
            percent_used=mem.percent
        )
        
        # Check GPU memory if available
        if HAS_TORCH and torch.cuda.is_available():
            try:
                gpu_used = torch.cuda.memory_allocated() / (1024 * 1024)
                gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                stats.gpu_used_mb = gpu_used
                stats.gpu_total_mb = gpu_total
            except Exception:
                pass
        
        return stats
    
    def check_memory_pressure(self) -> str:
        """
        Check current memory pressure level.
        
        Returns:
            "ok", "warning", or "critical"
        """
        stats = self.get_memory_stats()
        
        if stats.percent_used >= self.CRITICAL_THRESHOLD_PERCENT:
            return "critical"
        elif stats.percent_used >= self.WARNING_THRESHOLD_PERCENT:
            return "warning"
        return "ok"
    
    def cleanup(self, force: bool = False) -> Dict[str, Any]:
        """
        Perform memory cleanup.
        
        Args:
            force: Force cleanup even if recently cleaned
            
        Returns:
            Cleanup statistics
        """
        # Rate limiting
        current_time = time.time()
        if not force and (current_time - self._last_cleanup_time) < self._min_cleanup_interval:
            return {"skipped": True, "reason": "rate_limited"}
        
        stats_before = self.get_memory_stats()
        
        # Python garbage collection
        gc.collect()
        
        # GPU memory cleanup
        if HAS_TORCH and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            except Exception as e:
                logger.warning(f"GPU cleanup failed: {e}")
        
        # Force a second gc pass
        gc.collect()
        
        stats_after = self.get_memory_stats()
        
        self._cleanup_count += 1
        self._last_cleanup_time = current_time
        
        freed_mb = stats_before.used_mb - stats_after.used_mb
        
        if freed_mb > 10:  # Only log significant cleanups
            logger.info(f"Memory cleanup freed {freed_mb:.1f}MB "
                       f"({stats_before.percent_used:.1f}% -> {stats_after.percent_used:.1f}%)")
        
        return {
            "freed_mb": freed_mb,
            "before_percent": stats_before.percent_used,
            "after_percent": stats_after.percent_used,
            "cleanup_count": self._cleanup_count
        }
    
    def cleanup_if_needed(self) -> Optional[Dict[str, Any]]:
        """
        Perform cleanup only if memory pressure is high.
        
        Returns:
            Cleanup stats if cleanup was performed, None otherwise
        """
        pressure = self.check_memory_pressure()
        
        if pressure == "critical":
            logger.warning("Critical memory pressure detected, forcing cleanup")
            return self.cleanup(force=True)
        elif pressure == "warning":
            return self.cleanup(force=False)
        
        return None
    
    @contextmanager
    def managed_processing(self, label: str = "processing"):
        """
        Context manager for memory-intensive processing.
        
        Automatically cleans up memory on exit and handles pressure during processing.
        
        Args:
            label: Label for logging
            
        Usage:
            with memory_manager.managed_processing("video_encoding"):
                # Memory-intensive operation
                ...
        """
        stats_before = self.get_memory_stats()
        logger.debug(f"Starting {label}: memory at {stats_before.percent_used:.1f}%")
        
        try:
            yield self
        finally:
            # Always cleanup on exit
            cleanup_result = self.cleanup(force=False)
            stats_after = self.get_memory_stats()
            
            logger.debug(f"Finished {label}: memory at {stats_after.percent_used:.1f}% "
                        f"(freed {cleanup_result.get('freed_mb', 0):.1f}MB)")
    
    @contextmanager
    def monitor_processing(self, label: str = "processing", interval: float = 30.0):
        """
        Context manager that monitors memory during long processing.
        
        Periodically checks memory and cleans up if needed.
        
        Args:
            label: Label for logging
            interval: Monitoring interval in seconds
        """
        stop_event = threading.Event()
        
        def monitor_thread():
            while not stop_event.wait(interval):
                pressure = self.check_memory_pressure()
                if pressure != "ok":
                    logger.info(f"Memory pressure during {label}: {pressure}")
                    self.cleanup_if_needed()
        
        thread = threading.Thread(target=monitor_thread, daemon=True)
        thread.start()
        
        try:
            with self.managed_processing(label):
                yield self
        finally:
            stop_event.set()
            thread.join(timeout=1.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory manager statistics."""
        mem_stats = self.get_memory_stats()
        return {
            "current": mem_stats.to_dict(),
            "pressure": self.check_memory_pressure(),
            "cleanup_count": self._cleanup_count,
            "last_cleanup": self._last_cleanup_time
        }
    
    def log_stats(self):
        """Log current memory statistics."""
        stats = self.get_memory_stats()
        pressure = self.check_memory_pressure()
        
        msg = (f"Memory: {stats.percent_used:.1f}% used "
               f"({stats.available_mb:.0f}MB available), pressure: {pressure}")
        
        if stats.gpu_used_mb is not None:
            msg += f", GPU: {stats.gpu_used_mb:.0f}MB/{stats.gpu_total_mb:.0f}MB"
        
        if pressure == "critical":
            logger.warning(msg)
        elif pressure == "warning":
            logger.info(msg)
        else:
            logger.debug(msg)


# Global instance
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager


def cleanup_memory(force: bool = False) -> Dict[str, Any]:
    """Convenience function to cleanup memory."""
    return get_memory_manager().cleanup(force)


def cleanup_memory_if_needed() -> Optional[Dict[str, Any]]:
    """Convenience function to cleanup if memory pressure is high."""
    return get_memory_manager().cleanup_if_needed()


@contextmanager
def managed_processing(label: str = "processing"):
    """Convenience context manager for memory-managed processing."""
    with get_memory_manager().managed_processing(label):
        yield
