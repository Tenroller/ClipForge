#!/usr/bin/env python3
"""
Input Validation for TikYou Video Generator

This module provides comprehensive input validation for all components
of the video generation system, using custom exceptions and structured
validation results.
"""

import os
import re
import subprocess
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path

from .exceptions import (
    ValidationError, 
    VideoDownloadError, 
    FileSystemError,
    ConfigurationError,
    ResourceError,
    TikYouException
)
from .data_models import (
    ClipInfo, 
    VideoOrientation, 
    SceneType, 
    ValidationResult,
    SystemResources,
    CompilationRequest,
    ProcessingParams
)
from moviepy import VideoFileClip


class InputValidator:
    """Main input validation class"""
    
    def __init__(self):
        self.youtube_url_patterns = [
            r'^https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'^https?://youtu\.be/([a-zA-Z0-9_-]+)',
            r'^https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'^https?://(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]+)',
        ]
        
        self.valid_video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        self.valid_audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg'}
        
        # File size limits (in bytes)
        self.max_video_file_size = 10 * 1024 * 1024 * 1024  # 10GB
        self.min_video_file_size = 1024  # 1KB
        
        # Duration limits (in seconds)
        self.max_video_duration = 7200  # 2 hours
        self.min_video_duration = 0.1  # 100ms
        self.min_clip_duration = 0.5  # 500ms
        self.max_clip_duration = 300  # 5 minutes
        
        # Compilation limits
        self.max_clips_per_compilation = 100
        self.min_clips_per_compilation = 1
        self.max_compilation_duration = 600  # 10 minutes
        self.min_compilation_duration = 30  # 30 seconds
        
        # System resource limits
        self.max_memory_usage_percent = 95.0
        self.min_disk_space_gb = 1.0
        self.max_cpu_usage_percent = 100.0
    
    def validate_youtube_url(self, url: str) -> ValidationResult:
        """Validate YouTube URL format and accessibility"""
        result = ValidationResult(is_valid=True)
        
        if not url:
            result.add_error("YouTube URL is required")
            return result
        
        if not isinstance(url, str):
            result.add_error("YouTube URL must be a string")
            return result
        
        # Check URL format
        url_match = None
        for pattern in self.youtube_url_patterns:
            url_match = re.match(pattern, url)
            if url_match:
                break
        
        if not url_match:
            result.add_error(f"Invalid YouTube URL format: {url}")
            return result
        
        # Extract video ID
        video_id = url_match.group(1)
        if not video_id:
            result.add_error("Could not extract video ID from URL")
            return result
        
        # Validate video ID format
        if not re.match(r'^[a-zA-Z0-9_-]+$', video_id):
            result.add_error(f"Invalid video ID format: {video_id}")
            return result
        
        if len(video_id) != 11:
            result.add_warning(f"Unusual video ID length: {len(video_id)} characters")
        
        # Check if URL is accessible (basic check)
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                result.add_error("Invalid URL structure")
        except Exception as e:
            result.add_error(f"URL parsing error: {str(e)}")
        
        return result
    
    def validate_video_file(self, file_path: str, check_content: bool = True) -> ValidationResult:
        """Validate video file existence, format, and basic properties"""
        result = ValidationResult(is_valid=True)
        
        if not file_path:
            result.add_error("Video file path is required")
            return result
        
        if not isinstance(file_path, str):
            result.add_error("Video file path must be a string")
            return result
        
        # Check if file exists
        if not os.path.exists(file_path):
            result.add_error(f"Video file not found: {file_path}")
            return result
        
        # Check if it's a file (not directory)
        if not os.path.isfile(file_path):
            result.add_error(f"Path is not a file: {file_path}")
            return result
        
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.valid_video_extensions:
            result.add_warning(f"Unusual video file extension: {file_ext}")
        
        # Check file size
        try:
            file_size = os.path.getsize(file_path)
            if file_size < self.min_video_file_size:
                result.add_error(f"Video file too small: {file_size} bytes")
            elif file_size > self.max_video_file_size:
                result.add_error(f"Video file too large: {file_size} bytes")
        except OSError as e:
            result.add_error(f"Could not check file size: {str(e)}")
        
        # Check file permissions
        if not os.access(file_path, os.R_OK):
            result.add_error(f"Cannot read video file: {file_path}")
        
        # Content validation (optional, requires moviepy)
        if check_content:
            try:
                with VideoFileClip(file_path) as clip:
                    if clip.duration is None:
                        result.add_error("Could not determine video duration")
                    elif clip.duration < self.min_video_duration:
                        result.add_error(f"Video too short: {clip.duration}s")
                    elif clip.duration > self.max_video_duration:
                        result.add_error(f"Video too long: {clip.duration}s")
                    
                    if clip.size is None:
                        result.add_error("Could not determine video dimensions")
                    elif clip.size[0] <= 0 or clip.size[1] <= 0:
                        result.add_error(f"Invalid video dimensions: {clip.size}")
            except ImportError:
                result.add_warning("Could not validate video content (moviepy not available)")
            except Exception as e:
                result.add_error(f"Video content validation failed: {str(e)}")
        
        return result
    
    def validate_clip_info(self, clip_info: ClipInfo) -> ValidationResult:
        """Validate ClipInfo object"""
        result = ValidationResult(is_valid=True)
        
        if not clip_info:
            result.add_error("ClipInfo object is required")
            return result
        
        # Validate ID
        if not clip_info.id:
            result.add_error("Clip ID is required")
        elif not isinstance(clip_info.id, str):
            result.add_error("Clip ID must be a string")
        
        # Validate path
        path_result = self.validate_video_file(clip_info.path, check_content=False)
        if not path_result.is_valid:
            result.errors.extend(path_result.errors)
        result.warnings.extend(path_result.warnings)
        
        # Validate duration
        if clip_info.duration <= 0:
            result.add_error(f"Clip duration must be positive: {clip_info.duration}")
        elif clip_info.duration < self.min_clip_duration:
            result.add_warning(f"Clip duration very short: {clip_info.duration}s")
        elif clip_info.duration > self.max_clip_duration:
            result.add_warning(f"Clip duration very long: {clip_info.duration}s")
        
        # Validate orientation
        if not isinstance(clip_info.orientation, VideoOrientation):
            result.add_error(f"Invalid orientation type: {type(clip_info.orientation)}")
        elif clip_info.orientation == VideoOrientation.UNKNOWN:
            result.add_warning("Clip orientation is unknown")
        
        # Validate source ID
        if not clip_info.source_id:
            result.add_error("Clip source ID is required")
        elif not isinstance(clip_info.source_id, str):
            result.add_error("Clip source ID must be a string")
        
        # Validate type
        if not isinstance(clip_info.type, SceneType):
            result.add_error(f"Invalid scene type: {type(clip_info.type)}")
        
        # Validate time constraints
        if clip_info.start_time is not None and clip_info.end_time is not None:
            if clip_info.start_time >= clip_info.end_time:
                result.add_error(f"Start time {clip_info.start_time} must be less than end time {clip_info.end_time}")
            
            calculated_duration = clip_info.end_time - clip_info.start_time
            if abs(calculated_duration - clip_info.duration) > 0.1:  # 100ms tolerance
                result.add_warning(f"Duration mismatch: stated {clip_info.duration}s, calculated {calculated_duration}s")
        
        # Validate usage count
        if clip_info.usage_count < 0:
            result.add_error(f"Usage count cannot be negative: {clip_info.usage_count}")
        
        return result
    
    def validate_compilation_request(self, request: CompilationRequest) -> ValidationResult:
        """Validate compilation request"""
        result = ValidationResult(is_valid=True)
        
        if not request:
            result.add_error("Compilation request is required")
            return result
        
        # Validate clips
        if not request.clips:
            result.add_error("At least one clip is required")
        elif len(request.clips) > self.max_clips_per_compilation:
            result.add_error(f"Too many clips: {len(request.clips)} (max: {self.max_clips_per_compilation})")
        
        # Validate each clip
        for i, clip in enumerate(request.clips):
            clip_result = self.validate_clip_info(clip)
            if not clip_result.is_valid:
                for error in clip_result.errors:
                    result.add_error(f"Clip {i+1}: {error}")
            for warning in clip_result.warnings:
                result.add_warning(f"Clip {i+1}: {warning}")
        
        # Validate output path
        if not request.output_path:
            result.add_error("Output path is required")
        else:
            output_dir = os.path.dirname(request.output_path)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    result.add_error(f"Cannot create output directory: {str(e)}")
        
        # Validate compilation number
        if request.compilation_num < 1:
            result.add_error(f"Compilation number must be positive: {request.compilation_num}")
        
        # Duration limits removed - compilations can be any length
        # Validate duration constraints (basic sanity checks only)
        if request.min_duration <= 0:
            result.add_error(f"Minimum duration must be positive: {request.min_duration}")

        if request.max_duration <= 0:
            result.add_error(f"Maximum duration must be positive: {request.max_duration}")

        if request.min_duration >= request.max_duration:
            result.add_error(f"Minimum duration {request.min_duration} must be less than maximum {request.max_duration}")

        # Validate target resolution
        if len(request.target_resolution) != 2:
            result.add_error(f"Target resolution must be (width, height): {request.target_resolution}")
        elif request.target_resolution[0] <= 0 or request.target_resolution[1] <= 0:
            result.add_error(f"Invalid target resolution: {request.target_resolution}")

        # Total clips duration validation removed - allow any length compilations
        # total_duration = request.total_clips_duration
        # if total_duration < request.min_duration:
        #     result.add_error(f"Total clips duration {total_duration:.1f}s is less than minimum {request.min_duration}s")
        # elif total_duration > request.max_duration:
        #     result.add_error(f"Total clips duration {total_duration:.1f}s exceeds maximum {request.max_duration}s")
        
        return result
    
    def validate_processing_params(self, params: ProcessingParams) -> ValidationResult:
        """Validate processing parameters"""
        result = ValidationResult(is_valid=True)
        
        if not params:
            result.add_error("Processing parameters are required")
            return result
        
        # Validate worker count
        if params.max_workers <= 0:
            result.add_error(f"Max workers must be positive: {params.max_workers}")
        elif params.max_workers > 16:
            result.add_warning(f"Very high worker count: {params.max_workers}")
        
        # Validate chunk size
        if params.chunk_size <= 0:
            result.add_error(f"Chunk size must be positive: {params.chunk_size}")
        elif params.chunk_size > 50:
            result.add_warning(f"Very large chunk size: {params.chunk_size}")
        
        # Validate bitrate format
        if not re.match(r'^\d+[km]?$', params.bitrate.lower()):
            result.add_error(f"Invalid bitrate format: {params.bitrate}")
        
        # Validate FPS
        if params.fps <= 0:
            result.add_error(f"FPS must be positive: {params.fps}")
        elif params.fps > 120:
            result.add_warning(f"Very high FPS: {params.fps}")
        
        # Validate codec
        valid_codecs = {'libx264', 'h264_nvenc', 'libx265', 'hevc_nvenc'}
        if params.codec not in valid_codecs:
            result.add_warning(f"Unusual codec: {params.codec}")
        
        # Validate audio codec
        valid_audio_codecs = {'aac', 'mp3', 'libmp3lame', 'pcm_s16le'}
        if params.audio_codec not in valid_audio_codecs:
            result.add_warning(f"Unusual audio codec: {params.audio_codec}")
        
        # Validate processing strategy
        valid_strategies = {'parallel', 'sequential'}
        if params.processing_strategy not in valid_strategies:
            result.add_error(f"Invalid processing strategy: {params.processing_strategy}")
        
        return result
    
    def validate_system_resources(self, resources: SystemResources) -> ValidationResult:
        """Validate system resources for processing"""
        result = ValidationResult(is_valid=True)
        
        if not resources:
            result.add_error("System resources information is required")
            return result
        
        # Check memory usage
        if resources.memory_percent > self.max_memory_usage_percent:
            result.add_error(f"Memory usage too high: {resources.memory_percent:.1f}%")
        elif resources.memory_percent > 90:
            result.add_warning(f"High memory usage: {resources.memory_percent:.1f}%")
        
        # Check available memory
        if resources.available_memory_gb < self.min_disk_space_gb:
            result.add_error(f"Insufficient available memory: {resources.available_memory_gb:.1f}GB")
        elif resources.available_memory_gb < 2.0:
            result.add_warning(f"Low available memory: {resources.available_memory_gb:.1f}GB")
        
        # Check disk space
        if resources.disk_space_gb < self.min_disk_space_gb:
            result.add_error(f"Insufficient disk space: {resources.disk_space_gb:.1f}GB")
        elif resources.disk_space_gb < 5.0:
            result.add_warning(f"Low disk space: {resources.disk_space_gb:.1f}GB")
        
        # Check CPU usage
        if resources.cpu_percent > self.max_cpu_usage_percent:
            result.add_error(f"CPU usage too high: {resources.cpu_percent:.1f}%")
        elif resources.cpu_percent > 90:
            result.add_warning(f"High CPU usage: {resources.cpu_percent:.1f}%")
        
        return result
    
    def validate_directory_structure(self, base_path: str) -> ValidationResult:
        """Validate directory structure for video processing"""
        result = ValidationResult(is_valid=True)
        
        if not base_path:
            result.add_error("Base path is required")
            return result
        
        # Check if base path exists
        if not os.path.exists(base_path):
            try:
                os.makedirs(base_path, exist_ok=True)
                result.add_warning(f"Created base directory: {base_path}")
            except OSError as e:
                result.add_error(f"Cannot create base directory: {str(e)}")
                return result
        
        # Check if it's a directory
        if not os.path.isdir(base_path):
            result.add_error(f"Base path is not a directory: {base_path}")
            return result
        
        # Check permissions
        if not os.access(base_path, os.W_OK):
            result.add_error(f"No write permission for directory: {base_path}")
        
        if not os.access(base_path, os.R_OK):
            result.add_error(f"No read permission for directory: {base_path}")
        
        # Check required subdirectories
        required_subdirs = ['final_videos', 'temp_vertical', 'debug_frames']
        for subdir in required_subdirs:
            subdir_path = os.path.join(base_path, subdir)
            if not os.path.exists(subdir_path):
                try:
                    os.makedirs(subdir_path, exist_ok=True)
                    result.add_warning(f"Created subdirectory: {subdir_path}")
                except OSError as e:
                    result.add_error(f"Cannot create subdirectory {subdir}: {str(e)}")
        
        return result
    
    def validate_numeric_range(self, value: Union[int, float], min_val: Union[int, float], 
                             max_val: Union[int, float], name: str) -> ValidationResult:
        """Validate numeric value within a range"""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, (int, float)):
            result.add_error(f"{name} must be a number")
            return result
        
        if value < min_val:
            result.add_error(f"{name} {value} is below minimum {min_val}")
        elif value > max_val:
            result.add_error(f"{name} {value} is above maximum {max_val}")
        
        return result
    
    def validate_string_not_empty(self, value: str, name: str) -> ValidationResult:
        """Validate string is not empty"""
        result = ValidationResult(is_valid=True)
        
        if not value:
            result.add_error(f"{name} is required")
        elif not isinstance(value, str):
            result.add_error(f"{name} must be a string")
        elif not value.strip():
            result.add_error(f"{name} cannot be empty")
        
        return result
    
    def validate_file_extension(self, file_path: str, valid_extensions: set) -> ValidationResult:
        """Validate file extension"""
        result = ValidationResult(is_valid=True)
        
        if not file_path:
            result.add_error("File path is required")
            return result
        
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in valid_extensions:
            result.add_error(f"Invalid file extension: {file_ext}, expected one of {valid_extensions}")
        
        return result
    
    def validate_configuration(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration dictionary"""
        result = ValidationResult(is_valid=True)
        
        if not config:
            result.add_error("Configuration is required")
            return result
        
        # Validate required configuration keys
        required_keys = ['output_dir', 'max_workers', 'memory_threshold']
        for key in required_keys:
            if key not in config:
                result.add_error(f"Missing required configuration key: {key}")
        
        # Validate specific configuration values
        if 'max_workers' in config:
            worker_result = self.validate_numeric_range(
                config['max_workers'], 1, 16, 'max_workers'
            )
            if not worker_result.is_valid:
                result.errors.extend(worker_result.errors)
        
        if 'memory_threshold' in config:
            memory_result = self.validate_numeric_range(
                config['memory_threshold'], 0.1, 1.0, 'memory_threshold'
            )
            if not memory_result.is_valid:
                result.errors.extend(memory_result.errors)
        
        if 'output_dir' in config:
            dir_result = self.validate_directory_structure(config['output_dir'])
            if not dir_result.is_valid:
                result.errors.extend(dir_result.errors)
            result.warnings.extend(dir_result.warnings)
        
        return result


# Convenience functions
def validate_youtube_url(url: str) -> ValidationResult:
    """Convenience function to validate YouTube URL"""
    validator = InputValidator()
    return validator.validate_youtube_url(url)


def validate_video_file(file_path: str) -> ValidationResult:
    """Convenience function to validate video file"""
    validator = InputValidator()
    return validator.validate_video_file(file_path)


def validate_clip_info(clip_info: ClipInfo) -> ValidationResult:
    """Convenience function to validate ClipInfo"""
    validator = InputValidator()
    return validator.validate_clip_info(clip_info)


def validate_compilation_request(request: CompilationRequest) -> ValidationResult:
    """Convenience function to validate compilation request"""
    validator = InputValidator()
    return validator.validate_compilation_request(request)


def validate_system_resources(resources: SystemResources) -> ValidationResult:
    """Convenience function to validate system resources"""
    validator = InputValidator()
    return validator.validate_system_resources(resources)


def ensure_valid_or_raise(validation_result: ValidationResult, 
                         exception_class: type = ValidationError) -> None:
    """Raise exception if validation result is not valid"""
    if not validation_result.is_valid:
        error_message = "; ".join(validation_result.errors)
        raise exception_class(
            field_name="validation",
            field_value=error_message,
            constraint="All validation checks must pass"
        )


def log_validation_warnings(validation_result: ValidationResult, logger) -> None:
    """Log validation warnings using the provided logger"""
    if validation_result.has_warnings and logger:
        for warning in validation_result.warnings:
            logger.warning(f"Validation warning: {warning}")


# Advanced validation functions
def validate_batch_clips(clips: List[ClipInfo]) -> Dict[str, ValidationResult]:
    """Validate a batch of clips and return results"""
    validator = InputValidator()
    results = {}
    
    for i, clip in enumerate(clips):
        clip_id = clip.id if clip and hasattr(clip, 'id') else f"clip_{i}"
        results[clip_id] = validator.validate_clip_info(clip)
    
    return results


def validate_processing_environment() -> ValidationResult:
    """Validate the entire processing environment"""
    validator = InputValidator()
    result = ValidationResult(is_valid=True)
    
    # Check system resources
    from .data_models import create_system_resources
    resources = create_system_resources()
    resource_result = validator.validate_system_resources(resources)
    
    if not resource_result.is_valid:
        result.errors.extend(resource_result.errors)
    result.warnings.extend(resource_result.warnings)
    
    # Check directory structure
    dir_result = validator.validate_directory_structure('.')
    if not dir_result.is_valid:
        result.errors.extend(dir_result.errors)
    result.warnings.extend(dir_result.warnings)
    
    # Check required tools (ffmpeg, etc.)
    try:
        # Check for FFMPEG_PATH environment variable first
        ffmpeg_cmd = os.getenv('FFMPEG_PATH', 'ffmpeg')
        subprocess.run([ffmpeg_cmd, '-version'], 
                      capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        result.add_error("FFmpeg is not available or not working properly")
    except Exception as e:
        result.add_warning(f"Could not verify FFmpeg: {str(e)}")
    
    return result 