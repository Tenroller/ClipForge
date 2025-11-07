"""
Unified Job Queue for VideoHelper.

This combines the best features from both job_queue.py and job_queue_simple.py
while maintaining compatibility with the current app.py job management system.

Features:
- In-memory queue with priority scheduling
- Sequential job processing (one job at a time by default)
- ThreadPoolExecutor for job execution
- Job cancellation support
- Integration with database persistence
- WebSocket real-time updates
- Comprehensive error handling and logging
- No external dependencies (Redis-free)

Note: By default, max_workers is set to 1 to ensure sequential processing
for resource-constrained environments. This can be increased via the
VIDEOHELPER_MAX_CONCURRENT_JOBS environment variable if needed.
"""

import json
import os
import time
import uuid
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from .logging_config import get_logger

logger = get_logger("job_queue_unified")


class JobStatus(Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Job:
    """Unified job representation."""
    id: str
    func: Callable
    args: tuple
    kwargs: Dict[str, Any]
    priority: JobPriority
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    workflow: str = "default"
    user_id: Optional[str] = None
    logs: Optional[List[str]] = None
    step: str = "init"

    def __post_init__(self):
        if self.logs is None:
            self.logs = []


class UnifiedJobQueue:
    """
    Unified job queue combining the best features of both implementations.

    Features:
    - In-memory job storage with database persistence
    - Priority-based execution
    - Sequential job processing (one job at a time by default)
    - Background thread execution
    - Job cancellation support
    - WebSocket real-time updates
    - Comprehensive monitoring
    - No external dependencies

    The queue processes jobs sequentially by default (max_workers=1) to ensure
    compatibility with resource-constrained environments. Jobs are picked from
    the queue based on priority and processed one at a time.
    """

    def __init__(self, max_workers: int = 1, job_store=None):
        self.jobs: Dict[str, Job] = {}
        self.queue: List[str] = []  # Job IDs in priority order
        self.cancel_tokens: Dict[str, threading.Event] = {}
        self.futures: Dict[str, Future] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-worker")
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.job_store = job_store  # Database integration

        # Handle orphaned jobs on startup
        self._handle_orphaned_jobs()

        # Start the worker thread
        self.start_worker()

    def _handle_orphaned_jobs(self):
        """
        Handle jobs that were marked as running but are orphaned due to server restart.
        
        This method finds jobs in the database that have status 'running' but are not
        in the current job queue (because the server restarted). It marks them as
        cancelled with an appropriate message.
        """
        if not self.job_store:
            return
            
        try:
            # Get running and queued jobs
            running_jobs = self.job_store.list_jobs(limit=1000, status="running")
            queued_jobs = self.job_store.list_jobs(limit=1000, status="queued")
            orphaned_count = 0
            hung_count = 0
            
            from datetime import datetime, timezone
            current_time = datetime.now(timezone.utc)
            
            for job_data in running_jobs:
                job_id = job_data.get('id')
                if not job_id:
                    continue
                    
                # Check if job is orphaned (not in current queue)
                if job_id not in self.jobs:
                    orphaned_count += 1
                    
                    # Check if job has been running for too long (potential hung job)
                    started_at = job_data.get('started_at')
                    if started_at:
                        try:
                            # Parse ISO format datetime string
                            if started_at.endswith('Z'):
                                started_at = started_at[:-1] + '+00:00'
                            start_time = datetime.fromisoformat(started_at)
                            if start_time.tzinfo is None:
                                start_time = start_time.replace(tzinfo=timezone.utc)
                            
                            running_duration = (current_time - start_time).total_seconds()
                            max_duration = int(os.getenv("VIDEOHELPER_MAX_JOB_DURATION_HOURS", "4")) * 3600  # Default 4 hours
                            
                            if running_duration > max_duration:
                                hung_count += 1
                                error_msg = f"Job exceeded maximum duration ({running_duration/3600:.1f}h > 4h) - automatically cancelled"
                                logger.warning(f"Job {job_id} was hung (running for {running_duration/3600:.1f}h)")
                            else:
                                error_msg = f"Server restarted while job was running (was running for {running_duration/60:.1f}m) - automatically cancelled"
                        except Exception as e:
                            logger.warning(f"Failed to parse start time for job {job_id}: {e}")
                            error_msg = "Server restarted while job was running - automatically cancelled"
                    else:
                        error_msg = "Server restarted while job was running - automatically cancelled"
                    
                    # Mark as cancelled with explanation
                    self.job_store.update_job(
                        job_id,
                        status="cancelled", 
                        error=error_msg,
                        ended_at=current_time.isoformat(),
                        duration_seconds=0
                    )
                    
                    logger.warning(f"Marked orphaned job {job_id} as cancelled")
            
            # Cancel stale queued jobs that never started (older than 2 hours)
            stale_threshold_seconds = int(os.getenv("VIDEOHELPER_STALE_QUEUED_SECONDS", str(2 * 3600)))
            stale_count = 0
            for job_data in queued_jobs:
                created_at = job_data.get('created_at')
                job_id = job_data.get('id')
                if not created_at or not job_id:
                    continue
                try:
                    ts = created_at
                    if ts.endswith('Z'):
                        ts = ts[:-1] + '+00:00'
                    ctime = datetime.fromisoformat(ts)
                    if ctime.tzinfo is None:
                        ctime = ctime.replace(tzinfo=timezone.utc)
                    age = (current_time - ctime).total_seconds()
                    if age > stale_threshold_seconds:
                        self.job_store.update_job(
                            job_id,
                            status="cancelled",
                            error="Server restart: queued job stale (auto-cancel)",
                            ended_at=current_time.isoformat(),
                            duration_seconds=0
                        )
                        stale_count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse created_at for queued job {job_id}: {e}")

            if orphaned_count > 0 or stale_count > 0:
                logger.warning(f"Found and cancelled {orphaned_count} orphaned jobs on startup ({hung_count} were hung for >4h)")
                if stale_count > 0:
                    logger.warning(f"Also cancelled {stale_count} stale queued jobs (> {stale_threshold_seconds/3600:.1f}h old)")
                if hung_count > 0:
                    logger.warning(f"Consider investigating why {hung_count} jobs were running for over 4 hours")
            else:
                logger.info("No orphaned jobs found on startup - all jobs are properly tracked")
                
        except Exception as e:
            logger.error(f"Failed to handle orphaned jobs: {e}")

    def start_worker(self):
        """Start the background worker thread."""
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="unified-job-queue-worker"
        )
        self.worker_thread.start()
        logger.info("Unified job queue worker started")

    def stop_worker(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        # Cancel all running futures
        with self.lock:
            for future in self.futures.values():
                future.cancel()

        self.executor.shutdown(wait=True)
        logger.info("Unified job queue worker stopped")

    def add_job(self, func: Callable, *args, priority: JobPriority = JobPriority.NORMAL,
                job_id: Optional[str] = None, workflow: str = "default",
                user_id: Optional[str] = None, **kwargs) -> str:
        """
        Add a job to the queue.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            priority: Job priority
            job_id: Optional custom job ID
            workflow: Workflow type (for database categorization)
            user_id: User ID for multi-user support
            **kwargs: Keyword arguments for the function

        Returns:
            Job ID
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            status=JobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            workflow=workflow,
            user_id=user_id
        )

        with self.lock:
            self.jobs[job_id] = job
            self.cancel_tokens[job_id] = threading.Event()

            # Insert job in priority order (higher priority = lower index)
            insert_pos = 0
            for i, existing_job_id in enumerate(self.queue):
                existing_job = self.jobs[existing_job_id]
                if priority.value > existing_job.priority.value:
                    break
                insert_pos = i + 1

            self.queue.insert(insert_pos, job_id)

            # Persist to database if available
            if self.job_store:
                try:
                    # Convert args and kwargs to JSON-serializable format
                    serializable_args = self._make_serializable(args)
                    serializable_kwargs = self._make_serializable(kwargs)

                    # Persist original function name so we can resume accurately later
                    self.job_store.create_job(
                        job_id,
                        workflow,
                        {"func": getattr(func, '__name__', 'unknown'),
                         "args": serializable_args,
                         "kwargs": serializable_kwargs,
                         "priority": priority.name},
                        user_id
                    )
                except Exception as e:
                    logger.error(f"Failed to persist job {job_id} to database: {e}")

        logger.info(f"Job {job_id} added to queue with priority {priority.name}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job if it's still queued or running.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was cancelled, False otherwise
        """
        with self.lock:
            if job_id in self.cancel_tokens:
                self.cancel_tokens[job_id].set()

                # Cancel the future if it's running
                if job_id in self.futures:
                    self.futures[job_id].cancel()

                if job_id in self.jobs:
                    job = self.jobs[job_id]
                    if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
                        job.status = JobStatus.CANCELLED
                        job.completed_at = datetime.now(timezone.utc)
                        if job.started_at:
                            job.duration = (job.completed_at - job.started_at).total_seconds()

                        # Update database
                        if self.job_store:
                            try:
                                self.job_store.update_job(
                                    job_id,
                                    status="cancelled",
                                    error="cancelled",
                                    duration_seconds=int(job.duration or 0),
                                    ended_at=job.completed_at.isoformat() if job.completed_at else None
                                )
                            except Exception as e:
                                logger.error(f"Failed to update cancelled job {job_id} in database: {e}")

                        logger.info(f"Job {job_id} cancelled")
                        return True

        return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status and information.

        Args:
            job_id: Job ID

        Returns:
            Job information dictionary or None if job not found
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                # Try to get from database as fallback
                if self.job_store:
                    try:
                        db_job = self.job_store.get_job(job_id)
                        if db_job:
                            return {
                                'id': job_id,
                                'status': db_job.get('status', 'unknown'),
                                'step': db_job.get('step', 'unknown'),
                                'created_at': db_job.get('created_at'),
                                'started_at': db_job.get('started_at'),
                                'completed_at': db_job.get('ended_at'),
                                'duration': db_job.get('duration_seconds'),
                                'result': db_job.get('result'),  # Changed from result_data to result
                                'error': db_job.get('error_message'),
                                'logs': db_job.get('logs', [])
                            }
                    except Exception as e:
                        logger.error(f"Failed to get job {job_id} from database: {e}")
                return None

            return {
                'id': job.id,
                'status': job.status.value,
                'priority': job.priority.value,
                'workflow': job.workflow,
                'user_id': job.user_id,
                'step': job.step,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration': job.duration,
                'result': job.result,
                'error': job.error,
                'logs': job.logs
            }

    def list_jobs(self, limit: int = 100, status: Optional[JobStatus] = None,
                  workflow: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List jobs with optional filtering.

        Args:
            limit: Maximum number of jobs to return
            status: Filter by job status
            workflow: Filter by workflow type

        Returns:
            List of job information dictionaries
        """
        with self.lock:
            jobs = []
            for job_id, job in self.jobs.items():
                if status and job.status != status:
                    continue
                if workflow and job.workflow != workflow:
                    continue

                jobs.append({
                    'id': job.id,
                    'status': job.status.value,
                    'priority': job.priority.value,
                    'workflow': job.workflow,
                    'step': job.step,
                    'created_at': job.created_at.isoformat(),
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'duration': job.duration,
                    'error': job.error
                })

            # Sort by creation time (newest first)
            jobs.sort(key=lambda x: x['created_at'], reverse=True)
            return jobs[:limit]

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        with self.lock:
            stats = {
                'total_jobs': len(self.jobs),
                'queued_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.QUEUED]),
                'running_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING]),
                'completed_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.COMPLETED]),
                'failed_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.FAILED]),
                'cancelled_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.CANCELLED]),
                'queue_length': len(self.queue),
                'max_workers': self.executor._max_workers,
                'active_workers': len([f for f in self.futures.values() if not f.done()])
            }

            return stats

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            max_age_hours: Maximum age of jobs to keep

        Returns:
            Number of jobs removed
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed_count = 0

        with self.lock:
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    if job.completed_at and job.completed_at < cutoff_time:
                        jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                if job_id in self.cancel_tokens:
                    del self.cancel_tokens[job_id]
                if job_id in self.futures:
                    del self.futures[job_id]
                # Remove from queue if present
                if job_id in self.queue:
                    self.queue.remove(job_id)
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old jobs")

        return removed_count

    def update_job_progress(self, job_id: str, step: str, message: str = ""):
        """
        Update job progress and step information.

        Args:
            job_id: Job ID
            step: Current step in the job
            message: Optional progress message
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.step = step
                if message and job.logs is not None:
                    job.logs.append(message)

                # Update database
                if self.job_store:
                    try:
                        self.job_store.update_job(
                            job_id,
                            step=step,
                            logs=job.logs
                        )
                    except Exception as e:
                        logger.error(f"Failed to update job progress for {job_id}: {e}")

    def _worker_loop(self):
        """Main worker loop that processes jobs from the queue."""
        while self.running:
            try:
                job_id = None

                with self.lock:
                    if self.queue:
                        job_id = self.queue.pop(0)
                        job = self.jobs[job_id]
                        job.status = JobStatus.RUNNING
                        job.started_at = datetime.now(timezone.utc)

                        # Update database
                        if self.job_store:
                            try:
                                self.job_store.update_job(
                                    job_id,
                                    status="running",
                                    started_at=job.started_at.isoformat()
                                )
                            except Exception as e:
                                logger.error(f"Failed to update job start in database: {e}")

                if job_id:
                    self._execute_job(job_id)

                # Small delay to prevent busy waiting
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in job worker loop: {e}")
                time.sleep(1)

    def _execute_job(self, job_id: str):
        """Execute a job in the thread pool."""
        job = self.jobs[job_id]
        cancel_token = self.cancel_tokens[job_id]

        try:
            # Submit job to thread pool
            future = self.executor.submit(self._run_job_function, job, cancel_token)
            with self.lock:
                self.futures[job_id] = future

            # Wait for completion with timeout (for long-running jobs)
            result = future.result(timeout=3600)  # 1 hour timeout

            # Update job status
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration = (job.completed_at - job.started_at).total_seconds()

            logger.info(f"Job {job_id} completed successfully in {job.duration:.2f}s")

            # Update database
            if self.job_store:
                try:
                    self.job_store.update_job(
                        job_id,
                        status="completed",
                        result=result,  # Changed from result_data to result
                        duration_seconds=int(job.duration or 0),
                        ended_at=job.completed_at.isoformat() if job.completed_at else None
                    )
                except Exception as e:
                    logger.error(f"Failed to update completed job {job_id} in database: {e}")

        except asyncio.TimeoutError:
            job.status = JobStatus.FAILED
            job.error = "Job timed out"
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration = (job.completed_at - job.started_at).total_seconds()
            logger.error(f"Job {job_id} timed out")

            # Update database
            if self.job_store:
                try:
                    self.job_store.update_job(
                        job_id,
                        status="failed",
                        error_message="Job timed out",
                        duration_seconds=int(job.duration or 0),
                        ended_at=job.completed_at.isoformat() if job.completed_at else None
                    )
                except Exception as e:
                    logger.error(f"Failed to update timed out job {job_id} in database: {e}")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration = (job.completed_at - job.started_at).total_seconds()
            logger.error(f"Job {job_id} failed: {e}")

            # Update database
            if self.job_store:
                try:
                    self.job_store.update_job(
                        job_id,
                        status="failed",
                        error_message=str(e),
                        duration_seconds=int(job.duration or 0),
                        ended_at=job.completed_at.isoformat() if job.completed_at else None
                    )
                except Exception as e2:
                    logger.error(f"Failed to update failed job {job_id} in database: {e2}")

        finally:
            # Clean up
            with self.lock:
                if job_id in self.futures:
                    del self.futures[job_id]

    def _make_serializable(self, data):
        """Convert non-JSON serializable objects to serializable format."""
        if isinstance(data, (list, tuple)):
            return [self._make_serializable(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._make_serializable(value) for key, value in data.items()}
        elif hasattr(data, 'dict'):  # Pydantic models
            return data.dict()
        elif hasattr(data, '__dict__'):  # Other objects with __dict__
            # Convert object attributes to dict, skip private attributes
            return {k: self._make_serializable(v) for k, v in data.__dict__.items() if not k.startswith('_')}
        else:
            # For primitive types, return as-is
            return data

    def _run_job_function(self, job: Job, cancel_token: threading.Event):
        """Run the actual job function with cancellation support."""
        # Check for cancellation before starting
        if cancel_token.is_set():
            raise Exception("Job was cancelled")

        try:
            # Run the job function
            result = job.func(*job.args, **job.kwargs)

            # Check for cancellation after completion
            if cancel_token.is_set():
                raise Exception("Job was cancelled")

            return result

        except Exception as e:
            # Re-raise with cancellation check
            if cancel_token.is_set():
                raise Exception("Job was cancelled")
            raise


# Global instance
_job_queue: Optional[UnifiedJobQueue] = None


def get_job_queue() -> UnifiedJobQueue:
    """Get or create the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        from .database import get_job_store

        max_workers = int(os.getenv("VIDEOHELPER_MAX_CONCURRENT_JOBS", "1"))
        job_store = get_job_store()
        _job_queue = UnifiedJobQueue(max_workers=max_workers, job_store=job_store)
    return _job_queue


def cleanup_job_queue():
    """Clean up the global job queue."""
    global _job_queue
    if _job_queue:
        _job_queue.stop_worker()
        _job_queue = None


# Convenience functions for app.py compatibility
def update_job_progress(job_id: str, step: str, message: str = ""):
    """Update job progress (for compatibility with existing code)."""
    queue = get_job_queue()
    queue.update_job_progress(job_id, step, message)
