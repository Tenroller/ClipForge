"""
Simple in-memory job queue for video processing API
"""

import asyncio
import time
import uuid
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from ..models import JobStatus, JobPriority, WorkflowType, JobStatusResponse
from ..core.config import ProcessorConfig

import logging
logger = logging.getLogger(__name__)


@dataclass
class ProcessingJob:
    """Internal job representation."""
    job_id: str
    workflow: WorkflowType
    priority: JobPriority
    request_data: Dict[str, Any]
    callback_url: Optional[str] = None
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    progress: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    logs: List[str] = field(default_factory=list)
    cancelled: bool = False


class ProcessorJobQueue:
    """In-memory job queue for video processing."""
    
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.processor_id = config.processor_id
        self.running = False
        
        # Job storage
        self.jobs: Dict[str, ProcessingJob] = {}
        self.queue: List[str] = []  # Job IDs in priority order
        self.active_jobs: Dict[str, ProcessingJob] = {}
        
        # Job handlers
        self.job_handlers: Dict[WorkflowType, Callable] = {}
        
        # Processing control
        self._processing_tasks: List[asyncio.Task] = []
        
    async def connect(self):
        """Initialize the queue (no external connections needed)."""
        logger.info(f"Initialized in-memory job queue for processor {self.processor_id}")
    
    async def disconnect(self):
        """Clean shutdown."""
        await self.stop_processing()
        
    def register_handler(self, workflow: WorkflowType, handler: Callable):
        """Register a handler function for a workflow type."""
        self.job_handlers[workflow] = handler
        logger.info(f"Registered handler for workflow: {workflow}")
    
    async def add_job(self, 
                     job_id: str,
                     workflow: WorkflowType,
                     request_data: Dict[str, Any],
                     priority: JobPriority = JobPriority.NORMAL,
                     callback_url: Optional[str] = None) -> bool:
        """Add a job to the queue."""
        try:
            job = ProcessingJob(
                job_id=job_id,
                workflow=workflow,
                priority=priority,
                request_data=request_data,
                callback_url=callback_url
            )
            
            self.jobs[job_id] = job
            
            # Insert job in priority order (higher priority = lower index)
            insert_pos = len(self.queue)
            for i, existing_job_id in enumerate(self.queue):
                existing_job = self.jobs[existing_job_id]
                if self._get_priority_value(priority) > self._get_priority_value(existing_job.priority):
                    insert_pos = i
                    break
            
            self.queue.insert(insert_pos, job_id)
            
            logger.info(f"Added job {job_id} to queue with priority {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            return False
    
    def _get_priority_value(self, priority: JobPriority) -> int:
        """Get numeric value for priority (higher = more important)."""
        priority_values = {
            JobPriority.CRITICAL: 4,
            JobPriority.HIGH: 3,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 1
        }
        return priority_values.get(priority, 2)
    
    async def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get job status by ID."""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            workflow=job.workflow,
            priority=job.priority,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            progress=job.progress,
            current_step=job.current_step,
            error_message=job.error_message,
            result_data=job.result_data,
            logs=job.logs
        )
    
    async def list_jobs(self, 
                       status: Optional[JobStatus] = None,
                       limit: int = 50) -> List[JobStatusResponse]:
        """List jobs with optional filtering."""
        jobs = []
        
        for job in self.jobs.values():
            if status and job.status != status:
                continue
            
            jobs.append(JobStatusResponse(
                job_id=job.job_id,
                status=job.status,
                workflow=job.workflow,
                priority=job.priority,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
                progress=job.progress,
                current_step=job.current_step,
                error_message=job.error_message,
                result_data=job.result_data,
                logs=job.logs
            ))
        
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]
    
    async def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a job."""
        try:
            # Remove from queue if queued
            if job_id in self.queue:
                self.queue.remove(job_id)
            
            # Update job status
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.CANCELLED
                job.error_message = reason or "Job cancelled"
                job.cancelled = True
                
                if job.status == JobStatus.RUNNING:
                    job.completed_at = datetime.now(timezone.utc)
                    if job.started_at:
                        job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())
                
                # Remove from active jobs if running
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
            
            logger.info(f"Cancelled job {job_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    async def update_job_status(self,
                               job_id: str,
                               status: JobStatus,
                               progress: Optional[str] = None,
                               current_step: Optional[str] = None,
                               error_message: Optional[str] = None,
                               result_data: Optional[Dict[str, Any]] = None):
        """Update job status and metadata."""
        job = self.jobs.get(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found for status update")
            return
        
        try:
            # Update status
            job.status = status
            
            # Update optional fields
            if progress:
                job.progress = progress
            if current_step:
                job.current_step = current_step
            if error_message:
                job.error_message = error_message
            if result_data:
                job.result_data = result_data
            
            # Set timestamps
            now = datetime.now(timezone.utc)
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = now
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = now
                if job.started_at:
                    job.duration_seconds = int((now - job.started_at).total_seconds())
            
            logger.debug(f"Updated job {job_id} status to {status}")
            
            # Send callback to backend API
            await self.send_callback(
                job_id=job_id,
                status=status.value,
                current_step=current_step,
                error_message=error_message,
                result_data=result_data
            )
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
    
    async def add_job_log(self, job_id: str, message: str):
        """Add a log message to a job."""
        job = self.jobs.get(job_id)
        if job:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            job.logs.append(f"[{timestamp}] {message}")
    
    async def send_callback(self, job_id: str, status: str, 
                           current_step: Optional[str] = None,
                           error_message: Optional[str] = None,
                           result_data: Optional[Dict[str, Any]] = None):
        """Send HTTP callback to backend API for job status update."""
        job = self.jobs.get(job_id)
        if not job or not job.callback_url:
            return
        
        try:
            payload = {
                "job_id": job_id,
                "status": status,
                "current_step": current_step,
                "error_message": error_message,
                "result_data": result_data,
                "logs": job.logs[-10:] if job.logs else []  # Send last 10 log entries
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            logger.info(f"Sending callback for job {job_id} to {job.callback_url}")
            
            response = requests.post(
                job.callback_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.debug(f"Callback sent successfully for job {job_id}")
            else:
                logger.warning(f"Callback failed for job {job_id}: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to send callback for job {job_id}: {e}")
    
    def get_next_job(self) -> Optional[ProcessingJob]:
        """Get the next job from the queue."""
        # Check current capacity
        if len(self.active_jobs) >= self.config.max_concurrent_jobs:
            return None
        
        # Get highest priority job
        if not self.queue:
            return None
        
        job_id = self.queue.pop(0)
        job = self.jobs.get(job_id)
        
        if job and job.status == JobStatus.QUEUED:
            # Move to active jobs
            self.active_jobs[job_id] = job
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            return job
        
        return None
    
    async def start_processing(self):
        """Start the job processing loop."""
        if self.running:
            logger.warning("Job processing already running")
            return
        
        self.running = True
        logger.info(f"Starting job processing for processor {self.processor_id}")
        
        # Start processing tasks
        for i in range(self.config.max_concurrent_jobs):
            task = asyncio.create_task(self._processing_worker(f"worker-{i}"))
            self._processing_tasks.append(task)
    
    async def stop_processing(self):
        """Stop the job processing loop."""
        self.running = False
        logger.info("Stopping job processing")
        
        # Cancel processing tasks
        for task in self._processing_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        self._processing_tasks.clear()
        
        # Clear active jobs
        self.active_jobs.clear()
    
    async def _processing_worker(self, worker_name: str):
        """Processing worker loop."""
        logger.info(f"Started processing worker: {worker_name}")
        
        while self.running:
            try:
                # Get next job
                job = self.get_next_job()
                if not job:
                    await asyncio.sleep(1)  # Wait before checking again
                    continue
                
                # Process job
                await self._process_job(job)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing worker {worker_name}: {e}")
                await asyncio.sleep(5)  # Wait before retrying
        
        logger.info(f"Stopped processing worker: {worker_name}")
    
    async def _process_job(self, job: ProcessingJob):
        """Process a single job."""
        job_id = job.job_id
        workflow = job.workflow
        
        try:
            logger.info(f"Processing job {job_id} (workflow: {workflow})")
            await self.add_job_log(job_id, f"Started processing workflow: {workflow}")
            
            # Check if handler is registered
            if workflow not in self.job_handlers:
                raise ValueError(f"No handler registered for workflow: {workflow}")
            
            # Execute the handler
            handler = self.job_handlers[workflow]
            
            # Convert job data to handler format
            job_data = {
                "job_id": job.job_id,
                "workflow": job.workflow.value,
                "request_data": job.request_data,
                "callback_url": job.callback_url
            }
            
            result = await handler(job_data)
            
            # Check if job was cancelled during processing
            if job.cancelled:
                await self.update_job_status(job_id, JobStatus.CANCELLED)
                await self.add_job_log(job_id, "Job was cancelled during processing")
            else:
                await self.update_job_status(
                    job_id,
                    JobStatus.COMPLETED,
                    result_data=result
                )
                await self.add_job_log(job_id, "Job completed successfully")
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await self.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=str(e)
            )
            await self.add_job_log(job_id, f"Job failed: {str(e)}")
        finally:
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs."""
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
            removed = 0
            
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                # Only clean up completed/failed/cancelled jobs
                if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    continue
                
                # Check age
                if job.completed_at:
                    completed_time = job.completed_at.timestamp()
                    if completed_time < cutoff_time:
                        jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                removed += 1
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} old jobs")
            
            return removed
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        status_counts = {}
        for job in self.jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "processor_id": self.processor_id,
            "total_jobs": len(self.jobs),
            "queued_jobs": len(self.queue),
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.config.max_concurrent_jobs,
            "status_counts": status_counts,
            "registered_workflows": [w.value for w in self.job_handlers.keys()],
            "running": self.running
        }