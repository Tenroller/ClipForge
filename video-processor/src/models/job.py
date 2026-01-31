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


# MoneyPrinter specific models
class MoneyPrinterRequest(BaseModel):
    """MoneyPrinter video generation request."""
    videoSubject: str = Field(..., description="Subject for the video")
    paragraphNumber: int = Field(3, description="Number of paragraphs in script")
    voice: str = Field("en_male_jomboy", description="Voice to use for TTS")
    aiModel: str = Field("gemini-2.0-flash", description="AI model for script generation")
    useMusic: bool = Field(True, description="Whether to include background music")
    zipUrl: Optional[str] = Field(None, description="URL for background music ZIP")
    useTikTokSubtitles: bool = Field(True, description="Use TikTok-style subtitles")
    subtitleFont: str = Field("Arial", description="Font for subtitles")
    customPrompt: Optional[str] = Field(None, description="Custom prompt for script generation")


class BrainrotRequest(BaseModel):
    """Brainrot compilation video generation request."""
    youtubeUrl: Optional[str] = Field(None, description="YouTube URL to process")
    uploadedVideoPath: Optional[str] = Field(None, description="Path to uploaded video file (alternative to YouTube URL)")
    numCompilations: int = Field(1, description="Number of compilations to generate")
    minDuration: int = Field(30, description="Minimum duration in seconds")
    maxDuration: int = Field(60, description="Maximum duration in seconds")
    maxReuse: int = Field(3, description="Maximum reuse count")
    unlimited: bool = Field(False, description="Generate unlimited compilations")
    generateNoBackground: bool = Field(True, description="Generate third variation without white background")
    blurredPillarboxThreshold: float = Field(0.1, description="Aspect ratio tolerance for 9:16 format")

    def model_post_init(self, __context: Any) -> None:
        """Ensure exactly one of youtubeUrl or uploadedVideoPath is provided"""
        if not self.youtubeUrl and not self.uploadedVideoPath:
            raise ValueError("Either youtubeUrl or uploadedVideoPath must be provided")
        if self.youtubeUrl and self.uploadedVideoPath:
            raise ValueError("Cannot provide both youtubeUrl and uploadedVideoPath - choose one input method")


class PodcastClipsRequest(BaseModel):
    """PodcastClips viral short-form video generation request."""
    youtubeUrl: str = Field(..., description="YouTube URL of the podcast to process")
    aiModel: str = Field("gemini-2.0-flash", description="AI model for viral moment detection")
    whisperModel: str = Field("base", description="Whisper model size: tiny, base, small, medium, large")
    maxClipCount: int = Field(15, description="Maximum number of clips to generate (AI decides actual count based on viral potential)")
    minDuration: int = Field(20, description="Minimum clip duration in seconds")
    maxDuration: int = Field(70, description="Maximum clip duration in seconds")
    useGPU: bool = Field(True, description="Use GPU acceleration for processing")
    subtitleFontSize: int = Field(40, description="Subtitle font size")
    subtitleColor: str = Field("#FFFFFF", description="Subtitle text color (hex format)")
    subtitleStrokeColor: str = Field("#000000", description="Subtitle stroke/outline color")
    subtitleStrokeWidth: int = Field(2, description="Subtitle stroke width")
    subtitleStyle: str = Field("yellow_highlight", description="Subtitle style: yellow_highlight, multicolor_pop, clean_outline")
    subtitleDisplayMode: str = Field("word", description="Display mode: word (word-by-word) or sentence (full sentence)")
    subtitlePosition: str = Field("bottom", description="Subtitle position: top, center, bottom")
    subtitleHighlightColor: str = Field("#FFD700", description="Highlight/accent color for subtitles (hex format)")
    subtitleVerticalOffset: int = Field(500, description="Vertical offset from subtitle position in pixels")
    subtitleMaxWordsVisible: int = Field(5, description="Maximum words visible at once in word-by-word mode")
    viralFocusKeywords: List[str] = Field(default_factory=list, description="Optional keywords to prioritize when detecting viral moments")


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