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

from ..logging_config import initialize_logging, get_logger
from ..metrics import init_metrics_system
from ..database import get_job_store
from ..job_queue_unified import get_job_queue

# Global state for lifespan management
MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None
WS_SUBSCRIBERS: Dict[str, set] = defaultdict(set)
ASYNC_QUEUE: "asyncio.Queue[tuple[str, Dict[str, Any]]]" = asyncio.Queue()
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
            # Cleanup WebSocket connections
            try:
                from ..utils.websocket_manager import cleanup_websocket_connections
                # Use async context if available
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(cleanup_websocket_connections(timeout=5.0))
                logger.debug("WebSocket cleanup initiated")
            except Exception as e:
                logger.warning(f"WebSocket cleanup failed: {e}")

            # Cleanup temp files
            try:
                from ..utils.file_management import get_temp_manager
                manager = get_temp_manager()
                manager.cleanup_all(force=True)
                logger.debug("Temp file cleanup completed")
            except Exception as e:
                logger.warning(f"Temp file cleanup failed: {e}")

            # Cleanup GPU resources
            try:
                from ..utils.gpu_manager import cleanup_gpu_memory
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


async def _cleanup_websockets():
    """Helper function to cleanup WebSocket connections using the manager."""
    from ..utils.websocket_manager import cleanup_websocket_connections
    return await cleanup_websocket_connections(timeout=10.0)


async def _broadcast_loop():
    """Background task to broadcast job updates to WebSocket clients."""
    while True:
        try:
            job_id, payload = await asyncio.wait_for(ASYNC_QUEUE.get(), timeout=1.0)
            await _broadcast_job_update(job_id, payload)
        except asyncio.TimeoutError:
            # Normal timeout, continue loop
            continue
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
            await asyncio.sleep(1)


async def _broadcast_job_update(job_id: str, payload: Dict[str, Any]):
    """Broadcast job update to all WebSocket subscribers for this job."""
    from ..utils.websocket_manager import get_websocket_manager

    ws_manager = get_websocket_manager()
    subscribers = ws_manager.get_subscribers_for_job(job_id)

    if not subscribers:
        return

    dead_connections = []
    for websocket in subscribers:
        try:
            await websocket.send_json(payload)
            # Update activity timestamp
            ws_manager.update_activity(job_id, websocket)
        except Exception:
            # Connection is dead, mark for removal
            dead_connections.append(websocket)

    # Clean up dead connections
    for websocket in dead_connections:
        ws_manager.remove_connection(job_id, websocket)

    if dead_connections:
        logger.debug(f"Cleaned up {len(dead_connections)} dead WebSocket connections for job {job_id}")


def _enqueue_job_update(job_id: str) -> None:
    """Thread-safe enqueue of a job update for websocket broadcast."""
    global MAIN_LOOP
    try:
        # Get job data from unified queue (which includes database data)
        job_queue = get_job_queue()
        payload = job_queue.get_job_status(job_id)
        if payload and MAIN_LOOP is not None:
            MAIN_LOOP.call_soon_threadsafe(ASYNC_QUEUE.put_nowait, (job_id, payload))
    except Exception:
        # Best-effort only
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
        from ..utils.file_management import init_temp_manager, cleanup_temp_files_on_startup
        from ..utils.websocket_manager import init_websocket_manager
        from ..utils.streaming_processor import init_streaming_processor
        from ..utils.fonts import init_font_manager
        from ..utils.paths import init_path_manager
        from ..utils.gpu_manager import init_gpu_manager

        init_temp_manager()
        cleanup_temp_files_on_startup()
        init_websocket_manager()
        init_streaming_processor()
        init_font_manager()
        init_path_manager()
        init_gpu_manager()

        logger.info("✅ All systems initialized")
    except Exception as e:
        logger.error(f"Failed to initialize enhanced systems: {e}")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Start background tasks
    broadcaster_task = asyncio.create_task(_broadcast_loop())
    websocket_monitor_task = asyncio.create_task(_websocket_monitor_loop())
    
    try:
        yield
    finally:
        # Cancel background tasks
        broadcaster_task.cancel()
        websocket_monitor_task.cancel()
        
        # Wait for tasks to complete with timeout
        tasks_to_wait = [broadcaster_task, websocket_monitor_task]
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

        # Cleanup any remaining WebSocket connections
        try:
            await _cleanup_websockets()
        except Exception as e:
            logger.warning(f"Failed to cleanup WebSocket connections: {e}")


async def _websocket_monitor_loop():
    """Background task to monitor and cleanup WebSocket connections."""
    from ..utils.websocket_manager import get_websocket_manager
    
    ws_manager = get_websocket_manager()
    
    while True:
        try:
            # Run cleanup check every 30 seconds
            await asyncio.sleep(30)
            await ws_manager.cleanup_stale_connections()
            
            # Log stats every 5 minutes
            current_time = time.time()
            if int(current_time) % 300 == 0:  # Every 5 minutes
                stats = ws_manager.get_connection_stats()
                logger.info(f"WebSocket stats: {stats['total_connections']} connections, {stats['jobs_with_connections']} jobs")
                
        except asyncio.CancelledError:
            logger.info("WebSocket monitor loop cancelled")
            break
        except Exception as e:
            logger.error(f"WebSocket monitor error: {e}")
            await asyncio.sleep(30)  # Wait before retrying


# Module-level exports for use in other parts of the application
__all__ = [
    "lifespan",
    "_enqueue_job_update",
    "_broadcast_job_update",
    "MAIN_LOOP",
    "WS_SUBSCRIBERS", 
    "ASYNC_QUEUE"
]
