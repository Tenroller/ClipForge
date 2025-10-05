"""
Video processing orchestration service
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..models.requests import MoneyPrinterRequest, BrainrotRequest
from ..database import get_job_store
from ..logging_config import get_logger
from ..core.config import AppConfig
from .video_processor_client import ProcessorManager as VideoProcessorManager

logger = get_logger("video_orchestrator")

# Use correct imports
JobStore = get_job_store


class VideoOrchestrationService:
    """Service for orchestrating video processing across multiple processors."""
    
    def __init__(self, config: AppConfig):
        """Initialize the video orchestrator."""
        self.config = config
        # Get processor URLs from config
        self.processor_manager = VideoProcessorManager(config.video_processor_urls, config.video_processor_api_key)
        self.job_store = JobStore()
        logger.info("Video orchestrator initialized")
    
    async def close(self):
        """Clean up resources."""
        await self.processor_manager.close()
    
    async def submit_moneyprinter_job(self, job_id: str, request: MoneyPrinterRequest) -> bool:
        """Submit a MoneyPrinter job to available processor."""
        try:
            logger.info(f"Submitting MoneyPrinter job {job_id} to processor")
            
            # Prepare request data
            request_data = request.model_dump()
            
            # Submit to processor
            result = await self.processor_manager.submit_job(
                job_id=job_id,
                workflow="moneyprinter",
                request_data=request_data,
                priority="normal",
                callback_url=self._get_callback_url(job_id)
            )
            
            if result:
                # Job submitted successfully - frontend handles polling via REST API
                logger.info(f"Successfully submitted MoneyPrinter job {job_id}")
                return True
            else:
                logger.error(f"Failed to submit MoneyPrinter job {job_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting MoneyPrinter job {job_id}: {e}")
            return False
    
    async def submit_brainrot_job(self, job_id: str, request: BrainrotRequest) -> bool:
        """Submit a Brainrot job to available processor."""
        try:
            logger.info(f"Submitting Brainrot job {job_id} to processor")
            
            # Prepare request data
            request_data = request.model_dump()
            
            # Submit to processor
            result = await self.processor_manager.submit_job(
                job_id=job_id,
                workflow="brainrot",
                request_data=request_data,
                priority="normal",
                callback_url=self._get_callback_url(job_id)
            )
            
            if result:
                # Job submitted successfully - frontend handles polling via REST API
                logger.info(f"Successfully submitted Brainrot job {job_id}")
                return True
            else:
                logger.error(f"Failed to submit Brainrot job {job_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting Brainrot job {job_id}: {e}")
            return False
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job on the processors."""
        try:
            # Cancel on processor
            result = await self.processor_manager.cancel_job(job_id, "Cancelled by user")
            
            if result:
                # Update database
                self.job_store.update_job(
                    job_id,
                    status="cancelled",
                    error_message="Cancelled by user",
                    ended_at=datetime.now(timezone.utc).isoformat()
                )
                logger.info(f"Successfully cancelled job {job_id}")
                return True
            else:
                logger.warning(f"Job {job_id} not found on processors or already completed")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status, first from database, then from processors."""
        try:
            # Check database first
            job = self.job_store.get_job(job_id)
            if job:
                # If job is completed, return database status
                if job.get("status") in ["done", "error", "cancelled"]:
                    return job
                
                # If job is running/queued, check processor for latest status
                processor_status = await self.processor_manager.get_job_status(job_id)
                if processor_status:
                    # Merge processor status with database job
                    job.update({
                        "current_step": processor_status.get("current_step"),
                        "progress": processor_status.get("progress"),
                        "logs": processor_status.get("logs", [])
                    })
                
                return job
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None
    
    async def get_processor_cluster_status(self) -> Dict[str, Any]:
        """Get status of the processor cluster."""
        return await self.processor_manager.get_cluster_status()
    
    def _get_callback_url(self, job_id: str) -> Optional[str]:
        """Get callback URL for job updates."""
        # Return the callback URL where the video processor can send status updates
        # Use the backend service name for container-to-container communication
        return "http://backend:9000/api/jobs/callback"


# Global instance
_orchestrator: Optional[VideoOrchestrationService] = None


def get_video_orchestrator() -> VideoOrchestrationService:
    """Get or create the global video orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        from ..core.config import AppConfig
        config = AppConfig.from_env()
        _orchestrator = VideoOrchestrationService(config)
    return _orchestrator


def cleanup_video_orchestrator():
    """Clean up the global video orchestrator."""
    global _orchestrator
    if _orchestrator:
        _orchestrator = None
        _orchestrator = None