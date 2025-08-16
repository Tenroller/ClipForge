"""
Redis-based job queue for horizontal scaling and background processing.
"""

import json
import os
import time
import uuid
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import redis
    import rq
    from rq import Queue, Worker
    from rq.job import Job as RQJob
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    rq = None
    Queue = None
    Worker = None
    RQJob = None
    REDIS_AVAILABLE = False

from logging_config import get_logger

logger = get_logger("job_queue")


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class JobResult:
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[str] = None
    duration: float = 0.0
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []


class RedisJobQueue:
    """Redis-based job queue with support for priorities, retries, and monitoring."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.queues = {}
        self.workers = {}
        self.enabled = REDIS_AVAILABLE and self._test_connection()
        
        if self.enabled:
            self._setup_queues()
            logger.info(f"✅ Redis job queue initialized: {self.redis_url}")
        else:
            logger.warning("⚠️ Redis not available, falling back to in-memory queue")
    
    def _test_connection(self) -> bool:
        """Test Redis connection."""
        try:
            client = redis.from_url(self.redis_url)
            client.ping()
            self.redis_client = client
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False
    
    def _setup_queues(self):
        """Setup Redis queues with different priorities."""
        if not self.enabled:
            return
        
        priority_names = {
            JobPriority.CRITICAL: "critical",
            JobPriority.HIGH: "high", 
            JobPriority.NORMAL: "default",
            JobPriority.LOW: "low"
        }
        
        for priority, name in priority_names.items():
            self.queues[priority] = Queue(
                name=name,
                connection=self.redis_client,
                default_timeout=3600  # 1 hour timeout
            )
    
    def enqueue_job(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        job_id: Optional[str] = None,
        priority: JobPriority = JobPriority.NORMAL,
        retry_count: int = 3,
        delay: Optional[timedelta] = None
    ) -> str:
        """Enqueue a job for background processing."""
        if not self.enabled:
            # Fallback to direct execution
            job_id = job_id or str(uuid.uuid4())
            threading.Thread(
                target=self._execute_fallback,
                args=(func, args, kwargs or {}, job_id),
                daemon=True
            ).start()
            return job_id
        
        kwargs = kwargs or {}
        job_id = job_id or str(uuid.uuid4())
        
        try:
            queue = self.queues[priority]
            
            job_kwargs = {
                'job_id': job_id,
                'retry_count': retry_count,
                'job_timeout': 3600,
                'result_ttl': 86400  # Keep results for 24 hours
            }
            
            if delay:
                job_kwargs['delay'] = delay
            
            job = queue.enqueue(func, *args, **kwargs, **job_kwargs)
            
            logger.info(f"Job {job_id} enqueued with priority {priority.name}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            # Fallback to direct execution
            threading.Thread(
                target=self._execute_fallback,
                args=(func, args, kwargs, job_id),
                daemon=True
            ).start()
            return job_id
    
    def _execute_fallback(self, func: Callable, args: tuple, kwargs: Dict[str, Any], job_id: str):
        """Fallback execution when Redis is not available."""
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"Job {job_id} completed in fallback mode ({duration:.2f}s)")
        except Exception as e:
            logger.error(f"Job {job_id} failed in fallback mode: {e}")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status and metadata."""
        if not self.enabled:
            return {
                "id": job_id,
                "status": "unknown",
                "message": "Redis not available"
            }
        
        try:
            job = RQJob.fetch(job_id, connection=self.redis_client)
            
            status_map = {
                'queued': JobStatus.QUEUED.value,
                'started': JobStatus.RUNNING.value,
                'finished': JobStatus.COMPLETED.value,
                'failed': JobStatus.FAILED.value,
                'cancelled': JobStatus.CANCELLED.value
            }
            
            return {
                "id": job_id,
                "status": status_map.get(job.status, job.status),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                "result": job.result,
                "exc_info": job.exc_info,
                "progress": getattr(job, 'meta', {}).get('progress', 0),
                "queue": job.origin,
                "retry_count": job.retries_left if hasattr(job, 'retries_left') else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return {
                "id": job_id,
                "status": "unknown",
                "error": str(e)
            }
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        if not self.enabled:
            return False
        
        try:
            job = RQJob.fetch(job_id, connection=self.redis_client)
            job.cancel()
            logger.info(f"Job {job_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues."""
        if not self.enabled:
            return {"redis_available": False}
        
        stats = {"redis_available": True, "queues": {}}
        
        for priority, queue in self.queues.items():
            try:
                stats["queues"][priority.name] = {
                    "length": len(queue),
                    "started_jobs": queue.started_job_registry.count,
                    "finished_jobs": queue.finished_job_registry.count,
                    "failed_jobs": queue.failed_job_registry.count,
                    "deferred_jobs": queue.deferred_job_registry.count
                }
            except Exception as e:
                logger.error(f"Failed to get stats for queue {priority.name}: {e}")
                stats["queues"][priority.name] = {"error": str(e)}
        
        return stats
    
    def cleanup_old_jobs(self, older_than_hours: int = 24) -> int:
        """Clean up old completed/failed jobs."""
        if not self.enabled:
            return 0
        
        cleaned = 0
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        
        for queue in self.queues.values():
            try:
                # Clean finished jobs
                for job_id in queue.finished_job_registry.get_job_ids():
                    try:
                        job = RQJob.fetch(job_id, connection=self.redis_client)
                        if job.ended_at and job.ended_at < cutoff:
                            job.delete()
                            cleaned += 1
                    except:
                        pass
                
                # Clean failed jobs
                for job_id in queue.failed_job_registry.get_job_ids():
                    try:
                        job = RQJob.fetch(job_id, connection=self.redis_client)
                        if job.ended_at and job.ended_at < cutoff:
                            job.delete()
                            cleaned += 1
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Failed to cleanup queue {queue.name}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old jobs")
        
        return cleaned
    
    def start_worker(self, queues: List[str] = None, worker_name: str = None) -> Optional[Worker]:
        """Start a worker process."""
        if not self.enabled:
            logger.warning("Cannot start worker: Redis not available")
            return None
        
        if queues is None:
            queues = ['critical', 'high', 'default', 'low']
        
        worker_name = worker_name or f"worker-{uuid.uuid4().hex[:8]}"
        
        try:
            worker = Worker(
                queues,
                connection=self.redis_client,
                name=worker_name
            )
            
            # Start worker in a separate thread
            def run_worker():
                worker.work()
            
            worker_thread = threading.Thread(target=run_worker, daemon=True)
            worker_thread.start()
            
            self.workers[worker_name] = {
                'worker': worker,
                'thread': worker_thread,
                'started_at': datetime.now()
            }
            
            logger.info(f"Worker {worker_name} started for queues: {queues}")
            return worker
            
        except Exception as e:
            logger.error(f"Failed to start worker {worker_name}: {e}")
            return None


# Global job queue instance
_job_queue: Optional[RedisJobQueue] = None


def get_job_queue() -> RedisJobQueue:
    """Get or create the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        _job_queue = RedisJobQueue()
    return _job_queue


def update_job_progress(job_id: str, progress: int, message: str = ""):
    """Update job progress (for use within job functions)."""
    if not REDIS_AVAILABLE:
        return
    
    try:
        from rq import get_current_job
        job = get_current_job()
        if job and job.id == job_id:
            job.meta['progress'] = progress
            job.meta['message'] = message
            job.save_meta()
    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")


# Job decorators for common patterns
def background_job(priority: JobPriority = JobPriority.NORMAL, retry_count: int = 3):
    """Decorator to mark a function as a background job."""
    def decorator(func):
        func._background_job = True
        func._priority = priority
        func._retry_count = retry_count
        return func
    return decorator


def batch_job(batch_size: int = 10, priority: JobPriority = JobPriority.LOW):
    """Decorator for batch processing jobs."""
    def decorator(func):
        def wrapper(items: List[Any], *args, **kwargs):
            job_queue = get_job_queue()
            job_ids = []
            
            # Split items into batches
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                job_id = job_queue.enqueue_job(
                    func,
                    args=(batch,) + args,
                    kwargs=kwargs,
                    priority=priority
                )
                job_ids.append(job_id)
            
            return job_ids
        
        wrapper._batch_job = True
        wrapper._batch_size = batch_size
        return wrapper
    return decorator
