"""
WebSocket connection manager for proper cleanup and monitoring.
"""

import asyncio
import time
import threading
from typing import Dict, Set, Optional, Callable
from collections import defaultdict
from logging_config import get_logger

logger = get_logger("websocket_manager")


class WebSocketConnectionManager:
    """Manages WebSocket connections with proper cleanup and monitoring."""

    def __init__(self):
        self.subscribers: Dict[str, Set] = defaultdict(set)
        self.connection_times: Dict[str, Dict] = defaultdict(dict)
        self.heartbeat_intervals: Dict[str, float] = {}
        self.max_connection_age = 3600  # 1 hour max connection age
        self.heartbeat_interval = 30  # 30 second heartbeat
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def add_connection(self, job_id: str, websocket, client_info: Optional[Dict] = None):
        """Add a WebSocket connection for a job."""
        with self._lock:
            self.subscribers[job_id].add(websocket)
            self.connection_times[job_id][id(websocket)] = {
                'connected_at': time.time(),
                'last_activity': time.time(),
                'client_info': client_info or {},
                'job_id': job_id
            }

        logger.debug(f"WebSocket connection added for job {job_id} (total: {len(self.subscribers[job_id])})")

    def remove_connection(self, job_id: str, websocket):
        """Remove a WebSocket connection."""
        with self._lock:
            if websocket in self.subscribers[job_id]:
                self.subscribers[job_id].discard(websocket)
                if id(websocket) in self.connection_times[job_id]:
                    del self.connection_times[job_id][id(websocket)]

                # Clean up empty sets
                if not self.subscribers[job_id]:
                    del self.subscribers[job_id]
                    if job_id in self.connection_times:
                        del self.connection_times[job_id]

        logger.debug(f"WebSocket connection removed for job {job_id}")

    def update_activity(self, job_id: str, websocket):
        """Update last activity timestamp for a connection."""
        with self._lock:
            if id(websocket) in self.connection_times.get(job_id, {}):
                self.connection_times[job_id][id(websocket)]['last_activity'] = time.time()

    def get_connection_count(self, job_id: Optional[str] = None) -> int:
        """Get total number of active connections."""
        with self._lock:
            if job_id:
                return len(self.subscribers.get(job_id, set()))
            return sum(len(connections) for connections in self.subscribers.values())

    def get_connection_stats(self) -> Dict:
        """Get statistics about WebSocket connections."""
        with self._lock:
            stats = {
                'total_connections': self.get_connection_count(),
                'jobs_with_connections': len(self.subscribers),
                'connections_by_job': {}
            }

            current_time = time.time()
            for job_id, connections in self.subscribers.items():
                conn_times = self.connection_times.get(job_id, {})
                oldest_conn = min(
                    (info['connected_at'] for info in conn_times.values()),
                    default=current_time
                )

                stats['connections_by_job'][job_id] = {
                    'count': len(connections),
                    'oldest_connection_age_seconds': current_time - oldest_conn
                }

            return stats

    async def cleanup_stale_connections(self, max_age_seconds: Optional[int] = None):
        """Clean up stale WebSocket connections."""
        if max_age_seconds is None:
            max_age_seconds = self.max_connection_age

        logger.info(f"Cleaning up WebSocket connections older than {max_age_seconds} seconds")

        current_time = time.time()
        cleanup_count = 0

        with self._lock:
            # Create a copy of subscribers to avoid modification during iteration
            subscribers_copy = dict(self.subscribers)
            connection_times_copy = dict(self.connection_times)

        for job_id, connections in subscribers_copy.items():
            conn_times = connection_times_copy.get(job_id, {})
            stale_connections = []

            for websocket in connections:
                conn_id = id(websocket)
                if conn_id in conn_times:
                    conn_info = conn_times[conn_id]
                    age = current_time - conn_info['connected_at']
                    last_activity = current_time - conn_info['last_activity']

                    # Check if connection is stale (old or inactive)
                    if age > max_age_seconds or last_activity > (self.heartbeat_interval * 3):
                        stale_connections.append(websocket)
                        logger.debug(f"Marked stale connection for job {job_id}: age={age:.1f}s, inactive={last_activity:.1f}s")

            # Clean up stale connections
            for websocket in stale_connections:
                try:
                    # Try to close the connection gracefully
                    if hasattr(websocket, 'close'):
                        await asyncio.wait_for(websocket.close(), timeout=5.0)
                    logger.debug(f"Closed stale WebSocket connection for job {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to close stale WebSocket connection: {e}")

                # Remove from our tracking
                self.remove_connection(job_id, websocket)
                cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stale WebSocket connections")

        return cleanup_count

    async def cleanup_all_connections(self, timeout: float = 10.0):
        """Clean up all WebSocket connections with timeout."""
        logger.info(f"Cleaning up all {self.get_connection_count()} WebSocket connections")

        cleanup_count = 0
        start_time = time.time()

        with self._lock:
            # Create a copy to avoid modification during iteration
            subscribers_copy = dict(self.subscribers)

        for job_id, connections in subscribers_copy.items():
            for websocket in list(connections):
                try:
                    # Check timeout
                    if time.time() - start_time > timeout:
                        logger.warning(f"WebSocket cleanup timeout reached after {cleanup_count} connections")
                        return cleanup_count

                    # Try to close gracefully
                    if hasattr(websocket, 'close'):
                        await asyncio.wait_for(websocket.close(), timeout=2.0)
                        logger.debug(f"Closed WebSocket connection for job {job_id}")

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout closing WebSocket connection for job {job_id}")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket connection for job {job_id}: {e}")

                # Remove from our tracking
                self.remove_connection(job_id, websocket)
                cleanup_count += 1

        # Clear all subscribers
        with self._lock:
            self.subscribers.clear()
            self.connection_times.clear()

        logger.info(f"Successfully cleaned up {cleanup_count} WebSocket connections")
        return cleanup_count

    def start_monitoring(self):
        """Start background monitoring thread."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_worker, daemon=True)
        self.monitor_thread.start()
        logger.info("WebSocket monitoring thread started")

    def stop_monitoring(self):
        """Stop background monitoring thread."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def _monitoring_worker(self):
        """Background monitoring worker."""
        while self.monitoring_active:
            try:
                # Create event loop for async cleanup
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Run cleanup check
                cleanup_task = loop.create_task(self.cleanup_stale_connections())
                loop.run_until_complete(cleanup_task)

                loop.close()

                # Log stats periodically
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    stats = self.get_connection_stats()
                    logger.info(f"WebSocket stats: {stats['total_connections']} connections, {stats['jobs_with_connections']} jobs")

            except Exception as e:
                logger.error(f"WebSocket monitoring error: {e}")

            # Sleep for heartbeat interval
            time.sleep(self.heartbeat_interval)

    def get_subscribers_for_job(self, job_id: str) -> Set:
        """Get all subscribers for a specific job."""
        with self._lock:
            return set(self.subscribers.get(job_id, set()))


# Global instance
_ws_manager: Optional[WebSocketConnectionManager] = None


def get_websocket_manager() -> WebSocketConnectionManager:
    """Get or create the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketConnectionManager()
    return _ws_manager


def init_websocket_manager():
    """Initialize the WebSocket manager with monitoring."""
    manager = get_websocket_manager()
    manager.start_monitoring()
    logger.info("WebSocket manager initialized")


async def cleanup_websocket_connections(timeout: float = 10.0):
    """Clean up all WebSocket connections (async version for FastAPI)."""
    manager = get_websocket_manager()
    return await manager.cleanup_all_connections(timeout)


def cleanup_websocket_connections_sync(timeout: float = 10.0):
    """Clean up all WebSocket connections (sync version for cleanup)."""
    try:
        manager = get_websocket_manager()
        # Create event loop for sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        cleanup_task = loop.create_task(manager.cleanup_all_connections(timeout))
        result = loop.run_until_complete(cleanup_task)
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Failed to cleanup WebSocket connections: {e}")
        return 0
