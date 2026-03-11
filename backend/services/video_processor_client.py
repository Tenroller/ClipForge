"""
Client for communicating with Video Processing API instances
"""

import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..logging_config import get_logger

logger = get_logger("video_processor_client")


class VideoProcessorClient:
    """Client for communicating with Video Processing API instances."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def submit_job(self, 
                        job_id: str,
                        workflow: str,
                        request_data: Dict[str, Any],
                        priority: str = "normal",
                        callback_url: Optional[str] = None) -> Dict[str, Any]:
        """Submit a job to the video processor."""
        try:
            payload = {
                "job_id": job_id,
                "workflow": workflow,
                "priority": priority,
                "request_data": request_data,
                "callback_url": callback_url
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/jobs",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully submitted job {job_id} to processor {self.base_url}")
            return result
            
        except httpx.RequestError as e:
            logger.error(f"Failed to submit job {job_id} to processor {self.base_url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error submitting job {job_id} to processor {self.base_url}: {e.response.status_code}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from the processor."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/jobs/{job_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Failed to get job status {job_id} from processor {self.base_url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"HTTP error getting job status {job_id} from processor {self.base_url}: {e.response.status_code}")
            return None
    
    async def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a job on the processor."""
        try:
            payload = {"reason": reason} if reason else {}
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/jobs/{job_id}/cancel",
                json=payload,
                headers=self._get_headers()
            )
            
            if response.status_code == 404:
                return False
            
            response.raise_for_status()
            logger.info(f"Successfully cancelled job {job_id} on processor {self.base_url}")
            return True
            
        except httpx.RequestError as e:
            logger.error(f"Failed to cancel job {job_id} on processor {self.base_url}: {e}")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            logger.error(f"HTTP error cancelling job {job_id} on processor {self.base_url}: {e.response.status_code}")
            return False
    
    async def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List jobs on the processor."""
        try:
            params: Dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            
            response = await self.client.get(
                f"{self.base_url}/api/v1/jobs",
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("jobs", [])
            
        except httpx.RequestError as e:
            logger.error(f"Failed to list jobs from processor {self.base_url}: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error listing jobs from processor {self.base_url}: {e.response.status_code}")
            return []
    
    async def get_processor_status(self) -> Optional[Dict[str, Any]]:
        """Get processor status."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/status",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Failed to get processor status from {self.base_url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting processor status from {self.base_url}: {e.response.status_code}")
            return None
    
    async def health_check(self) -> bool:
        """Check if processor is healthy."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/health",
                headers=self._get_headers()
            )
            return response.status_code == 200

        except:
            return False

    async def get_available_voices(self) -> Optional[List[str]]:
        """Get available TTS voices from processor."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/voices",
                headers=self._get_headers()
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            return data.get("voices", [])

        except httpx.RequestError as e:
            logger.error(f"Failed to get voices from processor {self.base_url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"HTTP error getting voices from processor {self.base_url}: {e.response.status_code}")
            return None


class ProcessorManager:
    """Manages multiple video processor instances."""
    
    def __init__(self, processor_urls: List[str], api_key: Optional[str] = None):
        self.processors = [
            VideoProcessorClient(url, api_key) 
            for url in processor_urls
        ]
        self.current_index = 0
    
    async def close(self):
        """Close all processor clients."""
        for processor in self.processors:
            await processor.close()
    
    async def get_available_processor(self) -> Optional[VideoProcessorClient]:
        """Get an available processor using round-robin."""
        if not self.processors:
            return None

        # First pass: Try to find a processor with available capacity
        for i in range(len(self.processors)):
            processor_index = (self.current_index + i) % len(self.processors)
            processor = self.processors[processor_index]

            if await processor.health_check():
                status = await processor.get_processor_status()
                if status and status.get("current_jobs", 0) < status.get("max_concurrent_jobs", 1):
                    # Update current index for next request
                    self.current_index = (processor_index + 1) % len(self.processors)
                    return processor

        # Second pass: If all processors are at capacity, use any healthy processor (jobs will be queued)
        for i in range(len(self.processors)):
            processor_index = (self.current_index + i) % len(self.processors)
            processor = self.processors[processor_index]

            if await processor.health_check():
                logger.info(f"All processors at capacity, queueing job to processor {processor_index}")
                # Update current index for next request
                self.current_index = (processor_index + 1) % len(self.processors)
                return processor

        return None
    
    async def submit_job(self,
                        job_id: str,
                        workflow: str,
                        request_data: Dict[str, Any],
                        priority: str = "normal",
                        callback_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Submit a job to an available processor."""
        processor = await self.get_available_processor()
        if not processor:
            logger.error("No available processors for job submission")
            return None
        
        try:
            return await processor.submit_job(job_id, workflow, request_data, priority, callback_url)
        except Exception as e:
            logger.error(f"Failed to submit job {job_id}: {e}")
            return None
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from any processor that has it."""
        for processor in self.processors:
            status = await processor.get_job_status(job_id)
            if status:
                return status
        return None
    
    async def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a job on whichever processor has it."""
        for processor in self.processors:
            if await processor.cancel_job(job_id, reason):
                return True
        return False
    
    async def get_all_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get jobs from all processors."""
        all_jobs = []
        for processor in self.processors:
            jobs = await processor.list_jobs(status=status)
            all_jobs.extend(jobs)
        return all_jobs
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get status of all processors."""
        statuses = []
        healthy_count = 0
        total_capacity = 0
        total_active = 0
        
        for i, processor in enumerate(self.processors):
            processor_status = await processor.get_processor_status()
            if processor_status:
                healthy_count += 1
                total_capacity += processor_status.get("max_concurrent_jobs", 0)
                total_active += processor_status.get("current_jobs", 0)
                statuses.append({
                    "index": i,
                    "url": processor.base_url,
                    "status": "healthy",
                    **processor_status
                })
            else:
                statuses.append({
                    "index": i,
                    "url": processor.base_url,
                    "status": "unhealthy"
                })
        
        return {
            "total_processors": len(self.processors),
            "healthy_processors": healthy_count,
            "total_capacity": total_capacity,
            "total_active_jobs": total_active,
            "utilization": (total_active / total_capacity) if total_capacity > 0 else 0,
            "processors": statuses
        }

    async def get_available_voices(self) -> Optional[List[str]]:
        """Get available TTS voices from any healthy processor."""
        for processor in self.processors:
            if await processor.health_check():
                voices = await processor.get_available_voices()
                if voices:
                    return voices
        return None