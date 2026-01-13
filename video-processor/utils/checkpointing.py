"""
Pipeline Checkpointing for Video Processing Workflows.

Enables resume capability for long-running video processing jobs by saving
intermediate state after each major processing step. This protects against
loss of work when jobs fail for transient reasons (network, memory, etc.).

Built on top of the artifacts module for consistent persistence.

Checkpoint Philosophy:
1. Only checkpoint after expensive/time-consuming operations
2. Each checkpoint must contain enough state to resume from that point
3. Checkpoints are immutable once written (append-only)
4. Resume logic checks for existing checkpoints before starting steps
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, TypeVar, Generic
from enum import Enum

from .artifacts import (
    persist_artifact,
    load_artifact,
    has_artifact,
    _job_artifacts_root,
)
from ..logging_config import get_logger

logger = get_logger("checkpointing")


class PipelineStep(Enum):
    """Standard pipeline steps for video processing workflows."""
    # Common steps
    DOWNLOAD = "download"
    
    # MoneyPrinter steps
    SCRIPT_GENERATION = "script_generation"
    TTS_GENERATION = "tts_generation"
    STOCK_SEARCH = "stock_search"
    VIDEO_COMPOSITION = "video_composition"
    
    # Brainrot/Compilation steps
    SCENE_DETECTION = "scene_detection"
    CLIP_EXTRACTION = "clip_extraction"
    CLIP_SCORING = "clip_scoring"
    CLIP_PROCESSING = "clip_processing"
    COMPILATION_GENERATION = "compilation_generation"
    
    # PodcastClips steps
    TRANSCRIPTION = "transcription"
    SPEAKER_DIARIZATION = "speaker_diarization"
    VIRAL_DETECTION = "viral_detection"
    FACE_TRACKING = "face_tracking"
    CLIP_GENERATION = "clip_generation"


@dataclass
class Checkpoint:
    """A checkpoint representing the completion of a pipeline step."""
    job_id: str
    step: str
    status: str  # "completed", "in_progress", "failed"
    data: Dict[str, Any]  # Step-specific data needed for resume
    created_at: str
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Checkpoint":
        return cls(**d)


class CheckpointManager:
    """
    Manages pipeline checkpoints for resumable video processing.
    
    Usage:
        # Create checkpoint manager for a job
        checkpointer = CheckpointManager(job_id)
        
        # Check if step already completed (for resume)
        if checkpointer.is_step_completed(PipelineStep.SCENE_DETECTION):
            scenes = checkpointer.load_step_data(PipelineStep.SCENE_DETECTION)
        else:
            # Perform expensive operation
            with checkpointer.step_context(PipelineStep.SCENE_DETECTION) as ctx:
                scenes = detect_scenes(video_path)
                ctx.save({"scenes": scenes, "video_path": video_path})
    """
    
    CHECKPOINT_KEY = "checkpoint"
    
    def __init__(self, job_id: str, workflow: Optional[str] = None):
        self.job_id = job_id
        self.workflow = workflow
        self._step_times: Dict[str, float] = {}
        logger.info(f"CheckpointManager initialized for job {job_id}")
    
    def _step_name(self, step: PipelineStep | str) -> str:
        """Get step name from enum or string."""
        return step.value if isinstance(step, PipelineStep) else step
    
    def is_step_completed(self, step: PipelineStep | str) -> bool:
        """Check if a step has a completed checkpoint."""
        step_name = self._step_name(step)
        checkpoint = self.load_checkpoint(step_name)
        if checkpoint and checkpoint.status == "completed":
            logger.info(f"Step '{step_name}' found completed checkpoint, can skip")
            return True
        return False
    
    def load_checkpoint(self, step: PipelineStep | str) -> Optional[Checkpoint]:
        """Load a checkpoint for a step if it exists."""
        step_name = self._step_name(step)
        data = load_artifact(self.job_id, step_name, self.CHECKPOINT_KEY)
        if data:
            try:
                return Checkpoint.from_dict(data)
            except (TypeError, KeyError) as e:
                logger.warning(f"Corrupt checkpoint for step '{step_name}': {e}")
        return None
    
    def load_step_data(self, step: PipelineStep | str) -> Optional[Dict[str, Any]]:
        """Load just the data portion of a completed checkpoint."""
        checkpoint = self.load_checkpoint(step)
        if checkpoint and checkpoint.status == "completed":
            return checkpoint.data
        return None
    
    def save_checkpoint(
        self,
        step: PipelineStep | str,
        data: Dict[str, Any],
        status: str = "completed",
        duration_seconds: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """Save a checkpoint for a step."""
        step_name = self._step_name(step)
        
        checkpoint = Checkpoint(
            job_id=self.job_id,
            step=step_name,
            status=status,
            data=data,
            created_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration_seconds,
            metadata=metadata or {}
        )
        
        persist_artifact(
            self.job_id,
            step_name,
            self.CHECKPOINT_KEY,
            checkpoint.to_dict(),
            force=True  # Allow overwriting for status updates
        )
        
        logger.info(f"Checkpoint saved for step '{step_name}' (status={status}, duration={duration_seconds:.1f}s)")
        return checkpoint
    
    def mark_step_started(self, step: PipelineStep | str) -> float:
        """Mark a step as started and return start time."""
        step_name = self._step_name(step)
        start_time = time.time()
        self._step_times[step_name] = start_time
        
        self.save_checkpoint(
            step_name,
            data={},
            status="in_progress",
            duration_seconds=0.0,
            metadata={"started_at": datetime.now(timezone.utc).isoformat()}
        )
        
        return start_time
    
    def mark_step_completed(
        self,
        step: PipelineStep | str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """Mark a step as completed with its output data."""
        step_name = self._step_name(step)
        
        # Calculate duration
        start_time = self._step_times.get(step_name, time.time())
        duration = time.time() - start_time
        
        return self.save_checkpoint(
            step_name,
            data=data,
            status="completed",
            duration_seconds=duration,
            metadata=metadata
        )
    
    def mark_step_failed(
        self,
        step: PipelineStep | str,
        error: str,
        partial_data: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """Mark a step as failed with error info."""
        step_name = self._step_name(step)
        
        start_time = self._step_times.get(step_name, time.time())
        duration = time.time() - start_time
        
        return self.save_checkpoint(
            step_name,
            data=partial_data or {},
            status="failed",
            duration_seconds=duration,
            metadata={"error": error}
        )
    
    def step_context(self, step: PipelineStep | str):
        """Context manager for a step that auto-saves on success."""
        return StepContext(self, step)
    
    def get_resume_point(self) -> Optional[str]:
        """
        Determine where to resume a job from.
        
        Returns the name of the first uncompleted step, or None if all done.
        """
        # Load manifest to see all attempted steps
        manifest = self._load_job_manifest()
        
        if not manifest:
            return None
        
        # Find the last completed step and the first incomplete
        completed_steps = []
        for step_name, artifacts in manifest.get("artifacts", {}).items():
            if self.CHECKPOINT_KEY in artifacts:
                checkpoint = self.load_checkpoint(step_name)
                if checkpoint:
                    if checkpoint.status == "completed":
                        completed_steps.append((step_name, checkpoint.created_at))
                    elif checkpoint.status in ("failed", "in_progress"):
                        # Resume from this failed/incomplete step
                        return step_name
        
        # All completed or no checkpoints
        return None
    
    def _load_job_manifest(self) -> Dict[str, Any]:
        """Load the job manifest."""
        from .artifacts import load_manifest
        return load_manifest(self.job_id)
    
    def get_all_checkpoints(self) -> List[Checkpoint]:
        """Get all checkpoints for this job."""
        manifest = self._load_job_manifest()
        checkpoints = []
        
        for step_name in manifest.get("artifacts", {}).keys():
            checkpoint = self.load_checkpoint(step_name)
            if checkpoint:
                checkpoints.append(checkpoint)
        
        return sorted(checkpoints, key=lambda c: c.created_at)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of checkpoint status for this job."""
        checkpoints = self.get_all_checkpoints()
        
        return {
            "job_id": self.job_id,
            "workflow": self.workflow,
            "total_checkpoints": len(checkpoints),
            "completed_steps": [c.step for c in checkpoints if c.status == "completed"],
            "failed_steps": [c.step for c in checkpoints if c.status == "failed"],
            "in_progress_steps": [c.step for c in checkpoints if c.status == "in_progress"],
            "total_duration_seconds": sum(c.duration_seconds for c in checkpoints),
            "resume_point": self.get_resume_point()
        }


class StepContext:
    """Context manager for a pipeline step with automatic checkpointing."""
    
    def __init__(self, manager: CheckpointManager, step: PipelineStep | str):
        self.manager = manager
        self.step = step
        self._data: Optional[Dict[str, Any]] = None
        self._metadata: Optional[Dict[str, Any]] = None
    
    def __enter__(self) -> "StepContext":
        self.manager.mark_step_started(self.step)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Step failed
            self.manager.mark_step_failed(
                self.step,
                error=str(exc_val),
                partial_data=self._data
            )
            return False  # Re-raise exception
        
        if self._data is not None:
            # Step completed with data
            self.manager.mark_step_completed(
                self.step,
                data=self._data,
                metadata=self._metadata
            )
        
        return False
    
    def save(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        """Save step data (called before exiting context)."""
        self._data = data
        self._metadata = metadata


# Convenience functions
def get_checkpoint_manager(job_id: str, workflow: Optional[str] = None) -> CheckpointManager:
    """Get a checkpoint manager for a job."""
    return CheckpointManager(job_id, workflow)


def can_resume_step(job_id: str, step: PipelineStep | str) -> bool:
    """Check if a step has resumable data."""
    manager = CheckpointManager(job_id)
    return manager.is_step_completed(step)


def load_step_checkpoint(job_id: str, step: PipelineStep | str) -> Optional[Dict[str, Any]]:
    """Load checkpoint data for a step."""
    manager = CheckpointManager(job_id)
    return manager.load_step_data(step)
