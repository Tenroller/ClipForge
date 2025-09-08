#!/usr/bin/env python3
"""
Custom Exceptions for TikYou Video Generator

This module defines custom exception classes for better error handling
and debugging throughout the video generation system.
"""

from typing import Optional, Dict, Any, List


class TikYouException(Exception):
    """Base exception for all TikYou Video Generator errors"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        super().__init__(self.message)
    
    def __str__(self):
        context_str = ""
        if self.context:
            context_items = [f"{k}={v}" for k, v in self.context.items()]
            context_str = f" | Context: {', '.join(context_items)}"
        
        return f"[{self.error_code}] {self.message}{context_str}"


class VideoDownloadError(TikYouException):
    """Exception raised when video download fails"""
    
    def __init__(self, url: str, reason: str, error_code: Optional[str] = None):
        context = {"url": url, "reason": reason}
        super().__init__(f"Failed to download video from {url}: {reason}", error_code, context)


class VideoProcessingError(TikYouException):
    """Exception raised when video processing fails"""
    
    def __init__(self, video_path: str, operation: str, reason: str, 
                 error_code: Optional[str] = None):
        context = {"video_path": video_path, "operation": operation, "reason": reason}
        super().__init__(f"Failed to process video {video_path} during {operation}: {reason}", 
                        error_code, context)


class SceneDetectionError(TikYouException):
    """Exception raised when scene detection fails"""
    
    def __init__(self, video_path: str, sensitivity: float, reason: str,
                 error_code: Optional[str] = None):
        context = {"video_path": video_path, "sensitivity": sensitivity, "reason": reason}
        super().__init__(f"Scene detection failed for {video_path}: {reason}", 
                        error_code, context)


class EncodingError(TikYouException):
    """Exception raised when video encoding fails"""
    
    def __init__(self, input_path: str, output_path: str, codec: str, 
                 reason: str, error_code: Optional[str] = None):
        context = {
            "input_path": input_path,
            "output_path": output_path,
            "codec": codec,
            "reason": reason
        }
        super().__init__(f"Encoding failed for {input_path} -> {output_path} with codec {codec}: {reason}", 
                        error_code, context)


class ClipProcessingError(TikYouException):
    """Exception raised when individual clip processing fails"""
    
    def __init__(self, clip_path: str, clip_duration: float, 
                 operation: str, reason: str, error_code: Optional[str] = None):
        context = {
            "clip_path": clip_path,
            "clip_duration": clip_duration,
            "operation": operation,
            "reason": reason
        }
        super().__init__(f"Clip processing failed for {clip_path} during {operation}: {reason}", 
                        error_code, context)


class CompilationError(TikYouException):
    """Exception raised when compilation creation fails"""
    
    def __init__(self, compilation_id: str, clips_count: int, 
                 total_duration: float, reason: str, error_code: Optional[str] = None):
        context = {
            "compilation_id": compilation_id,
            "clips_count": clips_count,
            "total_duration": total_duration,
            "reason": reason
        }
        super().__init__(f"Compilation {compilation_id} creation failed: {reason}", 
                        error_code, context)


class ResourceError(TikYouException):
    """Exception raised when system resources are insufficient"""
    
    def __init__(self, resource_type: str, current_usage: float, 
                 threshold: float, reason: str, error_code: Optional[str] = None):
        context = {
            "resource_type": resource_type,
            "current_usage": current_usage,
            "threshold": threshold,
            "reason": reason
        }
        super().__init__(f"Insufficient {resource_type} resources: {reason}", 
                        error_code, context)


class ValidationError(TikYouException):
    """Exception raised when input validation fails"""
    
    def __init__(self, field_name: str, field_value: Any, 
                 constraint: str, error_code: Optional[str] = None):
        context = {
            "field_name": field_name,
            "field_value": field_value,
            "constraint": constraint
        }
        super().__init__(f"Validation failed for {field_name}: {constraint}", 
                        error_code, context)


class ConfigurationError(TikYouException):
    """Exception raised when configuration is invalid"""
    
    def __init__(self, config_section: str, config_key: str, 
                 reason: str, error_code: Optional[str] = None):
        context = {
            "config_section": config_section,
            "config_key": config_key,
            "reason": reason
        }
        super().__init__(f"Configuration error in {config_section}.{config_key}: {reason}", 
                        error_code, context)


class FFmpegError(TikYouException):
    """Exception raised when FFmpeg operations fail"""
    
    def __init__(self, command: str, return_code: int, 
                 stderr: str, error_code: Optional[str] = None):
        context = {
            "command": command,
            "return_code": return_code,
            "stderr": stderr
        }
        super().__init__(f"FFmpeg command failed with return code {return_code}: {stderr}", 
                        error_code, context)


class FileSystemError(TikYouException):
    """Exception raised when file system operations fail"""
    
    def __init__(self, operation: str, file_path: str, 
                 reason: str, error_code: Optional[str] = None):
        context = {
            "operation": operation,
            "file_path": file_path,
            "reason": reason
        }
        super().__init__(f"File system operation '{operation}' failed for {file_path}: {reason}", 
                        error_code, context)


class TTSError(TikYouException):
    """Exception raised when Text-to-Speech generation fails"""
    
    def __init__(self, text: str, voice: str, reason: str, 
                 error_code: Optional[str] = None):
        context = {
            "text": text,
            "voice": voice,
            "reason": reason
        }
        super().__init__(f"TTS generation failed for voice '{voice}': {reason}", 
                        error_code, context)


class TitleGenerationError(TikYouException):
    """Exception raised when title generation fails"""
    
    def __init__(self, context: str, style: str, reason: str, 
                 error_code: Optional[str] = None):
        context_dict = {
            "context": context,
            "style": style,
            "reason": reason
        }
        super().__init__(f"Title generation failed for style '{style}': {reason}", 
                        error_code, context_dict)


class MemoryError(TikYouException):
    """Exception raised when memory usage exceeds limits"""
    
    def __init__(self, current_usage: float, threshold: float, 
                 operation: str, error_code: Optional[str] = None):
        context = {
            "current_usage": current_usage,
            "threshold": threshold,
            "operation": operation
        }
        super().__init__(f"Memory usage {current_usage:.1f}% exceeds threshold {threshold:.1f}% during {operation}", 
                        error_code, context)


class DiskSpaceError(TikYouException):
    """Exception raised when disk space is insufficient"""
    
    def __init__(self, available_space_gb: float, required_space_gb: float, 
                 operation: str, error_code: Optional[str] = None):
        context = {
            "available_space_gb": available_space_gb,
            "required_space_gb": required_space_gb,
            "operation": operation
        }
        super().__init__(f"Insufficient disk space: {available_space_gb:.1f}GB available, {required_space_gb:.1f}GB required for {operation}", 
                        error_code, context)


class OrientationError(TikYouException):
    """Exception raised when video orientation detection fails"""
    
    def __init__(self, video_path: str, detected_orientation: str, 
                 reason: str, error_code: Optional[str] = None):
        context = {
            "video_path": video_path,
            "detected_orientation": detected_orientation,
            "reason": reason
        }
        super().__init__(f"Orientation detection failed for {video_path}: {reason}", 
                        error_code, context)


class ConcatenationError(TikYouException):
    """Exception raised when video concatenation fails"""
    
    def __init__(self, clips_paths: List[str], total_duration: float, 
                 reason: str, error_code: Optional[str] = None):
        context = {
            "clips_count": len(clips_paths),
            "clips_paths": clips_paths,
            "total_duration": total_duration,
            "reason": reason
        }
        super().__init__(f"Concatenation of {len(clips_paths)} clips failed: {reason}", 
                        error_code, context)


class OutputValidationError(TikYouException):
    """Exception raised when output file validation fails"""
    
    def __init__(self, output_path: str, expected_duration: float, 
                 actual_size: int, reason: str, error_code: Optional[str] = None):
        context = {
            "output_path": output_path,
            "expected_duration": expected_duration,
            "actual_size": actual_size,
            "reason": reason
        }
        super().__init__(f"Output validation failed for {output_path}: {reason}", 
                        error_code, context)


class RetryableError(TikYouException):
    """Exception that can be retried with exponential backoff"""
    
    def __init__(self, message: str, max_retries: int = 3, 
                 retry_delay: float = 1.0, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.current_attempt = 0
        
        if context is None:
            context = {}
        context.update({
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "current_attempt": self.current_attempt
        })
        
        super().__init__(message, error_code, context)
    
    def increment_attempt(self):
        """Increment the current attempt counter"""
        self.current_attempt += 1
        self.context["current_attempt"] = self.current_attempt
    
    def can_retry(self) -> bool:
        """Check if the error can be retried"""
        return self.current_attempt < self.max_retries
    
    def get_retry_delay(self) -> float:
        """Get the delay for the next retry (with exponential backoff)"""
        return self.retry_delay * (2 ** self.current_attempt)


class CriticalError(TikYouException):
    """Exception for critical errors that should stop all processing"""
    
    def __init__(self, message: str, system_state: Dict[str, Any], 
                 error_code: Optional[str] = None):
        context = {"system_state": system_state}
        super().__init__(f"CRITICAL ERROR: {message}", error_code, context)


# Exception hierarchy for different error categories
class InputError(TikYouException):
    """Base class for input-related errors"""
    pass


class ProcessingError(TikYouException):
    """Base class for processing-related errors"""
    pass


class OutputError(TikYouException):
    """Base class for output-related errors"""
    pass


class SystemError(TikYouException):
    """Base class for system-related errors"""
    pass


# Utility functions for error handling
def handle_retryable_error(func, max_retries: int = 3, retry_delay: float = 1.0, 
                          logger=None):
    """Decorator to handle retryable errors with exponential backoff"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except RetryableError as e:
                e.increment_attempt()
                if e.can_retry():
                    delay = e.get_retry_delay()
                    if logger:
                        logger.warning(f"Retrying {func.__name__} in {delay:.1f}s (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay)
                else:
                    if logger:
                        logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                    raise
            except Exception as e:
                if logger:
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                raise
        
        # This should never be reached
        raise TikYouException(f"Unexpected error in retry handler for {func.__name__}")
    
    return wrapper


def create_error_context(locals_dict: Dict[str, Any], 
                        exclude_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create an error context dictionary from local variables"""
    if exclude_keys is None:
        exclude_keys = ['self', '__class__', 'args', 'kwargs']
    
    context = {}
    for key, value in locals_dict.items():
        if key not in exclude_keys:
            try:
                # Try to convert to string to ensure it's serializable
                context[key] = str(value)
            except:
                context[key] = f"<{type(value).__name__}>"
    
    return context


def validate_file_exists(file_path: str, operation: str = "operation") -> None:
    """Validate that a file exists, raise FileSystemError if not"""
    import os
    
    if not os.path.exists(file_path):
        raise FileSystemError(
            operation=operation,
            file_path=file_path,
            reason="File does not exist"
        )
    
    if not os.path.isfile(file_path):
        raise FileSystemError(
            operation=operation,
            file_path=file_path,
            reason="Path is not a file"
        )


def validate_directory_exists(dir_path: str, operation: str = "operation") -> None:
    """Validate that a directory exists, raise FileSystemError if not"""
    import os
    
    if not os.path.exists(dir_path):
        raise FileSystemError(
            operation=operation,
            file_path=dir_path,
            reason="Directory does not exist"
        )
    
    if not os.path.isdir(dir_path):
        raise FileSystemError(
            operation=operation,
            file_path=dir_path,
            reason="Path is not a directory"
        )


def validate_video_file(video_path: str, min_duration: float = 0.1) -> None:
    """Validate that a video file is valid"""
    validate_file_exists(video_path, "video validation")
    
    # Check file size
    import os
    file_size = os.path.getsize(video_path)
    if file_size < 1024:  # Less than 1KB
        raise ValidationError(
            field_name="video_file_size",
            field_value=file_size,
            constraint="File size must be at least 1KB"
        )
    
    # TODO: Add more video-specific validation (format, duration, etc.)
    # This would require moviepy or ffprobe integration 