"""
Enhanced logging configuration for the video generator API using Loguru.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger


def json_serializer(record):
    """Serialize log record to JSON format for structured logging."""
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "process": record["process"].id,
        "thread": record["thread"].id,
    }
    
    # Add extra fields from record
    extra = record.get("extra", {})
    for key, value in extra.items():
        log_entry[key] = value
    
    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback
        }
    
    return json.dumps(log_entry)


def setup_logging() -> None:
    """Setup unified application logging with Loguru."""
    # Remove default handler
    logger.remove()

    # Console handler with colors
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan> - "
        "<level>{message}</level>"
    )

    # Add console handler (INFO level and above)
    logger.add(
        sys.stdout,
        format=console_format,
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # File logging (disabled in production via LOG_TO_FILE=false)
    if os.getenv("LOG_TO_FILE", "true").lower() != "false":
        root_dir = Path(__file__).resolve().parents[1]
        log_dir = root_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        # Unified file handler - captures ALL logs (DEBUG and above)
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} [{level: <8}] {name} - "
            "{module}:{function}:{line} - {message}"
        )

        logger.add(
            str(log_dir / "video_generator.log"),
            format=file_format,
            level="DEBUG",
            rotation="50 MB",
            retention=10,
            compression="zip",
            backtrace=True,
            diagnose=True,
            encoding="utf-8"
        )

        # JSON handler for structured logging (if enabled)
        if os.getenv("ENABLE_JSON_LOGGING", "").lower() == "true":
            logger.add(
                str(log_dir / "video_generator.json.log"),
                format=json_serializer,
                level="DEBUG",
                rotation="25 MB",
                retention=5,
                compression="zip",
                serialize=False,
                encoding="utf-8"
            )


def get_logger(name: str = "video_generator"):
    """Get a logger with the specified name."""
    return logger.bind(name=name)


def log_request(logger_instance, method: str, path: str,
                status_code: int, duration: float, user_ip: str = "",
                request_size: int = 0, response_size: int = 0,
                user_agent: str = "", request_id: str = "") -> None:
    """Log HTTP request with comprehensive details."""
    # Create detailed message
    message = f"HTTP {method} {path} -> {status_code} ({duration:.3f}s)"
    if request_size > 0:
        message += f" | Req: {request_size} bytes"
    if response_size > 0:
        message += f" | Resp: {response_size} bytes"
    if user_ip:
        message += f" | IP: {user_ip}"

    # Create context with extra data
    context = {
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

    # Determine log level based on status code
    if status_code >= 500:
        logger_instance.bind(**context).error(message)
    elif status_code >= 400:
        logger_instance.bind(**context).warning(message)
    else:
        logger_instance.bind(**context).info(message)


def log_job_event(logger_instance, job_id: str, workflow: str,
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

    # Create context
    context = {
        "job_id": job_id,
        "workflow": workflow,
        "event": event,
        "job_event": True,
        **kwargs
    }

    # Determine log level based on event type
    if event in ["failed", "error", "cancelled"]:
        logger_instance.bind(**context).error(message)
    elif event in ["completed", "finished"]:
        logger_instance.bind(**context).info(message)
    elif event in ["started", "queued", "running"]:
        logger_instance.bind(**context).info(message)
    else:
        logger_instance.bind(**context).debug(message)


def log_generation_step(logger_instance, job_id: str, workflow: str,
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

    # Create context
    context = {
        "job_id": job_id,
        "workflow": workflow,
        "step": step,
        "step_status": status,
        "generation_step": True,
        **kwargs
    }

    # Determine log level
    if status in ["failed", "error"]:
        logger_instance.bind(**context).error(message)
    elif status in ["completed", "success"]:
        logger_instance.bind(**context).info(message)
    elif status == "warning":
        logger_instance.bind(**context).warning(message)
    else:
        logger_instance.bind(**context).debug(message)


def log_api_call(logger_instance, service: str, endpoint: str,
                 method: str = "GET", status_code: int = 0,
                 duration: float = 0.0, **kwargs) -> None:
    """Log external API calls."""
    message = f"API Call: {service} {method} {endpoint}"

    if status_code > 0:
        message += f" -> {status_code}"
    if duration > 0:
        message += f" ({duration:.3f}s)"

    # Create context
    context = {
        "api_service": service,
        "api_endpoint": endpoint,
        "api_method": method,
        "api_status_code": status_code,
        "api_duration": duration,
        "external_api": True,
        **kwargs
    }

    # Determine log level based on status
    if status_code >= 500 or status_code == 0:
        log_method = logger_instance.bind(**context).error if status_code >= 500 else logger_instance.bind(**context).warning
    elif status_code >= 400:
        log_method = logger_instance.bind(**context).warning
    else:
        log_method = logger_instance.bind(**context).debug

    log_method(message)


def log_file_operation(logger_instance, operation: str, file_path: str,
                      file_size: int = 0, duration: float = 0.0, **kwargs) -> None:
    """Log file operations with details."""
    message = f"File {operation}: {file_path}"

    if file_size > 0:
        message += f" ({file_size / (1024*1024):.1f}MB)"
    if duration > 0:
        message += f" ({duration:.3f}s)"

    context = {
        "file_operation": operation,
        "file_path": file_path,
        "file_size": file_size,
        "operation_duration": duration,
        "file_operation_event": True,
        **kwargs
    }

    logger_instance.bind(**context).debug(message)


def log_error(logger_instance, error: Exception, context: Dict[str, Any] = {}) -> None:
    """Log errors with context."""
    logger_instance.bind(**context).opt(exception=True).error(f"Error: {str(error)}")


def log_performance_metric(logger_instance, metric_name: str, 
                          value: float, unit: str = "", **tags) -> None:
    """Log performance metrics."""
    message = f"Metric: {metric_name} = {value}"
    if unit:
        message += f" {unit}"
    
    context = {
        "metric_name": metric_name,
        "metric_value": value,
        "metric_unit": unit,
        **tags
    }
    
    logger_instance.bind(**context).info(message)


def log_security_event(logger_instance, event_type: str, 
                      user_ip: str = "", details: str = "") -> None:
    """Log security-related events."""
    message = f"Security event: {event_type}"
    if details:
        message += f" - {details}"
    
    context = {
        "security_event": event_type,
        "user_ip": user_ip,
        "details": details
    }
    
    logger_instance.bind(**context).warning(message)


def initialize_logging():
    """Initialize logging system and return the main logger."""
    setup_logging()
    main_logger = get_logger("video_generator")
    main_logger.info("Logging system initialized with Loguru")
    return main_logger


# Global logger instance for backwards compatibility
main_logger = None