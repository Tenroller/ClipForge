"""
Batch processing capabilities for the AI Video Generator.
"""

import uuid
import time
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from job_queue import get_job_queue, JobPriority, background_job
from database import get_job_store
from logging_config import get_logger

logger = get_logger("batch_processing")


class BatchStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class BatchJob:
    id: str
    workflow: str
    parameters: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: str = "pending"
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class BatchRequest:
    id: str
    name: str
    workflow: str
    jobs: List[BatchJob]
    priority: JobPriority = JobPriority.NORMAL
    max_concurrent: int = 3
    stop_on_error: bool = False
    status: BatchStatus = BatchStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    results: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.results is None:
            self.results = []


class BatchProcessor:
    """Process batches of video generation jobs."""
    
    def __init__(self):
        self.batches: Dict[str, BatchRequest] = {}
        self.active_batches: Dict[str, Dict[str, Any]] = {}
        self.job_queue = get_job_queue()
        self.job_store = get_job_store()
        self.lock = threading.RLock()
    
    def create_batch(self, name: str, workflow: str, job_parameters: List[Dict[str, Any]],
                    priority: JobPriority = JobPriority.NORMAL, max_concurrent: int = 3,
                    stop_on_error: bool = False) -> str:
        """Create a new batch processing request."""
        batch_id = str(uuid.uuid4())
        
        # Create individual jobs
        jobs = []
        for params in job_parameters:
            job = BatchJob(
                id=str(uuid.uuid4()),
                workflow=workflow,
                parameters=params,
                priority=priority
            )
            jobs.append(job)
        
        # Create batch request
        batch = BatchRequest(
            id=batch_id,
            name=name,
            workflow=workflow,
            jobs=jobs,
            priority=priority,
            max_concurrent=max_concurrent,
            stop_on_error=stop_on_error
        )
        
        with self.lock:
            self.batches[batch_id] = batch
        
        logger.info(f"✅ Created batch '{name}' with {len(jobs)} jobs (ID: {batch_id})")
        return batch_id
    
    def start_batch(self, batch_id: str) -> bool:
        """Start processing a batch."""
        with self.lock:
            if batch_id not in self.batches:
                logger.error(f"Batch {batch_id} not found")
                return False
            
            batch = self.batches[batch_id]
            
            if batch.status != BatchStatus.PENDING:
                logger.error(f"Batch {batch_id} is not in pending status")
                return False
            
            batch.status = BatchStatus.RUNNING
            batch.started_at = datetime.utcnow()
            
            # Start batch processing in background
            self.active_batches[batch_id] = {
                'semaphore': threading.Semaphore(batch.max_concurrent),
                'completed_jobs': 0,
                'failed_jobs': 0,
                'job_results': {}
            }
        
        # Queue batch processing job
        self.job_queue.enqueue_job(
            self._process_batch,
            args=(batch_id,),
            job_id=f"batch-{batch_id}",
            priority=batch.priority
        )
        
        logger.info(f"✅ Started batch processing: {batch_id}")
        return True
    
    def _process_batch(self, batch_id: str):
        """Process all jobs in a batch."""
        try:
            with self.lock:
                batch = self.batches[batch_id]
                active_info = self.active_batches[batch_id]
            
            logger.info(f"Processing batch {batch_id} with {len(batch.jobs)} jobs")
            
            # Start individual jobs
            job_threads = []
            for job in batch.jobs:
                if batch.stop_on_error and active_info['failed_jobs'] > 0:
                    break
                
                thread = threading.Thread(
                    target=self._process_batch_job,
                    args=(batch_id, job),
                    daemon=True
                )
                thread.start()
                job_threads.append(thread)
            
            # Wait for all jobs to complete
            for thread in job_threads:
                thread.join()
            
            # Update batch status
            with self.lock:
                batch = self.batches[batch_id]
                active_info = self.active_batches[batch_id]
                
                batch.completed_at = datetime.utcnow()
                batch.progress = 1.0
                
                total_jobs = len(batch.jobs)
                completed = active_info['completed_jobs']
                failed = active_info['failed_jobs']
                
                if failed == 0:
                    batch.status = BatchStatus.COMPLETED
                elif completed == 0:
                    batch.status = BatchStatus.FAILED
                else:
                    batch.status = BatchStatus.PARTIALLY_COMPLETED
                
                # Collect results
                batch.results = [
                    active_info['job_results'].get(job.id, {"error": "No result"})
                    for job in batch.jobs
                ]
                
                # Clean up active batch info
                del self.active_batches[batch_id]
            
            logger.info(f"✅ Batch {batch_id} completed: {completed}/{total_jobs} successful, {failed} failed")
            
        except Exception as e:
            logger.error(f"Batch processing failed for {batch_id}: {e}")
            with self.lock:
                if batch_id in self.batches:
                    self.batches[batch_id].status = BatchStatus.FAILED
                    self.batches[batch_id].completed_at = datetime.utcnow()
                if batch_id in self.active_batches:
                    del self.active_batches[batch_id]
    
    def _process_batch_job(self, batch_id: str, job: BatchJob):
        """Process a single job within a batch."""
        with self.active_batches[batch_id]['semaphore']:
            try:
                job.started_at = datetime.utcnow()
                job.status = "running"
                
                # Queue the actual video generation job
                if job.workflow == "moneyprinter":
                    result = self._process_moneyprinter_job(job.parameters)
                elif job.workflow == "brainrot":
                    result = self._process_brainrot_job(job.parameters)
                else:
                    raise ValueError(f"Unknown workflow: {job.workflow}")
                
                job.status = "completed"
                job.result = result
                job.completed_at = datetime.utcnow()
                
                with self.lock:
                    active_info = self.active_batches[batch_id]
                    active_info['completed_jobs'] += 1
                    active_info['job_results'][job.id] = result
                    
                    # Update batch progress
                    batch = self.batches[batch_id]
                    total_jobs = len(batch.jobs)
                    completed = active_info['completed_jobs'] + active_info['failed_jobs']
                    batch.progress = completed / total_jobs
                
                logger.info(f"✅ Batch job {job.id} completed successfully")
                
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                
                with self.lock:
                    active_info = self.active_batches[batch_id]
                    active_info['failed_jobs'] += 1
                    active_info['job_results'][job.id] = {"error": str(e)}
                    
                    # Update batch progress
                    batch = self.batches[batch_id]
                    total_jobs = len(batch.jobs)
                    completed = active_info['completed_jobs'] + active_info['failed_jobs']
                    batch.progress = completed / total_jobs
                
                logger.error(f"❌ Batch job {job.id} failed: {e}")
    
    def _process_moneyprinter_job(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a MoneyPrinter job."""
        # Import here to avoid circular imports
        from app import MoneyPrinterRequest
        from vendors.moneyprinter.main import generate_video
        
        # Create request object
        request = MoneyPrinterRequest(**parameters)
        
        # Mock job processing (in real implementation, this would call the actual generator)
        # For now, simulate processing time
        time.sleep(10)  # Simulate video generation
        
        return {
            "success": True,
            "video_path": f"/tmp/video_{uuid.uuid4()}.mp4",
            "duration": 30.0,
            "parameters": parameters
        }
    
    def _process_brainrot_job(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a Brainrot job."""
        # Import here to avoid circular imports
        from app import BrainrotRequest
        
        # Create request object
        request = BrainrotRequest(**parameters)
        
        # Mock job processing
        time.sleep(15)  # Simulate video generation
        
        return {
            "success": True,
            "video_path": f"/tmp/brainrot_{uuid.uuid4()}.mp4",
            "duration": 60.0,
            "parameters": parameters
        }
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a batch."""
        with self.lock:
            if batch_id not in self.batches:
                return None
            
            batch = self.batches[batch_id]
            
            # Calculate job status summary
            job_status_counts = {}
            for job in batch.jobs:
                status = job.status
                job_status_counts[status] = job_status_counts.get(status, 0) + 1
            
            return {
                "id": batch.id,
                "name": batch.name,
                "workflow": batch.workflow,
                "status": batch.status.value,
                "progress": batch.progress,
                "total_jobs": len(batch.jobs),
                "job_status_counts": job_status_counts,
                "created_at": batch.created_at.isoformat(),
                "started_at": batch.started_at.isoformat() if batch.started_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
                "max_concurrent": batch.max_concurrent,
                "stop_on_error": batch.stop_on_error
            }
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch and all its jobs."""
        with self.lock:
            if batch_id not in self.batches:
                return False
            
            batch = self.batches[batch_id]
            batch.status = BatchStatus.CANCELLED
            
            # Cancel individual jobs
            for job in batch.jobs:
                if job.status in ["pending", "running"]:
                    job.status = "cancelled"
            
            # Remove from active batches
            if batch_id in self.active_batches:
                del self.active_batches[batch_id]
        
        logger.info(f"✅ Cancelled batch: {batch_id}")
        return True
    
    def list_batches(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all batches."""
        with self.lock:
            batches = list(self.batches.values())
            batches.sort(key=lambda b: b.created_at, reverse=True)
            
            return [
                {
                    "id": batch.id,
                    "name": batch.name,
                    "workflow": batch.workflow,
                    "status": batch.status.value,
                    "progress": batch.progress,
                    "total_jobs": len(batch.jobs),
                    "created_at": batch.created_at.isoformat(),
                    "started_at": batch.started_at.isoformat() if batch.started_at else None,
                    "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
                }
                for batch in batches[:limit]
            ]
    
    def get_batch_results(self, batch_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get detailed results for a batch."""
        with self.lock:
            if batch_id not in self.batches:
                return None
            
            batch = self.batches[batch_id]
            
            results = []
            for job in batch.jobs:
                result = {
                    "job_id": job.id,
                    "status": job.status,
                    "parameters": job.parameters,
                    "created_at": job.created_at.isoformat(),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None
                }
                
                if job.result:
                    result["result"] = job.result
                if job.error:
                    result["error"] = job.error
                
                results.append(result)
            
            return results
    
    def create_template_batch(self, template_type: str, count: int = 10) -> str:
        """Create a batch from a template for testing/demo purposes."""
        if template_type == "moneyprinter_subjects":
            subjects = [
                "The future of artificial intelligence",
                "Climate change solutions",
                "Space exploration missions",
                "Ancient civilizations mysteries",
                "Ocean life discoveries",
                "Renewable energy innovations",
                "Quantum computing breakthroughs",
                "Medical research advances",
                "Astronomical phenomena",
                "Wildlife conservation efforts"
            ]
            
            job_params = [
                {
                    "videoSubject": subjects[i % len(subjects)],
                    "aiModel": "gemini-2.0-flash",
                    "paragraphNumber": 2,
                    "voice": "af_bella"
                }
                for i in range(count)
            ]
            
            return self.create_batch(
                name=f"MoneyPrinter Template Batch ({count} videos)",
                workflow="moneyprinter",
                job_parameters=job_params,
                priority=JobPriority.LOW,
                max_concurrent=2
            )
        
        elif template_type == "brainrot_compilation":
            youtube_urls = [
                "https://youtu.be/dQw4w9WgXcQ",  # Rick Roll (example)
                "https://youtu.be/oHg5SJYRHA0",  # RickRoll 2
                # Add more example URLs
            ]
            
            job_params = [
                {
                    "youtubeUrl": youtube_urls[i % len(youtube_urls)],
                    "numCompilations": 1,
                    "minDuration": 60,
                    "maxDuration": 120
                }
                for i in range(min(count, len(youtube_urls)))
            ]
            
            return self.create_batch(
                name=f"Brainrot Template Batch ({len(job_params)} compilations)",
                workflow="brainrot",
                job_parameters=job_params,
                priority=JobPriority.LOW,
                max_concurrent=1
            )
        
        else:
            raise ValueError(f"Unknown template type: {template_type}")
    
    def cleanup_old_batches(self, days: int = 7) -> int:
        """Clean up old completed batches."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cleaned = 0
        
        with self.lock:
            to_delete = []
            for batch_id, batch in self.batches.items():
                if (batch.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED] and
                    batch.completed_at and batch.completed_at < cutoff):
                    to_delete.append(batch_id)
            
            for batch_id in to_delete:
                del self.batches[batch_id]
                cleaned += 1
        
        if cleaned > 0:
            logger.info(f"✅ Cleaned up {cleaned} old batches")
        
        return cleaned


# Global batch processor instance
_batch_processor: Optional[BatchProcessor] = None


def get_batch_processor() -> BatchProcessor:
    """Get or create the global batch processor instance."""
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor()
        logger.info("✅ Batch processor initialized")
    return _batch_processor


# Convenience functions for batch operations
def create_moneyprinter_batch(subjects: List[str], name: str = None, **common_params) -> str:
    """Create a batch for multiple MoneyPrinter videos."""
    processor = get_batch_processor()
    
    job_params = []
    for subject in subjects:
        params = {"videoSubject": subject}
        params.update(common_params)
        job_params.append(params)
    
    batch_name = name or f"MoneyPrinter Batch ({len(subjects)} videos)"
    
    return processor.create_batch(
        name=batch_name,
        workflow="moneyprinter",
        job_parameters=job_params
    )


def create_brainrot_batch(youtube_urls: List[str], name: str = None, **common_params) -> str:
    """Create a batch for multiple Brainrot compilations."""
    processor = get_batch_processor()
    
    job_params = []
    for url in youtube_urls:
        params = {"youtubeUrl": url}
        params.update(common_params)
        job_params.append(params)
    
    batch_name = name or f"Brainrot Batch ({len(youtube_urls)} compilations)"
    
    return processor.create_batch(
        name=batch_name,
        workflow="brainrot",
        job_parameters=job_params
    )


def start_batch_job(batch_id: str) -> bool:
    """Start a batch job."""
    return get_batch_processor().start_batch(batch_id)


def get_batch_info(batch_id: str) -> Optional[Dict[str, Any]]:
    """Get batch information."""
    return get_batch_processor().get_batch_status(batch_id)
