"""
Standardized error handling utilities for VideoHelper.

This module provides consistent error handling patterns, custom exceptions,
and error response formatting throughout the application.
"""

import traceback
import json
from typing import Dict, Any, Optional, Union, List
from enum import Enum
try:
    from ..logging_config import get_logger
except ImportError:
    # Fallback for when running from backend directory
    from logging_config import get_logger

logger = get_logger("error_handling")


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VideoHelperError(Exception):
    """Base exception class for VideoHelper errors."""

    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR",
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity.value,
            'details': self.details,
            'cause': str(self.cause) if self.cause else None
        }


class ValidationError(VideoHelperError):
    """Validation error for invalid input data."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None, **kwargs):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            severity=ErrorSeverity.LOW,
            details={
                'field': field,
                'value': str(value) if value is not None else None,
                **kwargs
            }
        )


class ConfigurationError(VideoHelperError):
    """Configuration-related error."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            severity=ErrorSeverity.HIGH,
            details={
                'config_key': config_key,
                **kwargs
            }
        )


class ProcessingError(VideoHelperError):
    """Video/audio processing error."""

    def __init__(self, message: str, step: Optional[str] = None,
                 file_path: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="PROCESSING_ERROR",
            severity=ErrorSeverity.MEDIUM,
            details={
                'step': step,
                'file_path': file_path,
                **kwargs
            }
        )


class ExternalServiceError(VideoHelperError):
    """Error from external services (APIs, databases, etc.)."""

    def __init__(self, message: str, service: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            severity=ErrorSeverity.HIGH,
            details={
                'service': service,
                'status_code': status_code,
                **kwargs
            }
        )


class ResourceError(VideoHelperError):
    """Resource-related error (memory, disk space, etc.)."""

    def __init__(self, message: str, resource_type: str, **kwargs):
        super().__init__(
            message=message,
            error_code="RESOURCE_ERROR",
            severity=ErrorSeverity.HIGH,
            details={
                'resource_type': resource_type,
                **kwargs
            }
        )


def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None,
                log_error: bool = True) -> Dict[str, Any]:
    """
    Handle an exception and return standardized error response.

    Args:
        error: The exception that occurred
        context: Additional context information
        log_error: Whether to log the error

    Returns:
        Standardized error response dictionary
    """
    context = context or {}

    # Handle VideoHelperError subclasses
    if isinstance(error, VideoHelperError):
        error_dict = error.to_dict()

        if log_error:
            logger.log(
                _get_log_level(error.severity),
                f"VideoHelperError: {error.message}",
                extra={
                    'error_code': error.error_code,
                    'severity': error.severity.value,
                    'context': context,
                    'traceback': traceback.format_exc()
                }
            )

        return {
            'success': False,
            'error': error_dict,
            'context': context
        }

    # Handle standard exceptions
    error_code = _classify_error(error)
    severity = _get_error_severity(error)

    error_dict = {
        'error_code': error_code,
        'message': str(error),
        'severity': severity.value,
        'details': {},
        'cause': None
    }

    if log_error:
        logger.log(
            _get_log_level(severity),
            f"Unhandled error: {str(error)}",
            extra={
                'error_type': type(error).__name__,
                'context': context,
                'traceback': traceback.format_exc()
            }
        )

    return {
        'success': False,
        'error': error_dict,
        'context': context
    }


def _classify_error(error: Exception) -> str:
    """Classify an exception to determine its error code."""
    error_type = type(error).__name__

    # Common error classifications
    error_mappings = {
        'FileNotFoundError': 'FILE_NOT_FOUND',
        'PermissionError': 'PERMISSION_DENIED',
        'OSError': 'OS_ERROR',
        'ValueError': 'INVALID_VALUE',
        'TypeError': 'INVALID_TYPE',
        'KeyError': 'MISSING_KEY',
        'IndexError': 'INDEX_OUT_OF_RANGE',
        'AttributeError': 'ATTRIBUTE_ERROR',
        'ImportError': 'IMPORT_ERROR',
        'ModuleNotFoundError': 'MODULE_NOT_FOUND',
        'ConnectionError': 'CONNECTION_ERROR',
        'TimeoutError': 'TIMEOUT_ERROR',
        'HTTPError': 'HTTP_ERROR',
        'URLError': 'URL_ERROR',
        'sqlite3.Error': 'DATABASE_ERROR',
        'psycopg2.Error': 'DATABASE_ERROR',
        'pymongo.errors.PyMongoError': 'DATABASE_ERROR',
    }

    return error_mappings.get(error_type, 'UNKNOWN_ERROR')


def _get_error_severity(error: Exception) -> ErrorSeverity:
    """Determine the severity of an error."""
    error_type = type(error).__name__

    # High severity errors
    if error_type in ['SystemExit', 'KeyboardInterrupt', 'MemoryError']:
        return ErrorSeverity.CRITICAL

    # Medium severity errors
    if error_type in ['FileNotFoundError', 'PermissionError', 'OSError',
                     'ConnectionError', 'TimeoutError', 'sqlite3.Error']:
        return ErrorSeverity.HIGH

    # Low severity errors (most common)
    return ErrorSeverity.MEDIUM


def _get_log_level(severity: ErrorSeverity) -> str:
    """Convert error severity to Loguru logging level."""
    severity_mapping = {
        ErrorSeverity.LOW: "INFO",
        ErrorSeverity.MEDIUM: "WARNING", 
        ErrorSeverity.HIGH: "ERROR",
        ErrorSeverity.CRITICAL: "CRITICAL",
    }

    return severity_mapping.get(severity, "ERROR")  # Default to ERROR


def create_error_response(error: Exception, status_code: int = 500,
                         context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a standardized error response for API endpoints.

    Args:
        error: The exception that occurred
        status_code: HTTP status code
        context: Additional context

    Returns:
        Error response dictionary
    """
    error_info = handle_error(error, context, log_error=True)

    return {
        'status': 'error',
        'message': error_info['error']['message'],
        'error_code': error_info['error']['error_code'],
        'details': error_info['error']['details'],
        'status_code': status_code
    }


def safe_execute(func, *args, default_return=None, **kwargs):
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        default_return: Default return value on error
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Safe execution failed for {func.__name__}: {e}")
        return default_return


async def safe_execute_async(func, *args, default_return=None, **kwargs):
    """
    Safely execute an async function with error handling.

    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        default_return: Default return value on error
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return on error
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Safe async execution failed for {func.__name__}: {e}")
        return default_return


def validate_and_raise(condition: bool, message: str, error_class=ValidationError, **kwargs):
    """
    Validate a condition and raise an error if it fails.

    Args:
        condition: Condition to check
        message: Error message if condition fails
        error_class: Error class to raise
        **kwargs: Additional arguments for the error

    Raises:
        error_class: If condition is False
    """
    if not condition:
        raise error_class(message, **kwargs)


def log_error_with_context(error: Exception, context: Dict[str, Any],
                          level: str = "error"):
    """
    Log an error with additional context information.

    Args:
        error: The exception that occurred
        context: Context information
        level: Log level (debug, info, warning, error, critical)
    """
    log_func = getattr(logger, level, logger.error)

    log_func(
        f"Error with context: {str(error)}",
        extra={
            'error_type': type(error).__name__,
            'context': context,
            'traceback': traceback.format_exc()
        }
    )


def create_retry_wrapper(max_retries: int = 3, delay: float = 1.0,
                        backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Create a retry wrapper for functions.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


# Error response formatters for different output types
def format_error_for_api(error: Exception, status_code: int = 500) -> Dict[str, Any]:
    """Format error for JSON API response."""
    return create_error_response(error, status_code)


def format_error_for_cli(error: Exception) -> str:
    """Format error for CLI output."""
    if isinstance(error, VideoHelperError):
        return f"Error [{error.error_code}]: {error.message}"
    else:
        return f"Error: {str(error)}"


def format_error_for_log(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format error for logging purposes."""
    error_info = handle_error(error, context, log_error=False)
    error_info['timestamp'] = __import__('datetime').datetime.now().isoformat()
    return error_info


# Global error handler for unexpected errors
def setup_global_error_handler():
    """Setup global error handler for unhandled exceptions."""
    import sys

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Global exception handler."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Unhandled exception: {error_msg}")

        # Call the default handler
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = global_exception_handler


# Initialize global error handler
try:
    setup_global_error_handler()
except Exception as e:
    logger.error(f"Failed to setup global error handler: {e}")
