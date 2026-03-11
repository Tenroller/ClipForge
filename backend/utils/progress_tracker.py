"""
Enhanced progress tracking system for VideoHelper.

This module provides detailed progress tracking for video generation tasks,
including real-time updates, estimated completion times, and detailed step tracking.
"""

import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from ..logging_config import get_logger

logger = get_logger("progress_tracker")


class ProgressStage(Enum):
    """Progress stages for video generation."""
    INITIALIZING = "initializing"
    SCRIPT_GENERATION = "script_generation"
    SEARCH_TERMS = "search_terms"
    STOCK_DOWNLOAD = "stock_download"
    TTS_GENERATION = "tts_generation"
    SUBTITLE_PROCESSING = "subtitle_processing"
    VIDEO_COMPOSITION = "video_composition"
    FINAL_RENDERING = "final_rendering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressStep:
    """Individual progress step."""
    name: str
    stage: ProgressStage
    started_at: float
    completed_at: Optional[float] = None
    progress: float = 0.0  # 0-100
    message: str = ""
    estimated_duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get duration of this step."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return time.time() - self.started_at

    @property
    def is_completed(self) -> bool:
        """Check if step is completed."""
        return self.completed_at is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'name': self.name,
            'stage': self.stage.value,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'progress': self.progress,
            'message': self.message,
            'duration': self.duration,
            'estimated_duration': self.estimated_duration,
            'metadata': self.metadata
        }


class ProgressTracker:
    """
    Enhanced progress tracker with detailed step tracking and ETA calculation.

    Features:
    - Real-time progress updates
    - Estimated completion time (ETA)
    - Detailed step-by-step tracking
    - Performance metrics
    - Automatic progress calculation
    """

    def __init__(self, job_id: str, total_steps: int = 8):
        self.job_id = job_id
        self.total_steps = total_steps
        self.current_step_index = 0
        self.started_at = time.time()
        self.steps: List[ProgressStep] = []
        self.completed_steps = 0
        self.overall_progress = 0.0
        self.estimated_completion_time: Optional[float] = None
        self.callbacks: List[Callable] = []
        self.lock = threading.Lock()
        
        # Log tracking (for compatibility with video-processor version)
        self.logs: List[Dict[str, Any]] = []

        # Performance tracking
        self.performance_metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'disk_io': []
        }

        logger.info(f"Progress tracker initialized for job {job_id}")

    def start_step(self, step_name: str, stage: ProgressStage,
                  estimated_duration: Optional[float] = None,
                  message: str = "") -> ProgressStep:
        """
        Start a new progress step.

        Args:
            step_name: Name of the step
            stage: Progress stage
            estimated_duration: Estimated duration in seconds
            message: Progress message

        Returns:
            ProgressStep instance
        """
        with self.lock:
            # Mark previous step as completed if it exists
            if self.steps and not self.steps[-1].is_completed:
                self.complete_step(self.steps[-1].name)

            step = ProgressStep(
                name=step_name,
                stage=stage,
                started_at=time.time(),
                estimated_duration=estimated_duration,
                message=message
            )

            self.steps.append(step)
            self.current_step_index = len(self.steps) - 1

            # Update overall progress
            self._update_overall_progress()

            # Notify callbacks
            self._notify_callbacks()

            logger.info(f"Started step '{step_name}' for job {self.job_id}")
            return step

    def update_step_progress(self, step_name: str, progress: float,
                           message: str = "", metadata: Optional[Dict[str, Any]] = None):
        """
        Update progress for a specific step.

        Args:
            step_name: Name of the step to update
            progress: Progress percentage (0-100)
            message: Progress message
            metadata: Additional metadata
        """
        with self.lock:
            for step in self.steps:
                if step.name == step_name and not step.is_completed:
                    step.progress = max(0, min(100, progress))
                    if message:
                        step.message = message
                    if metadata:
                        step.metadata.update(metadata)

                    # Update overall progress
                    self._update_overall_progress()

                    # Notify callbacks
                    self._notify_callbacks()
                    return

            logger.warning(f"Step '{step_name}' not found or already completed")

    def complete_step(self, step_name: str, message: str = "Completed"):
        """
        Mark a step as completed.

        Args:
            step_name: Name of the step to complete
            message: Completion message
        """
        with self.lock:
            for step in self.steps:
                if step.name == step_name and not step.is_completed:
                    step.completed_at = time.time()
                    step.progress = 100.0
                    step.message = message
                    self.completed_steps += 1

                    # Update overall progress
                    self._update_overall_progress()

                    # Calculate ETA
                    self._calculate_eta()

                    # Notify callbacks
                    self._notify_callbacks()

                    logger.info(f"Completed step '{step_name}' for job {self.job_id} in {step.duration:.2f}s")
                    return

    def fail_step(self, step_name: str, error_message: str):
        """
        Mark a step as failed.

        Args:
            step_name: Name of the step that failed
            error_message: Error message
        """
        with self.lock:
            for step in self.steps:
                if step.name == step_name and not step.is_completed:
                    step.completed_at = time.time()
                    step.progress = 0.0
                    step.message = f"Failed: {error_message}"
                    step.metadata['error'] = error_message

                    # Update overall progress
                    self._update_overall_progress()

                    # Notify callbacks
                    self._notify_callbacks()

                    logger.error(f"Step '{step_name}' failed for job {self.job_id}: {error_message}")
                    return

    def get_current_progress(self) -> Dict[str, Any]:
        """
        Get current progress information.

        Returns:
            Dictionary with current progress information
        """
        with self.lock:
            current_step = None
            if self.steps and self.current_step_index < len(self.steps):
                current_step = self.steps[self.current_step_index]

            return {
                'job_id': self.job_id,
                'overall_progress': self.overall_progress,
                'current_step': current_step.to_dict() if current_step else None,
                'completed_steps': self.completed_steps,
                'total_steps': self.total_steps,
                'elapsed_time': time.time() - self.started_at,
                'estimated_completion_time': self.estimated_completion_time,
                'estimated_remaining_time': self._calculate_remaining_time(),
                'steps': [step.to_dict() for step in self.steps],
                'logs': self.logs,
                'performance_metrics': self.performance_metrics
            }

    def add_callback(self, callback: Callable):
        """
        Add a callback function to be called on progress updates.

        Args:
            callback: Function to call with progress updates
        """
        self.callbacks.append(callback)

    def add_log(self, message: str, level: str = "info", source: str = "progress"):
        """
        Add a log message to the tracker.

        Args:
            message: Log message
            level: Log level (info, warning, error, debug)
            source: Source of the log message
        """
        with self.lock:
            log_entry = {
                'timestamp': time.time(),
                'level': level,
                'source': source,
                'message': message
            }
            self.logs.append(log_entry)
            
            # Keep only last 1000 log entries
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]

            # Notify callbacks
            self._notify_callbacks()

    def record_performance_metric(self, metric_type: str, value: Any):
        """
        Record a performance metric.

        Args:
            metric_type: Type of metric (cpu_usage, memory_usage, disk_io)
            value: Metric value
        """
        if metric_type in self.performance_metrics:
            self.performance_metrics[metric_type].append({
                'timestamp': time.time(),
                'value': value
            })

            # Keep only last 100 entries per metric
            if len(self.performance_metrics[metric_type]) > 100:
                self.performance_metrics[metric_type] = self.performance_metrics[metric_type][-100:]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        summary = {}

        for metric_type, measurements in self.performance_metrics.items():
            if measurements:
                values = [m['value'] for m in measurements]
                summary[metric_type] = {
                    'current': values[-1] if values else None,
                    'average': sum(values) / len(values) if values else None,
                    'min': min(values) if values else None,
                    'max': max(values) if values else None,
                    'count': len(values)
                }

        return summary

    def _update_overall_progress(self):
        """Update overall progress based on completed steps and current step progress."""
        if not self.steps:
            self.overall_progress = 0.0
            return

        # Calculate base progress from completed steps
        completed_progress = (self.completed_steps / self.total_steps) * 100

        # Add progress from current step
        current_step = self.steps[-1] if self.steps else None
        if current_step and not current_step.is_completed:
            current_step_progress = (current_step.progress / 100) * (1 / self.total_steps) * 100
            completed_progress += current_step_progress

        self.overall_progress = min(100.0, completed_progress)

    def _calculate_eta(self):
        """Calculate estimated time of completion."""
        if self.completed_steps == 0:
            return

        elapsed_time = time.time() - self.started_at
        avg_time_per_step = elapsed_time / self.completed_steps
        remaining_steps = self.total_steps - self.completed_steps

        self.estimated_completion_time = time.time() + (remaining_steps * avg_time_per_step)

    def _calculate_remaining_time(self) -> Optional[float]:
        """Calculate estimated remaining time."""
        if self.estimated_completion_time:
            remaining = self.estimated_completion_time - time.time()
            return max(0, remaining)
        return None

    def _notify_callbacks(self):
        """Notify all registered callbacks of progress updates."""
        # Build progress info directly since we're already inside the lock context
        # Avoid calling get_current_progress() which would try to acquire the lock again
        current_step = None
        if self.steps and self.current_step_index < len(self.steps):
            current_step = self.steps[self.current_step_index]

        progress_info = {
            'job_id': self.job_id,
            'overall_progress': self.overall_progress,
            'current_step': current_step.to_dict() if current_step else None,
            'completed_steps': self.completed_steps,
            'total_steps': self.total_steps,
            'elapsed_time': time.time() - self.started_at,
            'estimated_completion_time': self.estimated_completion_time,
            'estimated_remaining_time': self._calculate_remaining_time(),
            'steps': [step.to_dict() for step in self.steps],
            'logs': self.logs,
            'performance_metrics': self.performance_metrics
        }

        for callback in self.callbacks:
            try:
                callback(progress_info)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def finalize(self, success: bool = True, error_message: Optional[str] = None):
        """
        Finalize the progress tracking.

        Args:
            success: Whether the job completed successfully
            error_message: Error message if failed
        """
        with self.lock:
            # Mark any incomplete steps as failed or completed
            for step in self.steps:
                if not step.is_completed:
                    if success:
                        self.complete_step(step.name, "Auto-completed")
                    else:
                        self.fail_step(step.name, error_message or "Job failed")

            # Update final progress
            self.overall_progress = 100.0 if success else 0.0

            total_duration = time.time() - self.started_at
            logger.info(f"Job {self.job_id} finalized in {total_duration:.2f}s (success: {success})")

            # Final callback notification
            self._notify_callbacks()


# Global progress trackers
_progress_trackers: Dict[str, ProgressTracker] = {}


def get_progress_tracker(job_id: str) -> ProgressTracker:
    """
    Get or create a progress tracker for a job.

    Args:
        job_id: Job ID

    Returns:
        ProgressTracker instance
    """
    if job_id not in _progress_trackers:
        _progress_trackers[job_id] = ProgressTracker(job_id)

    return _progress_trackers[job_id]


def cleanup_progress_tracker(job_id: str):
    """
    Clean up a progress tracker.

    Args:
        job_id: Job ID to clean up
    """
    if job_id in _progress_trackers:
        del _progress_trackers[job_id]


def get_all_progress() -> Dict[str, Dict[str, Any]]:
    """
    Get progress information for all active jobs.

    Returns:
        Dictionary mapping job IDs to progress information
    """
    return {
        job_id: tracker.get_current_progress()
        for job_id, tracker in _progress_trackers.items()
    }


def cleanup_old_trackers(max_age_seconds: int = 3600):
    """
    Clean up old progress trackers.

    Args:
        max_age_seconds: Maximum age of trackers to keep
    """
    current_time = time.time()
    to_remove = []

    for job_id, tracker in _progress_trackers.items():
        if current_time - tracker.started_at > max_age_seconds:
            to_remove.append(job_id)

    for job_id in to_remove:
        del _progress_trackers[job_id]

    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old progress trackers")


# Convenience functions for common progress tracking patterns
def track_video_generation_progress(job_id: str):
    """
    Set up progress tracking for video generation.

    Args:
        job_id: Job ID
    """
    return get_progress_tracker(job_id)


def create_step_progress_updater(tracker: ProgressTracker, step_name: str):
    """
    Create a progress updater function for a specific step.

    Args:
        tracker: ProgressTracker instance
        step_name: Name of the step to update

    Returns:
        Function that can be called to update step progress
    """
    def update_progress(progress: float, message: str = "", **metadata):
        tracker.update_step_progress(step_name, progress, message, metadata)

    return update_progress
