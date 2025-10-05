"""
FastAPI application lifespan management.
"""

import asyncio
import signal
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any
from collections import defaultdict

from fastapi import FastAPI

try:
    from ..logging_config import initialize_logging, get_logger
    from ..metrics import init_metrics_system
except ImportError:
    # Fallback for when running from backend directory
    from logging_config import initialize_logging, get_logger
    from metrics import init_metrics_system

# Global state for lifespan management
MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None
_SHUTDOWN_IN_PROGRESS = False
_CLEANUP_COMPLETED = False

logger = get_logger("lifespan")


def _is_interpreter_shutting_down():
    """Check if the Python interpreter is shutting down."""
    try:
        # Check if the interpreter is shutting down
        return sys.is_finalizing()
    except AttributeError:
        # sys.is_finalizing() is Python 3.7+, fallback to checking thread count
        return len(threading.enumerate()) <= 2  # Only main thread + daemon threads


def _signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    global _SHUTDOWN_IN_PROGRESS
    _SHUTDOWN_IN_PROGRESS = True

    logger.info(f"Received signal {signum}, initiating graceful shutdown...")

    def cleanup_with_timeout():
        try:
            _cleanup_resources()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            # Don't log "can't register atexit after shutdown" errors during import
            if "can't register atexit after shutdown" not in str(e):
                logger.error(f"Error during cleanup: {e}")

    # Run cleanup in a separate thread with timeout
    cleanup_thread = threading.Thread(target=cleanup_with_timeout, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=10)  # 10 second timeout

    if cleanup_thread.is_alive():
        logger.warning("Cleanup timeout reached, forcing exit")

    # Force exit after cleanup attempt
    logger.info("Shutdown complete, exiting")
    import os
    os._exit(0)


def _cleanup_resources():
    """Comprehensive cleanup function for all resources."""
    global _CLEANUP_COMPLETED

    # Prevent duplicate cleanup
    if _CLEANUP_COMPLETED:
        return

    # Skip cleanup if interpreter is shutting down
    if _is_interpreter_shutting_down():
        logger.info("Interpreter shutting down, skipping resource cleanup")
        _CLEANUP_COMPLETED = True
        return

    logger.info("Cleaning up resources...")

    def cleanup_worker():
        try:
            # Cleanup temp files
            try:
                try:
                    from ..utils.file_management import get_temp_manager
                except ImportError:
                    from utils.file_management import get_temp_manager
                manager = get_temp_manager()
                manager.cleanup_all(force=True)
                logger.debug("Temp file cleanup completed")
            except Exception as e:
                logger.warning(f"Temp file cleanup failed: {e}")

            # Cleanup GPU resources
            try:
                try:
                    from ..utils.gpu_manager import cleanup_gpu_memory
                except ImportError:
                    from utils.gpu_manager import cleanup_gpu_memory
                cleanup_gpu_memory(force=True)
                logger.debug("GPU cleanup completed")
            except Exception as e:
                logger.warning(f"GPU cleanup failed: {e}")

        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")

    # Run cleanup with timeout
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=15)  # 15 second overall timeout

    _CLEANUP_COMPLETED = True

    if cleanup_thread.is_alive():
        logger.warning("Cleanup timeout reached, some resources may not be fully cleaned up")
    else:
        logger.info("Cleanup completed successfully")


async def _job_expiration_loop():
    """Periodic loop to expire stale jobs in the database."""
    try:
        from ..database import get_job_store
    except ImportError:
        from database import get_job_store
    job_store = get_job_store()
    interval_seconds = 300  # 5 minutes
    while True:
        try:
            result = job_store.expire_stale_jobs()
            if result and result.get('expired_count', 0) > 0:
                logger.info(f"Expired {result['expired_count']} stale jobs")
        except Exception as e:
            logger.error(f"Error during job expiration: {e}")
        
        await asyncio.sleep(interval_seconds)


def _enqueue_job_update(job_id: str) -> None:
    """No-op: WebSocket broadcasting has been removed, using REST API polling instead."""
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context to manage background broadcaster task."""
    global MAIN_LOOP, logger
    MAIN_LOOP = asyncio.get_running_loop()

    # Initialize logging system (only once per process)
    logger = initialize_logging()

    # Initialize enhanced systems
    try:
        init_metrics_system()

        # Initialize utility systems
        try:
            from ..utils.file_management import init_temp_manager, cleanup_temp_files_on_startup
            from ..utils.streaming_processor import init_streaming_processor
            from ..utils.fonts import init_font_manager
            from ..utils.paths import init_path_manager
            from ..utils.gpu_manager import init_gpu_manager
        except ImportError:
            from utils.file_management import init_temp_manager, cleanup_temp_files_on_startup
            from utils.streaming_processor import init_streaming_processor
            from utils.fonts import init_font_manager
            from utils.paths import init_path_manager
            from utils.gpu_manager import init_gpu_manager

        init_temp_manager()
        cleanup_temp_files_on_startup()
        init_streaming_processor()
        init_font_manager()
        init_path_manager()
        init_gpu_manager()

        # Initialize and start job queue worker (delayed import to avoid circular dependency)
        try:
            try:
                from ..job_queue_unified import get_job_queue
            except ImportError:
                from job_queue_unified import get_job_queue
            job_queue = get_job_queue()
            if not job_queue.running:
                job_queue.start_worker()
                logger.info("Job queue worker started")
            else:
                logger.info("Job queue worker already running")
        except Exception as e:
            logger.error(f"Failed to initialize job queue worker: {e}")

        logger.info("✅ All systems initialized")
    except Exception as e:
        logger.error(f"Failed to initialize enhanced systems: {e}")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Start background tasks
    expiration_task = asyncio.create_task(_job_expiration_loop())
    
    try:
        yield
    finally:
        # Cancel background tasks
        expiration_task.cancel()
        
        # Wait for tasks to complete with timeout
        tasks_to_wait = [expiration_task]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks_to_wait, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Background tasks timeout during shutdown")
        except Exception:
            # Expected when cancelling
            pass
        
        # Cleanup multiprocessing resources to prevent semaphore leaks
        if not _is_interpreter_shutting_down():
            try:
                import multiprocessing
                processes = multiprocessing.active_children()
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=5)
                        if process.is_alive():
                            process.kill()
            except Exception as e:
                logger.warning(f"Failed to cleanup multiprocessing resources: {e}")
        else:
            logger.info("Skipping multiprocessing cleanup - interpreter shutting down")

        # Cleanup threading resources
        if not _is_interpreter_shutting_down():
            try:
                # Give threads a moment to finish gracefully
                time.sleep(0.5)
            except Exception:
                pass
        else:
            logger.info("Skipping threading cleanup - interpreter shutting down")

        # Cleanup any remaining connections and resources
        try:
            logger.info("Resource cleanup completed")
        except Exception as e:
            logger.warning(f"Failed to cleanup resources: {e}")


# Module-level exports for use in other parts of the application
__all__ = [
    "lifespan",
    "_enqueue_job_update",
    "MAIN_LOOP",
]
