#!/usr/bin/env python3
"""
Data Models for TikYou Video Generator

This module defines dataclasses for structured data used throughout
the video generation system to improve type safety and code organization.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum
from datetime import datetime
from pathlib import Path


class VideoOrientation(Enum):
    """Video orientation enumeration"""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    SQUARE = "square"
    UNKNOWN = "unknown"


class ProcessingStatus(Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CompilationType(Enum):
    """Compilation type enumeration"""
    NORMAL = "normal"
    TTS = "tts"
    HEAVILY_EDITED = "heavily_edited"


class SceneType(Enum):
    """Scene type enumeration"""
    SINGLE = "single"
    SPLIT = "split"
    COMPILATION = "compilation"


@dataclass
class VideoMetadata:
    """Video metadata information"""
    width: int
    height: int
    duration: float
    fps: float
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    file_size: Optional[int] = None
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio"""
        return self.width / self.height if self.height > 0 else 0.0
    
    @property
    def orientation(self) -> VideoOrientation:
        """Determine video orientation"""
        if self.width > self.height:
            return VideoOrientation.HORIZONTAL
        elif self.width < self.height:
            return VideoOrientation.VERTICAL
        else:
            return VideoOrientation.SQUARE
    
    @property
    def resolution(self) -> Tuple[int, int]:
        """Get resolution as tuple"""
        return (self.width, self.height)
    
    @property
    def is_high_resolution(self) -> bool:
        """Check if video is high resolution (above 1080p)"""
        return self.width * self.height > 1920 * 1080


@dataclass
class ClipInfo:
    """Information about a video clip"""
    id: str
    path: str
    duration: float
    orientation: VideoOrientation
    source_id: str
    type: SceneType
    metadata: Optional[VideoMetadata] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    scene_number: Optional[int] = None
    usage_count: int = 0
    
    def __post_init__(self):
        """Post-initialization validation"""
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Clip file not found: {self.path}")
    
    @property
    def filename(self) -> str:
        """Get filename without path"""
        return os.path.basename(self.path)
    
    @property
    def file_size(self) -> int:
        """Get file size in bytes"""
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size / (1024 * 1024)
    
    def is_available_for_use(self, max_usage: int = 3) -> bool:
        """Check if clip is available for use based on usage count"""
        return self.usage_count < max_usage
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1


@dataclass
class SceneInfo:
    """Information about a detected scene"""
    start_time: float
    end_time: float
    scene_number: int
    confidence: float = 0.0
    
    @property
    def duration(self) -> float:
        """Calculate scene duration"""
        return self.end_time - self.start_time
    
    def __post_init__(self):
        """Post-initialization validation"""
        if self.start_time >= self.end_time:
            raise ValueError(f"Start time {self.start_time} must be less than end time {self.end_time}")
        
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


@dataclass
class VideoAnalysis:
    """Results of video analysis"""
    video_path: str
    duration: float
    is_compilation: bool
    scenes: List[SceneInfo]
    metadata: Optional[VideoMetadata] = None
    detection_sensitivity: float = 30.0
    
    @property
    def total_scenes(self) -> int:
        """Get total number of scenes"""
        return len(self.scenes)
    
    @property
    def average_scene_duration(self) -> float:
        """Calculate average scene duration"""
        if not self.scenes:
            return 0.0
        return sum(scene.duration for scene in self.scenes) / len(self.scenes)
    
    @property
    def shortest_scene(self) -> Optional[SceneInfo]:
        """Get the shortest scene"""
        return min(self.scenes, key=lambda s: s.duration) if self.scenes else None
    
    @property
    def longest_scene(self) -> Optional[SceneInfo]:
        """Get the longest scene"""
        return max(self.scenes, key=lambda s: s.duration) if self.scenes else None


@dataclass
class ProcessingParams:
    """Parameters for video processing"""
    max_workers: int = 4
    chunk_size: int = 5
    quality_preset: str = "medium"
    bitrate: str = "4000k"
    memory_conservative: bool = False
    processing_strategy: str = "parallel"
    
    # Encoding specific
    codec: str = "libx264"
    audio_codec: str = "aac"
    fps: int = 30
    ffmpeg_params: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "max_workers": self.max_workers,
            "chunk_size": self.chunk_size,
            "quality_preset": self.quality_preset,
            "bitrate": self.bitrate,
            "memory_conservative": self.memory_conservative,
            "processing_strategy": self.processing_strategy,
            "codec": self.codec,
            "audio_codec": self.audio_codec,
            "fps": self.fps,
            "ffmpeg_params_count": len(self.ffmpeg_params)
        }


@dataclass
class SystemResources:
    """System resource information"""
    cpu_percent: float
    memory_percent: float
    available_memory_gb: float
    disk_space_gb: float
    gpu_available: bool = False
    gpu_memory_gb: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_under_pressure(self, cpu_threshold: float = 85.0, 
                         memory_threshold: float = 80.0) -> bool:
        """Check if system is under resource pressure"""
        return self.cpu_percent > cpu_threshold or self.memory_percent > memory_threshold
    
    def has_low_memory(self, threshold_gb: float = 2.0) -> bool:
        """Check if system has low available memory"""
        return self.available_memory_gb < threshold_gb
    
    def has_low_disk_space(self, threshold_gb: float = 5.0) -> bool:
        """Check if system has low disk space"""
        return self.disk_space_gb < threshold_gb


@dataclass
class CompilationRequest:
    """Request for creating a compilation"""
    clips: List[ClipInfo]
    output_path: str
    compilation_type: CompilationType
    compilation_num: int
    min_duration: float = 20.0
    max_duration: float = 40.0
    target_resolution: Tuple[int, int] = (1080, 1920)
    title: Optional[str] = None
    
    @property
    def total_clips_duration(self) -> float:
        """Calculate total duration of all clips"""
        return sum(clip.duration for clip in self.clips)
    
    @property
    def clips_count(self) -> int:
        """Get number of clips"""
        return len(self.clips)
    
    def validate(self) -> List[str]:
        """Validate compilation request"""
        errors = []
        
        if not self.clips:
            errors.append("No clips provided")
        
        # Duration limits removed - compilations can be any length
        # if self.total_clips_duration < self.min_duration:
        #     errors.append(f"Total clips duration {self.total_clips_duration:.1f}s is less than minimum {self.min_duration}s")
        #
        # if self.total_clips_duration > self.max_duration:
        #     errors.append(f"Total clips duration {self.total_clips_duration:.1f}s exceeds maximum {self.max_duration}s")
        
        for clip in self.clips:
            if not os.path.exists(clip.path):
                errors.append(f"Clip file not found: {clip.path}")
        
        return errors


@dataclass
class CompilationResult:
    """Result of compilation creation"""
    compilation_request: CompilationRequest
    output_path: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    processing_time: float = 0.0
    output_size_mb: float = 0.0
    actual_duration: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def success(self) -> bool:
        """Check if compilation was successful"""
        return self.status == ProcessingStatus.COMPLETED and self.output_path is not None
    
    @property
    def output_exists(self) -> bool:
        """Check if output file exists"""
        return self.output_path is not None and os.path.exists(self.output_path)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get compilation summary"""
        return {
            "compilation_type": self.compilation_request.compilation_type.value,
            "compilation_num": self.compilation_request.compilation_num,
            "clips_count": self.compilation_request.clips_count,
            "status": self.status.value,
            "success": self.success,
            "output_path": self.output_path,
            "output_size_mb": self.output_size_mb,
            "processing_time": self.processing_time,
            "actual_duration": self.actual_duration,
            "error_message": self.error_message
        }


@dataclass
class ProcessingSession:
    """Information about a processing session"""
    session_id: str
    youtube_url: str
    video_id: str
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    
    # Progress tracking
    total_clips: int = 0
    processed_clips: int = 0
    total_compilations: int = 0
    completed_compilations: int = 0
    failed_compilations: int = 0
    
    # Results
    compilation_results: List[CompilationResult] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Get session duration in seconds"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.now() - self.started_at).total_seconds()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.completed_compilations + self.failed_compilations
        return (self.completed_compilations / total * 100) if total > 0 else 0.0
    
    @property
    def clip_progress(self) -> float:
        """Get clip processing progress (0-100)"""
        return (self.processed_clips / self.total_clips * 100) if self.total_clips > 0 else 0.0
    
    @property
    def compilation_progress(self) -> float:
        """Get compilation progress (0-100)"""
        total = self.completed_compilations + self.failed_compilations
        return (total / self.total_compilations * 100) if self.total_compilations > 0 else 0.0
    
    def add_compilation_result(self, result: CompilationResult):
        """Add compilation result to session"""
        self.compilation_results.append(result)
        
        if result.success:
            self.completed_compilations += 1
        else:
            self.failed_compilations += 1
            if result.error_message:
                self.error_messages.append(result.error_message)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get session summary"""
        successful_results = [r for r in self.compilation_results if r.success]
        total_size = sum(r.output_size_mb for r in successful_results)
        total_processing_time = sum(r.processing_time for r in self.compilation_results)
        
        return {
            "session_id": self.session_id,
            "youtube_url": self.youtube_url,
            "video_id": self.video_id,
            "status": self.status.value,
            "duration": self.duration,
            "total_clips": self.total_clips,
            "processed_clips": self.processed_clips,
            "total_compilations": self.total_compilations,
            "completed_compilations": self.completed_compilations,
            "failed_compilations": self.failed_compilations,
            "success_rate": self.success_rate,
            "total_output_size_mb": total_size,
            "total_processing_time": total_processing_time,
            "error_count": len(self.error_messages)
        }


@dataclass
class PerformanceStats:
    """Performance statistics for video processing"""
    start_time: float
    end_time: Optional[float] = None
    
    # Timing breakdown
    download_time: float = 0.0
    processing_time: float = 0.0
    generation_time: float = 0.0
    
    # Processing stats
    total_clips_processed: int = 0
    successful_compilations: int = 0
    failed_compilations: int = 0
    
    # Resource usage
    peak_memory_usage: float = 0.0
    initial_memory_usage: float = 0.0
    average_cpu_usage: float = 0.0
    
    # Output stats
    total_output_size_mb: float = 0.0
    normal_variations: int = 0
    tts_variations: int = 0
    total_variations: int = 0
    
    @property
    def total_time(self) -> float:
        """Get total processing time"""
        if self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.successful_compilations + self.failed_compilations
        return (self.successful_compilations / total * 100) if total > 0 else 0.0
    
    @property
    def average_time_per_compilation(self) -> float:
        """Calculate average time per compilation"""
        return self.generation_time / self.successful_compilations if self.successful_compilations > 0 else 0.0
    
    @property
    def average_size_per_compilation(self) -> float:
        """Calculate average size per compilation"""
        return self.total_output_size_mb / self.successful_compilations if self.successful_compilations > 0 else 0.0
    
    @property
    def memory_usage_increase(self) -> float:
        """Calculate memory usage increase"""
        return self.peak_memory_usage - self.initial_memory_usage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "total_time": self.total_time,
            "download_time": self.download_time,
            "processing_time": self.processing_time,
            "generation_time": self.generation_time,
            "total_clips_processed": self.total_clips_processed,
            "successful_compilations": self.successful_compilations,
            "failed_compilations": self.failed_compilations,
            "success_rate": self.success_rate,
            "peak_memory_usage": self.peak_memory_usage,
            "memory_usage_increase": self.memory_usage_increase,
            "average_cpu_usage": self.average_cpu_usage,
            "total_output_size_mb": self.total_output_size_mb,
            "normal_variations": self.normal_variations,
            "tts_variations": self.tts_variations,
            "total_variations": self.total_variations,
            "average_time_per_compilation": self.average_time_per_compilation,
            "average_size_per_compilation": self.average_size_per_compilation
        }


@dataclass
class CacheEntry:
    """Cache entry for expensive operations"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
    
    def access(self) -> Any:
        """Access the cached value and update statistics"""
        self.last_accessed = datetime.now()
        self.access_count += 1
        return self.value
    
    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds"""
        return (datetime.now() - self.created_at).total_seconds()


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings"""
        return len(self.warnings) > 0


# Utility functions for data models
def create_clip_info_from_dict(data: Dict[str, Any]) -> ClipInfo:
    """Create ClipInfo from dictionary"""
    return ClipInfo(
        id=data.get('id', ''),
        path=data.get('path', ''),
        duration=data.get('duration', 0.0),
        orientation=VideoOrientation(data.get('orientation', 'unknown')),
        source_id=data.get('source_id', ''),
        type=SceneType(data.get('type', 'single')),
        scene_number=data.get('scene_number')
    )


def create_system_resources() -> SystemResources:
    """Create SystemResources with current system information"""
    import psutil
    import torch
    
    # Get basic system info
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Check GPU availability
    gpu_available = torch.cuda.is_available()
    gpu_memory_gb = 0.0
    if gpu_available:
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    
    return SystemResources(
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        available_memory_gb=memory.available / (1024**3),
        disk_space_gb=disk.free / (1024**3),
        gpu_available=gpu_available,
        gpu_memory_gb=gpu_memory_gb
    )


def create_performance_stats() -> PerformanceStats:
    """Create PerformanceStats with current timestamp"""
    import time
    import psutil
    
    return PerformanceStats(
        start_time=time.time(),
        initial_memory_usage=psutil.virtual_memory().percent
    ) 