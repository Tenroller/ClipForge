"""
GPU memory management utilities for video processing.
"""

import subprocess
import os
import sys
import time
import threading
import psutil
from typing import Dict, Optional, List, Tuple, Any, Callable
from dataclasses import dataclass
import json
try:
    from ..logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger("gpu_manager")


class GPUMemoryManager:
    """
    Intelligent GPU memory manager for video processing applications.

    Features:
    - GPU memory monitoring and usage tracking
    - Automatic memory cleanup and optimization
    - Memory usage predictions and warnings
    - GPU utilization optimization
    """

    def __init__(self):
        self.gpu_available = self._detect_gpu()
        self.memory_stats = {}
        self.usage_history = []
        self.memory_thresholds = {
            'warning': 0.8,  # 80% memory usage warning
            'critical': 0.95,  # 95% memory usage critical
            'cleanup': 0.9   # Trigger cleanup at 90%
        }
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.cleanup_callbacks: List[Callable] = []

        if self.gpu_available:
            logger.info("GPU memory manager initialized")
            self.start_monitoring()
        else:
            logger.info("No GPU detected, memory manager running in CPU-only mode")

    def _detect_gpu(self) -> bool:
        """Detect available GPU and capabilities."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB

                logger.info(f"GPU detected: {gpu_name} ({gpu_count} device(s), {gpu_memory:.1f} GB)")
                return True
        except ImportError:
            logger.debug("PyTorch not available for GPU detection")

        # Try to detect GPU via other methods
        try:
            # Check for NVIDIA GPU
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total',
                                   '--format=csv,noheader,nounits'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines and lines[0] != '[Not Supported]':
                    gpu_info = lines[0].split(',')
                    gpu_name = gpu_info[0].strip()
                    gpu_memory = int(gpu_info[1].strip()) / 1024  # Convert MB to GB

                    logger.info(f"GPU detected via nvidia-smi: {gpu_name} ({gpu_memory:.1f} GB)")
                    return True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        logger.info("No GPU detected")
        return False

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current GPU memory statistics."""
        if not self.gpu_available:
            return {
                'gpu_available': False,
                'cpu_memory': self._get_cpu_memory_stats()
            }

        try:
            import torch

            stats = {
                'gpu_available': True,
                'device_count': torch.cuda.device_count(),
                'devices': []
            }

            for i in range(torch.cuda.device_count()):
                device_stats = {
                    'device_id': i,
                    'name': torch.cuda.get_device_name(i),
                    'total_memory_gb': torch.cuda.get_device_properties(i).total_memory / (1024**3),
                    'allocated_memory_gb': torch.cuda.memory_allocated(i) / (1024**3),
                    'cached_memory_gb': torch.cuda.memory_reserved(i) / (1024**3),
                    'free_memory_gb': (torch.cuda.get_device_properties(i).total_memory -
                                     torch.cuda.memory_reserved(i)) / (1024**3)
                }

                # Calculate usage percentage
                total = device_stats['total_memory_gb']
                allocated = device_stats['allocated_memory_gb']
                device_stats['usage_percentage'] = (allocated / total) * 100 if total > 0 else 0

                stats['devices'].append(device_stats)

            # Overall stats
            if stats['devices']:
                primary_device = stats['devices'][0]
                stats['overall'] = {
                    'total_memory_gb': primary_device['total_memory_gb'],
                    'allocated_memory_gb': primary_device['allocated_memory_gb'],
                    'usage_percentage': primary_device['usage_percentage']
                }

            return stats

        except Exception as e:
            logger.warning(f"Failed to get GPU memory stats: {e}")
            return {
                'gpu_available': False,
                'error': str(e),
                'cpu_memory': self._get_cpu_memory_stats()
            }

    def _get_cpu_memory_stats(self) -> Dict[str, Any]:
        """Get CPU memory statistics as fallback."""
        memory = psutil.virtual_memory()
        return {
            'total_gb': memory.total / (1024**3),
            'available_gb': memory.available / (1024**3),
            'used_gb': memory.used / (1024**3),
            'usage_percentage': memory.percent
        }

    def should_use_gpu(self, estimated_memory_gb: float = 0) -> Dict[str, Any]:
        """
        Determine if GPU should be used for a task.

        Args:
            estimated_memory_gb: Estimated GPU memory required

        Returns:
            Decision with reasoning
        """
        if not self.gpu_available:
            return {
                'use_gpu': False,
                'reason': 'No GPU available',
                'confidence': 'high'
            }

        stats = self.get_memory_stats()
        if not stats.get('devices'):
            return {
                'use_gpu': False,
                'reason': 'No GPU devices accessible',
                'confidence': 'high'
            }

        primary_device = stats['devices'][0]
        available_memory = primary_device['free_memory_gb']
        usage_percentage = primary_device['usage_percentage']

        # Check if we have enough free memory
        if estimated_memory_gb > 0 and available_memory < estimated_memory_gb:
            return {
                'use_gpu': False,
                'reason': f'Insufficient GPU memory (need {estimated_memory_gb:.1f} GB, have {available_memory:.1f} GB free)',
                'confidence': 'high'
            }

        # Check usage thresholds
        if usage_percentage >= self.memory_thresholds['critical'] * 100:
            return {
                'use_gpu': False,
                'reason': f'GPU memory usage too high ({usage_percentage:.1f}%)',
                'confidence': 'high'
            }

        if usage_percentage >= self.memory_thresholds['warning'] * 100:
            return {
                'use_gpu': True,
                'reason': f'GPU available but memory usage high ({usage_percentage:.1f}%)',
                'confidence': 'medium',
                'warning': 'High memory usage detected'
            }

        return {
            'use_gpu': True,
            'reason': f'GPU available with sufficient memory ({available_memory:.1f} GB free)',
            'confidence': 'high'
        }

    def optimize_for_task(self, task_type: str, video_size_mb: int = 0) -> Dict[str, Any]:
        """
        Get optimization settings for a specific task.

        Args:
            task_type: Type of task (video_processing, subtitle_rendering, etc.)
            video_size_mb: Size of video being processed in MB

        Returns:
            Optimization settings
        """
        base_settings = {
            'use_gpu': self.should_use_gpu(),
            'memory_optimization': True,
            'parallel_processing': True
        }

        # Task-specific optimizations
        if task_type == 'video_processing':
            # Estimate memory usage for video processing
            estimated_memory = video_size_mb * 0.1  # Rough estimate: 10% of video size
            gpu_decision = self.should_use_gpu(estimated_memory)

            base_settings.update({
                'estimated_memory_gb': estimated_memory,
                'gpu_decision': gpu_decision,
                'recommended_threads': min(4, max(1, int(video_size_mb / 100))),  # 1 thread per 100MB
                'chunk_processing': video_size_mb > 500,  # Process in chunks for large videos
            })

        elif task_type == 'subtitle_rendering':
            base_settings.update({
                'use_gpu': self.should_use_gpu(0.5),  # Subtitles need ~500MB GPU memory
                'frame_buffering': False,  # Reduce memory usage
                'batch_size': 100  # Process frames in smaller batches
            })

        elif task_type == 'audio_processing':
            base_settings.update({
                'use_gpu': False,  # Audio processing usually better on CPU
                'parallel_workers': min(2, max(1, int(video_size_mb / 200)))
            })

        return base_settings

    def cleanup_gpu_memory(self, force: bool = False) -> Dict[str, Any]:
        """
        Clean up GPU memory.

        Args:
            force: Force cleanup even if not needed

        Returns:
            Cleanup results
        """
        if not self.gpu_available:
            return {'success': False, 'reason': 'No GPU available'}

        try:
            import torch

            stats_before = self.get_memory_stats()
            devices = stats_before.get('devices', [])
            if not devices:
                return {'success': False, 'reason': 'No GPU devices found'}
            primary_device = devices[0]
            usage_before = primary_device.get('usage_percentage', 0)

            # Trigger cleanup if usage is high or forced
            should_cleanup = force or usage_before >= (self.memory_thresholds['cleanup'] * 100)

            if should_cleanup:
                logger.info(f"Starting GPU memory cleanup (usage: {usage_before:.1f}%)")

                # Force garbage collection
                import gc
                gc.collect()

                # Clear PyTorch cache
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()

                # Call cleanup callbacks
                for callback in self.cleanup_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.warning(f"Cleanup callback failed: {e}")

                # Wait a moment for cleanup to take effect
                time.sleep(0.5)

                stats_after = self.get_memory_stats()
                devices_after = stats_after.get('devices', [])
                if not devices_after:
                    usage_after = 0
                else:
                    primary_device_after = devices_after[0]
                    usage_after = primary_device_after.get('usage_percentage', 0)

                memory_freed = max(0, usage_before - usage_after)

                result = {
                    'success': True,
                    'memory_freed_percentage': memory_freed,
                    'usage_before': usage_before,
                    'usage_after': usage_after,
                    'cleanup_performed': True
                }

                logger.info(f"GPU memory cleanup completed: {memory_freed:.1f}% memory freed")
                return result
            else:
                return {
                    'success': True,
                    'cleanup_performed': False,
                    'reason': f'Memory usage ({usage_before:.1f}%) below cleanup threshold'
                }

        except Exception as e:
            logger.error(f"GPU memory cleanup failed: {e}")
            return {'success': False, 'error': str(e)}

    def add_cleanup_callback(self, callback: Callable):
        """Add a callback to be called during memory cleanup."""
        self.cleanup_callbacks.append(callback)

    def start_monitoring(self):
        """Start background memory monitoring."""
        if self.monitoring_active or not self.gpu_available:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="gpu-monitor")
        self.monitor_thread.start()
        logger.info("GPU memory monitoring started")

    def stop_monitoring(self):
        """Stop background memory monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                stats = self.get_memory_stats()
                self.usage_history.append({
                    'timestamp': time.time(),
                    'stats': stats
                })

                # Keep only last 100 entries
                if len(self.usage_history) > 100:
                    self.usage_history = self.usage_history[-100:]

                # Check for high memory usage
                devices = stats.get('devices', [])
                if devices:
                    primary_device = devices[0]
                    usage = primary_device.get('usage_percentage', 0)

                    if usage >= self.memory_thresholds['critical'] * 100:
                        logger.warning(f"Critical GPU memory usage: {usage:.1f}%")
                        self.cleanup_gpu_memory(force=True)
                    elif usage >= self.memory_thresholds['warning'] * 100:
                        logger.info(f"High GPU memory usage: {usage:.1f}%")

            except Exception as e:
                logger.error(f"GPU monitoring error: {e}")

            # Monitor every 30 seconds
            time.sleep(30)

    def get_usage_history(self, minutes: int = 10) -> List[Dict]:
        """
        Get GPU usage history for the last N minutes.

        Args:
            minutes: Number of minutes of history to retrieve

        Returns:
            List of usage data points
        """
        cutoff_time = time.time() - (minutes * 60)
        return [entry for entry in self.usage_history if entry['timestamp'] >= cutoff_time]


# Global instance
_gpu_manager: Optional[GPUMemoryManager] = None


def get_gpu_manager() -> GPUMemoryManager:
    """Get or create the global GPU manager instance."""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUMemoryManager()
    return _gpu_manager


def init_gpu_manager():
    """Initialize the GPU manager."""
    manager = get_gpu_manager()
    if manager.gpu_available:
        logger.info("GPU memory manager initialized with monitoring")
    else:
        logger.info("GPU memory manager initialized (CPU-only mode)")


def should_use_gpu(estimated_memory_gb: float = 0) -> Dict[str, Any]:
    """Convenience function to check if GPU should be used."""
    return get_gpu_manager().should_use_gpu(estimated_memory_gb)


def cleanup_gpu_memory(force: bool = False) -> Dict[str, Any]:
    """Convenience function to cleanup GPU memory."""
    return get_gpu_manager().cleanup_gpu_memory(force)


def get_gpu_stats() -> Dict[str, Any]:
    """Convenience function to get GPU memory stats."""
    return get_gpu_manager().get_memory_stats()


# Initialize GPU manager when module is imported
try:
    init_gpu_manager()
except Exception as e:
    logger.error(f"Failed to initialize GPU manager: {e}")
