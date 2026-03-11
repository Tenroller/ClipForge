"""
Data models for video processing API
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowType(str, Enum):
    """Supported workflow types."""
    MONEYPRINTER = "moneyprinter"
    BRAINROT = "brainrot"
    PODCASTCLIPS = "podcastclips"


# Job models
class ProcessingJobRequest(BaseModel):
    """Request to create a new processing job."""
    job_id: str = Field(..., description="Unique job identifier")
    workflow: WorkflowType = Field(..., description="Type of workflow to execute")
    priority: JobPriority = Field(JobPriority.NORMAL, description="Job priority")
    request_data: Dict[str, Any] = Field(..., description="Workflow-specific request data")
    callback_url: Optional[str] = Field(None, description="URL to call when job completes")
    timeout_seconds: Optional[int] = Field(None, description="Job timeout override")


class ProcessingJobResponse(BaseModel):
    """Response for job creation."""
    job_id: str
    status: JobStatus
    message: str
    estimated_duration: Optional[int] = None


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    job_id: str
    status: JobStatus
    workflow: WorkflowType
    priority: JobPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    progress: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    logs: List[str] = Field(default_factory=list)


class JobListResponse(BaseModel):
    """Response for listing jobs."""
    jobs: List[JobStatusResponse]
    total: int
    page: int = 1
    page_size: int = 50


class ProcessorStatusResponse(BaseModel):
    """Response for processor status."""
    processor_id: str
    status: str
    current_jobs: int
    max_concurrent_jobs: int
    total_processed: int
    uptime_seconds: int
    last_heartbeat: datetime
    available_workflows: List[WorkflowType]


class JobCancelRequest(BaseModel):
    """Request to cancel a job."""
    reason: Optional[str] = Field(None, description="Reason for cancellation")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    processor_id: str
    timestamp: datetime
    queue_size: int
    active_jobs: int
    system_resources: Dict[str, Any]


# Callback models for communicating with backend API
class JobUpdateCallback(BaseModel):
    """Callback payload sent to backend API on job updates."""
    job_id: str
    processor_id: str
    status: JobStatus
    progress: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[int] = None


class ProcessorHeartbeat(BaseModel):
    """Heartbeat payload sent to backend API."""
    processor_id: str
    status: str
    current_jobs: int
    max_concurrent_jobs: int
    last_activity: datetime
    queue_size: int