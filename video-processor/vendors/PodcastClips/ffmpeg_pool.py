"""
FFmpeg Process Pool Manager

Provides thread-safe limiting of concurrent FFmpeg processes to prevent
resource exhaustion and "Broken pipe" errors.

This is critical when multiple clips are being generated in parallel, as each
clip may spawn 2-3 FFmpeg processes (extraction, normalization, encoding).
Without limits, this can easily create 12-18+ concurrent FFmpeg processes,
leading to system instability and segmentation faults.
"""

import os
import subprocess
import threading
from loguru import logger as loguru_logger
from typing import List, Optional, Any
from contextlib import contextmanager

logger = loguru_logger.bind(name="PodcastClips.ffmpeg_pool")

# Global semaphore to limit concurrent FFmpeg processes
_MAX_FFMPEG_PROCESSES = int(os.getenv("MAX_FFMPEG_PROCESSES", "2"))
_ffmpeg_semaphore = threading.Semaphore(_MAX_FFMPEG_PROCESSES)
_ffmpeg_lock = threading.Lock()
_active_processes = 0


@contextmanager
def ffmpeg_process_slot():
    """
    Context manager for acquiring a slot in the FFmpeg process pool.

    This ensures only MAX_FFMPEG_PROCESSES FFmpeg operations run concurrently.

    Usage:
        with ffmpeg_process_slot():
            subprocess.run(ffmpeg_command, ...)

    The semaphore will block if too many FFmpeg processes are running,
    preventing resource exhaustion.
    """
    global _active_processes

    # Acquire semaphore (blocks if at capacity)
    _ffmpeg_semaphore.acquire()

    with _ffmpeg_lock:
        _active_processes += 1
        logger.debug(f"FFmpeg slot acquired ({_active_processes}/{_MAX_FFMPEG_PROCESSES} active)")

    try:
        yield
    finally:
        # Always release, even if exception occurs
        with _ffmpeg_lock:
            _active_processes -= 1
            logger.debug(f"FFmpeg slot released ({_active_processes}/{_MAX_FFMPEG_PROCESSES} active)")
        _ffmpeg_semaphore.release()


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
    Run an FFmpeg command with process pool management.

    This wrapper automatically acquires a slot in the process pool before
    running the command, preventing too many concurrent FFmpeg processes.

    Args:
        cmd: Command to run (list of strings)
        description: Human-readable description for logging
        capture_output: Whether to capture stdout/stderr
        text: Whether to decode output as text
        check: Whether to raise exception on non-zero exit
        timeout: Optional timeout in seconds
        **kwargs: Additional arguments to pass to subprocess.run

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        subprocess.TimeoutExpired: If timeout is exceeded
        RuntimeError: If FFmpeg command fails with broken pipe or other critical errors
    """
    logger.debug(f"Queuing FFmpeg command: {description}")

    with ffmpeg_process_slot():
        logger.debug(f"Executing FFmpeg command: {description}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=text,
                check=check,
                timeout=timeout,
                **kwargs
            )

            # Check for broken pipe errors in stderr
            if result.stderr and "Broken pipe" in result.stderr:
                logger.warning(f"FFmpeg broken pipe detected in: {description}")
                logger.warning(f"stderr: {result.stderr[:500]}")

            logger.debug(f"FFmpeg command completed: {description}")
            return result

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg command failed: {description}")
            logger.error(f"Return code: {e.returncode}")
            logger.error(f"stderr: {e.stderr[:1000] if e.stderr else 'N/A'}")

            # Check for common error patterns
            if e.stderr:
                if "Broken pipe" in e.stderr:
                    raise RuntimeError(f"FFmpeg broken pipe error in {description}") from e
                elif "No space left on device" in e.stderr:
                    raise RuntimeError(f"Disk full during {description}") from e
                elif "Permission denied" in e.stderr:
                    raise RuntimeError(f"Permission denied during {description}") from e

            raise

        except subprocess.TimeoutExpired as e:
            logger.error(f"FFmpeg command timeout: {description} (timeout={timeout}s)")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in FFmpeg command: {description}")
            logger.error(f"Error: {e}")
            raise


def get_pool_status() -> dict:
    """
    Get current status of the FFmpeg process pool.

    Returns:
        dict with pool statistics
    """
    with _ffmpeg_lock:
        return {
            "max_processes": _MAX_FFMPEG_PROCESSES,
            "active_processes": _active_processes,
            "available_slots": _MAX_FFMPEG_PROCESSES - _active_processes
        }


def log_pool_status():
    """Log current FFmpeg pool status."""
    status = get_pool_status()
    logger.info(
        f"FFmpeg Pool: {status['active_processes']}/{status['max_processes']} active, "
        f"{status['available_slots']} slots available"
    )
