"""
Centralized FFmpeg Process Pool Manager

Provides thread-safe limiting of concurrent FFmpeg processes to prevent
resource exhaustion across all video processing workflows.

This module provides:
- Semaphore-based process limiting
- Automatic GPU detection and configuration
- Process timeout handling
- Pool statistics and monitoring
"""

import os
import subprocess
import threading
import time
import shutil
from typing import List, Optional, Any, Dict
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from ..logging_config import get_logger

logger = get_logger("ffmpeg_pool")


class FFmpegEncoder(Enum):
    """Available FFmpeg encoders."""
    CPU_H264 = "libx264"
    CPU_H265 = "libx265"
    NVIDIA_H264 = "h264_nvenc"
    NVIDIA_H265 = "hevc_nvenc"
    APPLE_H264 = "h264_videotoolbox"
    APPLE_H265 = "hevc_videotoolbox"


@dataclass
class FFmpegPoolConfig:
    """Configuration for FFmpeg process pool."""
    max_processes: int = 2
    default_timeout: float = 600.0  # 10 minutes
    use_gpu: bool = True
    preferred_encoder: Optional[FFmpegEncoder] = None
    
    @classmethod
    def from_env(cls) -> "FFmpegPoolConfig":
        """Create config from environment variables."""
        return cls(
            max_processes=int(os.getenv("MAX_FFMPEG_PROCESSES", "2")),
            default_timeout=float(os.getenv("FFMPEG_TIMEOUT", "600")),
            use_gpu=os.getenv("FFMPEG_USE_GPU", "true").lower() == "true"
        )


class FFmpegPool:
    """
    Centralized FFmpeg process pool manager.
    
    Features:
    - Thread-safe semaphore-based limiting
    - Automatic GPU encoder detection
    - Process timeout handling
    - Statistics and monitoring
    - Cross-platform support
    """
    
    _instance: Optional["FFmpegPool"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "FFmpegPool":
        """Singleton pattern for global pool."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize the FFmpeg pool."""
        if self._initialized:
            return
            
        self.config = FFmpegPoolConfig.from_env()
        self._semaphore = threading.Semaphore(self.config.max_processes)
        self._process_lock = threading.Lock()
        self._active_processes = 0
        self._total_commands = 0
        self._failed_commands = 0
        self._total_wait_time = 0.0
        self._total_execution_time = 0.0
        
        # Detect available GPU encoder
        self._gpu_encoder = self._detect_gpu_encoder() if self.config.use_gpu else None
        
        self._initialized = True
        logger.info(f"FFmpeg pool initialized: max_processes={self.config.max_processes}, "
                   f"gpu_encoder={self._gpu_encoder}")
    
    def _detect_gpu_encoder(self) -> Optional[FFmpegEncoder]:
        """Detect available GPU encoder."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            encoders_output = result.stdout
            
            # Check for NVIDIA
            if "h264_nvenc" in encoders_output:
                logger.info("Detected NVIDIA GPU encoder (h264_nvenc)")
                return FFmpegEncoder.NVIDIA_H264
            
            # Check for Apple VideoToolbox (macOS)
            if "h264_videotoolbox" in encoders_output:
                logger.info("Detected Apple VideoToolbox encoder")
                return FFmpegEncoder.APPLE_H264
            
            logger.info("No GPU encoder detected, using CPU encoding")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to detect GPU encoder: {e}")
            return None
    
    @property
    def gpu_encoder(self) -> Optional[FFmpegEncoder]:
        """Get the detected GPU encoder."""
        return self._gpu_encoder
    
    @property
    def preferred_codec(self) -> str:
        """Get the preferred codec string for ffmpeg."""
        if self._gpu_encoder:
            return self._gpu_encoder.value
        return FFmpegEncoder.CPU_H264.value
    
    @contextmanager
    def process_slot(self):
        """
        Context manager for acquiring a slot in the FFmpeg process pool.
        
        Usage:
            with ffmpeg_pool.process_slot():
                subprocess.run(ffmpeg_command, ...)
        """
        wait_start = time.time()
        
        # Acquire semaphore (blocks if at capacity)
        self._semaphore.acquire()
        
        wait_time = time.time() - wait_start
        with self._process_lock:
            self._active_processes += 1
            self._total_wait_time += wait_time
            
        logger.debug(f"FFmpeg slot acquired ({self._active_processes}/{self.config.max_processes} active, "
                    f"waited {wait_time:.2f}s)")
        
        exec_start = time.time()
        try:
            yield
        finally:
            exec_time = time.time() - exec_start
            with self._process_lock:
                self._active_processes -= 1
                self._total_execution_time += exec_time
            
            self._semaphore.release()
            logger.debug(f"FFmpeg slot released ({self._active_processes}/{self.config.max_processes} active, "
                        f"executed in {exec_time:.2f}s)")
    
    def run_command(
        self,
        cmd: List[str],
        description: str = "FFmpeg operation",
        capture_output: bool = True,
        text: bool = True,
        check: bool = True,
        timeout: Optional[float] = None,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run an FFmpeg command with process pool management.
        
        Args:
            cmd: Command to run (list of strings)
            description: Human-readable description for logging
            capture_output: Whether to capture stdout/stderr
            text: Whether to decode output as text
            check: Whether to raise exception on non-zero exit
            timeout: Optional timeout in seconds (default from config)
            **kwargs: Additional arguments for subprocess.run
            
        Returns:
            CompletedProcess instance
            
        Raises:
            subprocess.CalledProcessError: If check=True and command fails
            subprocess.TimeoutExpired: If timeout is exceeded
            RuntimeError: For critical FFmpeg errors
        """
        if timeout is None:
            timeout = self.config.default_timeout
        
        logger.debug(f"Queuing FFmpeg command: {description}")
        
        with self._process_lock:
            self._total_commands += 1
        
        with self.process_slot():
            logger.debug(f"Executing: {description}")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=capture_output,
                    text=text,
                    check=check,
                    timeout=timeout,
                    **kwargs
                )
                
                # Check for broken pipe errors
                if result.stderr and "Broken pipe" in result.stderr:
                    logger.warning(f"FFmpeg broken pipe in: {description}")
                
                logger.debug(f"Completed: {description}")
                return result
                
            except subprocess.CalledProcessError as e:
                with self._process_lock:
                    self._failed_commands += 1
                
                logger.error(f"FFmpeg failed: {description}, code={e.returncode}")
                
                if e.stderr:
                    stderr = e.stderr[:1000] if isinstance(e.stderr, str) else str(e.stderr)[:1000]
                    logger.error(f"stderr: {stderr}")
                    
                    # Check for common errors
                    if "Broken pipe" in stderr:
                        raise RuntimeError(f"FFmpeg broken pipe: {description}") from e
                    elif "No space left on device" in stderr:
                        raise RuntimeError(f"Disk full: {description}") from e
                    elif "Permission denied" in stderr:
                        raise RuntimeError(f"Permission denied: {description}") from e
                raise
                
            except subprocess.TimeoutExpired as e:
                with self._process_lock:
                    self._failed_commands += 1
                logger.error(f"FFmpeg timeout: {description} (timeout={timeout}s)")
                raise
    
    def run_ffprobe(
        self,
        input_path: str,
        args: Optional[List[str]] = None,
        timeout: float = 30.0
    ) -> subprocess.CompletedProcess:
        """
        Run an FFprobe command with pool management.
        
        Args:
            input_path: Path to input file
            args: Additional ffprobe arguments
            timeout: Timeout in seconds
            
        Returns:
            CompletedProcess with JSON output
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams"
        ]
        
        if args:
            cmd.extend(args)
        
        cmd.append(input_path)
        
        return self.run_command(
            cmd,
            description=f"FFprobe: {os.path.basename(input_path)}",
            timeout=timeout,
            check=True
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._process_lock:
            avg_wait = (self._total_wait_time / self._total_commands 
                       if self._total_commands > 0 else 0)
            avg_exec = (self._total_execution_time / self._total_commands
                       if self._total_commands > 0 else 0)
            
            return {
                "max_processes": self.config.max_processes,
                "active_processes": self._active_processes,
                "available_slots": self.config.max_processes - self._active_processes,
                "total_commands": self._total_commands,
                "failed_commands": self._failed_commands,
                "success_rate": ((self._total_commands - self._failed_commands) / self._total_commands * 100
                                if self._total_commands > 0 else 100),
                "avg_wait_time": avg_wait,
                "avg_execution_time": avg_exec,
                "gpu_encoder": self._gpu_encoder.value if self._gpu_encoder else None
            }
    
    def log_stats(self):
        """Log current pool statistics."""
        stats = self.get_stats()
        logger.info(
            f"FFmpeg Pool Stats: {stats['active_processes']}/{stats['max_processes']} active, "
            f"{stats['total_commands']} total commands, {stats['success_rate']:.1f}% success rate, "
            f"avg wait {stats['avg_wait_time']:.2f}s, avg exec {stats['avg_execution_time']:.2f}s"
        )


# Global pool instance
_pool: Optional[FFmpegPool] = None


def get_ffmpeg_pool() -> FFmpegPool:
    """Get the global FFmpeg pool instance."""
    global _pool
    if _pool is None:
        _pool = FFmpegPool()
    return _pool


def run_ffmpeg_command(
    cmd: List[str],
    description: str = "FFmpeg operation",
    capture_output: bool = True,
    text: bool = True,
    check: bool = True,
    timeout: Optional[float] = None,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """
    Convenience function to run FFmpeg with pool management.
    
    This is the recommended way to run FFmpeg commands across all workflows.
    """
    return get_ffmpeg_pool().run_command(
        cmd=cmd,
        description=description,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
        **kwargs
    )


@contextmanager
def ffmpeg_process_slot():
    """
    Convenience context manager for acquiring an FFmpeg slot.
    
    Use this when you need to run multiple FFmpeg commands in sequence
    without releasing the slot in between.
    """
    with get_ffmpeg_pool().process_slot():
        yield


def get_preferred_codec() -> str:
    """Get the preferred video codec (GPU if available, else CPU)."""
    return get_ffmpeg_pool().preferred_codec


def get_pool_stats() -> Dict[str, Any]:
    """Get FFmpeg pool statistics."""
    return get_ffmpeg_pool().get_stats()


def log_pool_stats():
    """Log FFmpeg pool statistics."""
    get_ffmpeg_pool().log_stats()


# Check FFmpeg availability on import
def _check_ffmpeg():
    """Verify FFmpeg is installed."""
    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg not found in PATH - video processing will fail")
    if not shutil.which("ffprobe"):
        logger.warning("FFprobe not found in PATH - video analysis will fail")


_check_ffmpeg()
