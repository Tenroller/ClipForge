"""
Pre-flight Validation for Video Processing Jobs.

Validates that all prerequisites are met before starting expensive 
video processing operations. This prevents late failures and provides
early feedback to users about configuration issues.

Checks include:
- System resources (disk space, memory)
- Required dependencies (FFmpeg, yt-dlp)
- API keys for external services
- Input file existence and validity
- GPU availability if requested
"""

import os
import shutil
import psutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..logging_config import get_logger

logger = get_logger("preflight_validation")


class ValidationSeverity(Enum):
    """Severity level for validation issues."""
    ERROR = "error"      # Job cannot proceed
    WARNING = "warning"  # Job can proceed but may have issues
    INFO = "info"        # Informational only


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    passed: bool
    severity: ValidationSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details
        }


@dataclass
class PreflightReport:
    """Complete pre-flight validation report."""
    job_id: str
    workflow: str
    can_proceed: bool
    results: List[ValidationResult] = field(default_factory=list)
    
    @property
    def errors(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationSeverity.ERROR and not r.passed]
    
    @property
    def warnings(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationSeverity.WARNING and not r.passed]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "workflow": self.workflow,
            "can_proceed": self.can_proceed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "results": [r.to_dict() for r in self.results]
        }


class PreflightValidator:
    """
    Pre-flight validator for video processing jobs.
    
    Usage:
        validator = PreflightValidator(job_id, workflow="brainrot")
        report = validator.validate(job_data)
        
        if not report.can_proceed:
            for error in report.errors:
                print(f"Error: {error.message}")
    """
    
    # Minimum requirements
    MIN_DISK_SPACE_GB = 2.0
    MIN_MEMORY_PERCENT_FREE = 10.0
    
    def __init__(self, job_id: str, workflow: str):
        self.job_id = job_id
        self.workflow = workflow
        self.results: List[ValidationResult] = []
    
    def validate(self, job_data: Dict[str, Any]) -> PreflightReport:
        """
        Run all validation checks.
        
        Args:
            job_data: Job configuration data
            
        Returns:
            PreflightReport with all validation results
        """
        logger.info(f"Starting pre-flight validation for job {self.job_id} ({self.workflow})")
        
        self.results = []
        
        # System checks
        self._check_disk_space(job_data.get("output_dir"))
        self._check_memory()
        
        # Dependency checks  
        self._check_ffmpeg()
        self._check_yt_dlp()
        
        # Workflow-specific checks
        if self.workflow in ("brainrot", "compilation"):
            self._check_brainrot_requirements(job_data)
        elif self.workflow == "moneyprinter":
            self._check_moneyprinter_requirements(job_data)
        elif self.workflow == "podcastclips":
            self._check_podcastclips_requirements(job_data)
        
        # GPU check if requested
        if job_data.get("use_gpu", True):
            self._check_gpu()
        
        # Input validation
        self._check_input_sources(job_data)
        
        # Determine if job can proceed
        can_proceed = len([r for r in self.results 
                          if r.severity == ValidationSeverity.ERROR and not r.passed]) == 0
        
        report = PreflightReport(
            job_id=self.job_id,
            workflow=self.workflow,
            can_proceed=can_proceed,
            results=self.results
        )
        
        logger.info(f"Pre-flight validation complete: can_proceed={can_proceed}, "
                   f"errors={len(report.errors)}, warnings={len(report.warnings)}")
        
        return report
    
    def _add_result(self, check_name: str, passed: bool, severity: ValidationSeverity,
                   message: str, details: Optional[Dict[str, Any]] = None):
        """Add a validation result."""
        self.results.append(ValidationResult(
            check_name=check_name,
            passed=passed,
            severity=severity,
            message=message,
            details=details
        ))
    
    def _check_disk_space(self, output_dir: Optional[str] = None):
        """Check available disk space."""
        try:
            path = output_dir or os.getcwd()
            disk = psutil.disk_usage(path)
            free_gb = disk.free / (1024 ** 3)
            
            if free_gb < self.MIN_DISK_SPACE_GB:
                self._add_result(
                    "disk_space", False, ValidationSeverity.ERROR,
                    f"Insufficient disk space: {free_gb:.1f}GB free (need {self.MIN_DISK_SPACE_GB}GB)",
                    {"free_gb": free_gb, "required_gb": self.MIN_DISK_SPACE_GB}
                )
            else:
                self._add_result(
                    "disk_space", True, ValidationSeverity.INFO,
                    f"Disk space OK: {free_gb:.1f}GB free",
                    {"free_gb": free_gb}
                )
        except Exception as e:
            self._add_result(
                "disk_space", False, ValidationSeverity.WARNING,
                f"Could not check disk space: {e}"
            )
    
    def _check_memory(self):
        """Check available memory."""
        try:
            mem = psutil.virtual_memory()
            free_percent = 100 - mem.percent
            
            if free_percent < self.MIN_MEMORY_PERCENT_FREE:
                self._add_result(
                    "memory", False, ValidationSeverity.WARNING,
                    f"Low memory: {free_percent:.1f}% free",
                    {"free_percent": free_percent, "used_percent": mem.percent}
                )
            else:
                self._add_result(
                    "memory", True, ValidationSeverity.INFO,
                    f"Memory OK: {free_percent:.1f}% free",
                    {"free_percent": free_percent}
                )
        except Exception as e:
            self._add_result(
                "memory", False, ValidationSeverity.WARNING,
                f"Could not check memory: {e}"
            )
    
    def _check_ffmpeg(self):
        """Check FFmpeg availability."""
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        
        if not ffmpeg_path:
            self._add_result(
                "ffmpeg", False, ValidationSeverity.ERROR,
                "FFmpeg not found in PATH - video processing will fail",
                {"install_hint": "brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu)"}
            )
        elif not ffprobe_path:
            self._add_result(
                "ffprobe", False, ValidationSeverity.ERROR,
                "FFprobe not found in PATH - video analysis will fail"
            )
        else:
            self._add_result(
                "ffmpeg", True, ValidationSeverity.INFO,
                f"FFmpeg available at {ffmpeg_path}"
            )
    
    def _check_yt_dlp(self):
        """Check yt-dlp availability for YouTube workflows."""
        yt_dlp_path = shutil.which("yt-dlp")
        
        if not yt_dlp_path:
            self._add_result(
                "yt-dlp", False, ValidationSeverity.WARNING,
                "yt-dlp not found - YouTube downloads may fail",
                {"install_hint": "pip install yt-dlp"}
            )
        else:
            self._add_result(
                "yt-dlp", True, ValidationSeverity.INFO,
                f"yt-dlp available at {yt_dlp_path}"
            )
    
    def _check_gpu(self):
        """Check GPU availability."""
        # Always report CPU mode, GPU checks disabled
        self._add_result(
            "gpu", True, ValidationSeverity.INFO,
            "CPU Mode: Processing will run on CPU (GPU disabled project-wide)"
        )
    
    def _check_brainrot_requirements(self, job_data: Dict[str, Any]):
        """Check Brainrot/Compilation specific requirements."""
        youtube_url = job_data.get("youtubeUrl")
        uploaded_path = job_data.get("uploadedVideoPath")
        
        if not youtube_url and not uploaded_path:
            self._add_result(
                "input_source", False, ValidationSeverity.ERROR,
                "No video source provided (need youtubeUrl or uploadedVideoPath)"
            )
    
    def _check_moneyprinter_requirements(self, job_data: Dict[str, Any]):
        """Check MoneyPrinter specific requirements."""
        video_subject = job_data.get("videoSubject")
        if not video_subject:
            self._add_result(
                "video_subject", False, ValidationSeverity.ERROR,
                "No video subject provided"
            )
        
        # Check for Pexels API key (optional but recommended)
        if not os.getenv("PEXELS_API_KEY"):
            self._add_result(
                "pexels_api", False, ValidationSeverity.WARNING,
                "PEXELS_API_KEY not set - will use black background instead of stock footage"
            )
    
    def _check_podcastclips_requirements(self, job_data: Dict[str, Any]):
        """Check PodcastClips specific requirements."""
        youtube_url = job_data.get("youtubeUrl")
        if not youtube_url:
            self._add_result(
                "youtube_url", False, ValidationSeverity.ERROR,
                "No YouTube URL provided for podcast"
            )
        
        # Check for OpenRouter API (for viral moment detection)
        if not os.getenv("OPENROUTER_API_KEY"):
            self._add_result(
                "openrouter_api", False, ValidationSeverity.WARNING,
                "OPENROUTER_API_KEY not set - viral moment detection may not work"
            )
    
    def _check_input_sources(self, job_data: Dict[str, Any]):
        """Validate input files exist."""
        uploaded_path = job_data.get("uploadedVideoPath")
        
        if uploaded_path:
            if os.path.exists(uploaded_path):
                file_size = os.path.getsize(uploaded_path) / (1024 * 1024)
                self._add_result(
                    "input_file", True, ValidationSeverity.INFO,
                    f"Input file exists: {os.path.basename(uploaded_path)} ({file_size:.1f}MB)"
                )
            else:
                self._add_result(
                    "input_file", False, ValidationSeverity.ERROR,
                    f"Input file not found: {uploaded_path}"
                )


def validate_job(job_id: str, workflow: str, job_data: Dict[str, Any]) -> PreflightReport:
    """
    Convenience function to validate a job.
    
    Args:
        job_id: Job identifier
        workflow: Workflow type (brainrot, moneyprinter, podcastclips)
        job_data: Job configuration
        
    Returns:
        PreflightReport with validation results
    """
    validator = PreflightValidator(job_id, workflow)
    return validator.validate(job_data)


def quick_validate(job_data: Dict[str, Any]) -> List[str]:
    """
    Quick validation returning just error messages.
    
    Args:
        job_data: Job configuration
        
    Returns:
        List of error messages (empty if all OK)
    """
    validator = PreflightValidator("quick", job_data.get("workflow", "unknown"))
    report = validator.validate(job_data)
    return [e.message for e in report.errors]
