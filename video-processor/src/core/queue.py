"""
Job queue implementation for video processing API using Redis
"""

import json
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from contextlib import asynccontextmanager

import redis
from ..models import JobStatus, JobPriority, WorkflowType, JobStatusResponse
from ..core.config import ProcessorConfig

import logging
logger = logging.getLogger(__name__)


class ProcessorJobQueue:
    """Redis-based job queue for video processing."""
    
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.running = False
        self.processor_id = config.processor_id
        
        # Redis keys
        self.jobs_key = f"processor:{self.processor_id}:jobs"
        self.queue_key = f"processor:{self.processor_id}:queue"
        self.active_key = f"processor:{self.processor_id}:active"
        self.results_key = f"processor:{self.processor_id}:results"
        
        # Job tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_handlers: Dict[WorkflowType, Callable] = {}
        
    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                db=self.config.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {self.config.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            self.redis_client.close()
            self.redis_client = None
    
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
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")
        
        job_data = {
            "job_id": job_id,
            "workflow": workflow.value,
            "priority": priority.value,
            "request_data": request_data,
            "callback_url": callback_url,
            "status": JobStatus.QUEUED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processor_id": self.processor_id
        }
        
        try:
            # Store job data
            self.redis_client.hset(
                self.jobs_key,
                job_id,
                json.dumps(job_data)
            )
            
            # Add to priority queue (higher priority = lower score)
            priority_scores = {
                JobPriority.CRITICAL: 0,
                JobPriority.HIGH: 100,
                JobPriority.NORMAL: 200,
                JobPriority.LOW: 300
            }
            score = priority_scores.get(priority, 200)
            
            self.redis_client.zadd(
                self.queue_key,
                {job_id: score}
            )
            
            logger.info(f"Added job {job_id} to queue with priority {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get job status by ID."""
        if not self.redis_client:
            return None
        
        try:
            # First check if job is in active processing
            if job_id in self.active_jobs:
                job_data = self.active_jobs[job_id]
            else:
                # Check Redis storage
                job_json = self.redis_client.hget(self.jobs_key, job_id)
                if not job_json:
                    return None
                job_data = json.loads(job_json)
            
            return JobStatusResponse(
                job_id=job_data["job_id"],
                status=JobStatus(job_data["status"]),
                workflow=WorkflowType(job_data["workflow"]),
                priority=JobPriority(job_data["priority"]),
                created_at=datetime.fromisoformat(job_data["created_at"]),
                started_at=datetime.fromisoformat(job_data["started_at"]) if job_data.get("started_at") else None,
                completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data.get("completed_at") else None,
                duration_seconds=job_data.get("duration_seconds"),
                progress=job_data.get("progress"),
                current_step=job_data.get("current_step"),
                error_message=job_data.get("error_message"),
                result_data=job_data.get("result_data"),
                logs=job_data.get("logs", [])
            )
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return None
    
    async def list_jobs(self, 
                       status: Optional[JobStatus] = None,
                       limit: int = 50) -> List[JobStatusResponse]:
        """List jobs with optional filtering."""
        if not self.redis_client:
            return []
        
        try:
            all_jobs = await self.redis_client.hgetall(self.jobs_key)
            jobs = []
            
            for job_id, job_json in all_jobs.items():
                job_data = json.loads(job_json)
                job_status = JobStatus(job_data["status"])
                
                if status and job_status != status:
                    continue
                
                jobs.append(JobStatusResponse(
                    job_id=job_data["job_id"],
                    status=job_status,
                    workflow=WorkflowType(job_data["workflow"]),
                    priority=JobPriority(job_data["priority"]),
                    created_at=datetime.fromisoformat(job_data["created_at"]),
                    started_at=datetime.fromisoformat(job_data["started_at"]) if job_data.get("started_at") else None,
                    completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data.get("completed_at") else None,
                    duration_seconds=job_data.get("duration_seconds"),
                    progress=job_data.get("progress"),
                    current_step=job_data.get("current_step"),
                    error_message=job_data.get("error_message"),
                    result_data=job_data.get("result_data"),
                    logs=job_data.get("logs", [])
                ))
            
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            return jobs[:limit]
            
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []
    
    async def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a job."""
        if not self.redis_client:
            return False
        
        try:
            # Remove from queue if queued
            await self.redis_client.zrem(self.queue_key, job_id)
            
            # Update job status
            await self.update_job_status(
                job_id,
                JobStatus.CANCELLED,
                error_message=reason or "Job cancelled"
            )
            
            # Remove from active jobs if running
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["cancelled"] = True
            
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
        if not self.redis_client:
            return
        
        try:
            # Get current job data
            job_json = await self.redis_client.hget(self.jobs_key, job_id)
            if not job_json:
                logger.warning(f"Job {job_id} not found for status update")
                return
            
            job_data = json.loads(job_json)
            
            # Update status
            job_data["status"] = status.value
            
            # Update optional fields
            if progress:
                job_data["progress"] = progress
            if current_step:
                job_data["current_step"] = current_step
            if error_message:
                job_data["error_message"] = error_message
            if result_data:
                job_data["result_data"] = result_data
            
            # Set timestamps
            now = datetime.now(timezone.utc).isoformat()
            if status == JobStatus.RUNNING and not job_data.get("started_at"):
                job_data["started_at"] = now
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job_data["completed_at"] = now
                if job_data.get("started_at"):
                    start_time = datetime.fromisoformat(job_data["started_at"])
                    end_time = datetime.fromisoformat(now)
                    job_data["duration_seconds"] = int((end_time - start_time).total_seconds())
            
            # Save updated job data
            await self.redis_client.hset(
                self.jobs_key,
                job_id,
                json.dumps(job_data)
            )
            
            # Update active jobs cache
            if job_id in self.active_jobs:
                self.active_jobs[job_id].update(job_data)
            
            logger.debug(f"Updated job {job_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
    
    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue."""
        if not self.redis_client:
            return None
        
        try:
            # Check current capacity
            if len(self.active_jobs) >= self.config.max_concurrent_jobs:
                return None
            
            # Get highest priority job (lowest score)
            result = await self.redis_client.zpopmin(self.queue_key, 1)
            if not result:
                return None
            
            job_id, _ = result[0]
            
            # Get job data
            job_json = await self.redis_client.hget(self.jobs_key, job_id)
            if not job_json:
                logger.warning(f"Job {job_id} data not found")
                return None
            
            job_data = json.loads(job_json)
            
            # Move to active jobs
            self.active_jobs[job_id] = job_data
            
            # Update status to running
            await self.update_job_status(job_id, JobStatus.RUNNING)
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to get next job: {e}")
            return None
    
    async def start_processing(self):
        """Start the job processing loop."""
        if self.running:
            logger.warning("Job processing already running")
            return
        
        self.running = True
        logger.info(f"Starting job processing for processor {self.processor_id}")
        
        while self.running:
            try:
                # Get next job
                job_data = await self.get_next_job()
                if not job_data:
                    await asyncio.sleep(1)  # Wait before checking again
                    continue
                
                # Process job in background
                asyncio.create_task(self._process_job(job_data))
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def stop_processing(self):
        """Stop the job processing loop."""
        self.running = False
        logger.info("Stopping job processing")
        
        # Wait for active jobs to complete or timeout
        timeout = 30
        start_time = time.time()
        
        while self.active_jobs and (time.time() - start_time) < timeout:
            await asyncio.sleep(1)
        
        if self.active_jobs:
            logger.warning(f"Forcibly stopping with {len(self.active_jobs)} active jobs")
            self.active_jobs.clear()
    
    async def _process_job(self, job_data: Dict[str, Any]):
        """Process a single job."""
        job_id = job_data["job_id"]
        workflow = WorkflowType(job_data["workflow"])
        
        try:
            logger.info(f"Processing job {job_id} (workflow: {workflow})")
            
            # Check if handler is registered
            if workflow not in self.job_handlers:
                raise ValueError(f"No handler registered for workflow: {workflow}")
            
            # Execute the handler
            handler = self.job_handlers[workflow]
            result = await handler(job_data)
            
            # Check if job was cancelled during processing
            if job_data.get("cancelled"):
                await self.update_job_status(job_id, JobStatus.CANCELLED)
            else:
                await self.update_job_status(
                    job_id,
                    JobStatus.COMPLETED,
                    result_data=result
                )
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await self.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=str(e)
            )
        finally:
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs."""
        if not self.redis_client:
            return 0
        
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
            removed = 0
            
            all_jobs = await self.redis_client.hgetall(self.jobs_key)
            for job_id, job_json in all_jobs.items():
                job_data = json.loads(job_json)
                
                # Only clean up completed/failed/cancelled jobs
                status = JobStatus(job_data["status"])
                if status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    continue
                
                # Check age
                completed_at = job_data.get("completed_at")
                if completed_at:
                    completed_time = datetime.fromisoformat(completed_at).timestamp()
                    if completed_time < cutoff_time:
                        await self.redis_client.hdel(self.jobs_key, job_id)
                        removed += 1
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} old jobs")
            
            return removed
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "processor_id": self.processor_id,
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.config.max_concurrent_jobs,
            "registered_workflows": list(self.job_handlers.keys()),
            "running": self.running
        }