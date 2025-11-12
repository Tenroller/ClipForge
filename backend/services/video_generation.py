"""
Video generation service layer.

This service handles video generation requests by delegating the actual
video processing to the video-processor microservice.
"""

from typing import Dict, Any, Optional

from ..models.requests import MoneyPrinterRequest, BrainrotRequest
from ..logging_config import get_logger
from .video_processor_client import ProcessorManager


class VideoGenerationService:
    """Service for handling video generation workflows via video-processor microservice."""

    def __init__(self, processor_manager: Optional[ProcessorManager] = None):
        self.logger = get_logger("video_generation.service")
        self.processor_manager = processor_manager or self._create_default_processor_manager()
    
    def _create_default_processor_manager(self) -> ProcessorManager:
        """Create a default processor manager with video-processor instances."""
        # TODO: Load these URLs from configuration
        processor_urls = [
            "http://localhost:8001",  # Default video-processor instance
        ]
        return ProcessorManager(processor_urls)
    
    async def generate_moneyprinter_video(self, job_id: str, request: MoneyPrinterRequest) -> Dict[str, Any]:
        """
        Generate video using MoneyPrinter workflow via video-processor service.
        
        Args:
            job_id: Unique job identifier
            request: MoneyPrinter generation request
            
        Returns:
            Dictionary containing job submission result
        """
        self.logger.info(f"Submitting MoneyPrinter job {job_id} to video-processor")
        
        # Convert request to dictionary for processor
        request_data = request.model_dump()
        
        # Submit job to video processor
        result = await self.processor_manager.submit_job(
            job_id=job_id,
            workflow="moneyprinter",
            request_data=request_data,
            priority="normal",
            callback_url=f"http://localhost:9000/api/jobs/{job_id}/callback"  # TODO: Make configurable
        )
        
        if not result:
            raise RuntimeError("Failed to submit job to video processor")
        
        self.logger.info(f"Successfully submitted MoneyPrinter job {job_id}")
        return result
    
    async def generate_brainrot_video(self, job_id: str, request: BrainrotRequest) -> Dict[str, Any]:
        """
        Generate video using Brainrot workflow via video-processor service.
        
        Args:
            job_id: Unique job identifier
            request: Brainrot generation request
            
        Returns:
            Dictionary containing job submission result
        """
        self.logger.info(f"Submitting Brainrot job {job_id} to video-processor")
        
        # Convert request to dictionary for processor
        request_data = request.model_dump()
        
        # Submit job to video processor
        result = await self.processor_manager.submit_job(
            job_id=job_id,
            workflow="brainrot",
            request_data=request_data,
            priority="normal",
            callback_url=f"http://localhost:9000/api/jobs/{job_id}/callback"  # TODO: Make configurable
        )
        
        if not result:
            raise RuntimeError("Failed to submit job to video processor")
        
        self.logger.info(f"Successfully submitted Brainrot job {job_id}")
        return result
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from video processor."""
        return await self.processor_manager.get_job_status(job_id)
    
    async def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a job in the video processor."""
        return await self.processor_manager.cancel_job(job_id, reason)
    
    async def get_processor_health(self) -> Dict[str, Any]:
        """Get health status of all video processors."""
        return await self.processor_manager.get_cluster_status()
    
    async def close(self):
        """Close processor connections."""
        if self.processor_manager:
            await self.processor_manager.close()
