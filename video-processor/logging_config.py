"""
Enhanced logging configuration for the video generator API using Loguru.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


# === Integration with standard logging (for libraries that use it) ===
def intercept_standard_logging():
    """
    Intercept standard library logging and redirect to Loguru.

    Call this if you have third-party libraries using standard logging
    and want their logs to appear in Loguru format.
    """
    import logging
    import inspect

    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = inspect.currentframe(), 0
            while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Replace all standard logging handlers with Loguru interceptor
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Suppress some noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)


def setup_logging() -> logger:
    """
    Setup unified application logging with Loguru.

    Configures:
    - Console output with colors (INFO and above)
    - File output with rotation and retention (DEBUG and above)
    - JSON structured logging (optional via env var)
    - Interception of standard logging (automatically enabled)

    Returns:
        Configured loguru logger instance
    """
    # Determine log directory (project root / logs)
    root_dir = Path(__file__).resolve().parents[1]
    log_dir = root_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # Remove default handler to avoid duplicates
    logger.remove()

    # === Console Handler (Colored) ===
    # Shows INFO and above with colors and simplified format
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # === Intercept standard library logging ===
    # This must be done BEFORE any libraries that use standard logging are initialized
    intercept_standard_logging()

    # === File Handler (Detailed, Rotating) ===
    # Captures everything (DEBUG and above) with full details
    logger.add(
        log_dir / "video_generator.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="50 MB",  # Rotate when file reaches 50MB
        retention="10 days",  # Keep logs for 10 days
        compression="zip",  # Compress rotated logs
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        enqueue=True  # Thread-safe, async writing
    )

    # === JSON Structured Logging (Optional) ===
    # Enable with: export ENABLE_JSON_LOGGING=true
    if os.getenv("ENABLE_JSON_LOGGING", "").lower() == "true":
        logger.add(
            log_dir / "video_generator.json.log",
            level="INFO",
            format="{message}",
            serialize=True,  # Output as JSON
            rotation="25 MB",
            retention="7 days",
            compression="zip",
            encoding="utf-8",
            enqueue=True
        )

    # === Error-Only Handler ===
    # Separate file for errors and above for quick debugging
    logger.add(
        log_dir / "errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",  # Keep error logs longer
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )

    # Log successful initialization
    logger.info("Loguru logging system initialized")
    logger.debug(f"Log directory: {log_dir}")

    return logger


def get_logger(name: str = "video_generator") -> logger:
    """
    Get a logger with the specified name.

    Note: With Loguru, the logger is global, but you can use .bind()
    to add contextual information.

    Args:
        name: Logger name (used for contextual binding)

    Returns:
        Loguru logger with name context
    """
    return logger.bind(name=name)


def log_request(log: logger, method: str, path: str,
                status_code: int, duration: float, user_ip: str = "",
                request_size: int = 0, response_size: int = 0,
                user_agent: str = "", request_id: str = "") -> None:
    """Log HTTP request with comprehensive details."""
    # Determine log level based on status code
    if status_code >= 500:
        log_func = log.error
    elif status_code >= 400:
        log_func = log.warning
    else:
        log_func = log.info

    # Create detailed message
    message = f"HTTP {method} {path} -> {status_code} ({duration:.3f}s)"
    if request_size > 0:
        message += f" | Req: {request_size} bytes"
    if response_size > 0:
        message += f" | Resp: {response_size} bytes"
    if user_ip:
        message += f" | IP: {user_ip}"

    # Log with extra context
    log_func(
        message,
        extra={
            "request_id": request_id,
            "user_ip": user_ip,
            "duration": duration,
            "status_code": status_code,
            "method": method,
            "path": path,
            "request_size": request_size,
            "response_size": response_size,
            "user_agent": user_agent[:200] if user_agent else "",
            "http_request": True
        }
    )


def log_job_event(log: logger, job_id: str, workflow: str,
                  event: str, **kwargs) -> None:
    """Log job-related events with enhanced details."""
    message = f"Job {job_id} ({workflow}): {event}"

    # Add important details to message
    important_details = []
    if "status" in kwargs:
        important_details.append(f"status={kwargs['status']}")
    if "progress" in kwargs:
        important_details.append(f"progress={kwargs['progress']}%")
    if "duration" in kwargs:
        important_details.append(f"duration={kwargs['duration']:.2f}s")
    if "error" in kwargs:
        important_details.append(f"error={kwargs['error']}")

    if important_details:
        message += f" [{', '.join(important_details)}]"

    # Determine log level based on event type
    if event in ["failed", "error", "cancelled"]:
        log_func = log.error
    elif event in ["completed", "finished"]:
        log_func = log.info
    elif event in ["started", "queued", "running"]:
        log_func = log.info
    else:
        log_func = log.debug

    log_func(
        message,
        extra={
            "job_id": job_id,
            "workflow": workflow,
            "event": event,
            "job_event": True,
            **kwargs
        }
    )


def log_generation_step(log: logger, job_id: str, workflow: str,
                       step: str, status: str = "started", **kwargs) -> None:
    """Log video generation process steps with detailed information."""
    message = f"Generation {job_id} ({workflow}): Step '{step}' - {status}"

    # Add step-specific details
    step_details = []
    if "duration" in kwargs:
        step_details.append(f"{kwargs['duration']:.2f}s")
    if "file_count" in kwargs:
        step_details.append(f"{kwargs['file_count']} files")
    if "file_size" in kwargs:
        step_details.append(f"{kwargs['file_size'] / (1024*1024):.1f}MB")
    if "model" in kwargs:
        step_details.append(f"model={kwargs['model']}")
    if "voice" in kwargs:
        step_details.append(f"voice={kwargs['voice']}")

    if step_details:
        message += f" ({', '.join(step_details)})"

    # Determine log level
    if status in ["failed", "error"]:
        log_func = log.error
    elif status in ["completed", "success"]:
        log_func = log.info
    elif status == "warning":
        log_func = log.warning
    else:
        log_func = log.debug

    log_func(
        message,
        extra={
            "job_id": job_id,
            "workflow": workflow,
            "step": step,
            "step_status": status,
            "generation_step": True,
            **kwargs
        }
    )


def log_api_call(log: logger, service: str, endpoint: str,
                 method: str = "GET", status_code: int = 0,
                 duration: float = 0.0, **kwargs) -> None:
    """Log external API calls."""
    message = f"API Call: {service} {method} {endpoint}"

    if status_code > 0:
        message += f" -> {status_code}"
    if duration > 0:
        message += f" ({duration:.3f}s)"

    # Determine log level based on status
    if status_code >= 500 or status_code == 0:
        log_func = log.error if status_code >= 500 else log.warning
    elif status_code >= 400:
        log_func = log.warning
    else:
        log_func = log.debug

    log_func(
        message,
        extra={
            "api_service": service,
            "api_endpoint": endpoint,
            "api_method": method,
            "api_status_code": status_code,
            "api_duration": duration,
            "external_api": True,
            **kwargs
        }
    )


def log_file_operation(log: logger, operation: str, file_path: str,
                      file_size: int = 0, duration: float = 0.0, **kwargs) -> None:
    """Log file operations with details."""
    message = f"File {operation}: {file_path}"

    if file_size > 0:
        message += f" ({file_size / (1024*1024):.1f}MB)"
    if duration > 0:
        message += f" ({duration:.3f}s)"

    log.debug(
        message,
        extra={
            "file_operation": operation,
            "file_path": file_path,
            "file_size": file_size,
            "operation_duration": duration,
            "file_operation_event": True,
            **kwargs
        }
    )


def log_performance_metric(log: logger, metric_name: str,
                          value: float, unit: str = "", **tags) -> None:
    """Log performance metrics."""
    message = f"Performance: {metric_name} = {value}"
    if unit:
        message += f" {unit}"

    log.info(
        message,
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "performance_metric": True,
            **tags
        }
    )


def log_error(log: logger, error: Exception, context: Dict[str, Any] = {}) -> None:
    """Log errors with context and full traceback."""
    log.opt(exception=True).error(
        f"Error: {str(error)}",
        extra=context
    )


def log_security_event(log: logger, event_type: str,
                      user_ip: str = "", details: str = "") -> None:
    """Log security-related events."""
    message = f"Security event: {event_type}"
    if details:
        message += f" - {details}"

    log.warning(
        message,
        extra={
            "security_event": event_type,
            "user_ip": user_ip,
            "details": details
        }
    )


def initialize_logging() -> logger:
    """
    Initialize logging system and return the main logger.

    This is the main entry point for setting up logging.
    """
    configured_logger = setup_logging()
    logger.info("Logging system initialized")
    return configured_logger


# Backwards compatibility: expose logger as main_logger
main_logger = logger
