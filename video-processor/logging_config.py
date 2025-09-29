"""
Enhanced logging configuration for the video generator API.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        import json
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "job_id"):
            log_entry["job_id"] = getattr(record, "job_id")
        
        if hasattr(record, "workflow"):
            log_entry["workflow"] = getattr(record, "workflow")
        if hasattr(record, "user_ip"):
            log_entry["user_ip"] = getattr(record, "user_ip")
            
        if hasattr(record, "duration"):
            log_entry["duration"] = getattr(record, "duration")
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for better readability."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class WindowsSafeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode on Windows."""
    
    def __init__(self, stream=None):
        super().__init__(stream)
        # Force UTF-8 encoding for the stream on Windows
        if sys.platform == "win32":
            try:
                # Try to set UTF-8 encoding for the stream
                if hasattr(self.stream, 'reconfigure'):
                    self.stream.reconfigure(encoding='utf-8', errors='replace')
                elif hasattr(self.stream, 'encoding'):
                    # For older Python versions, we'll handle encoding in emit
                    pass
            except Exception:
                # Fallback to error handling in emit
                pass
    
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            # Fallback: replace problematic characters
            try:
                msg = self.format(record)
                # Replace common problematic Unicode characters
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8')
                if hasattr(self.stream, 'write'):
                    self.stream.write(safe_msg + self.terminator)
                    self.flush()
            except Exception:
                # Last resort: write ASCII-only message
                try:
                    safe_msg = record.getMessage().encode('ascii', errors='replace').decode('ascii')
                    fallback_msg = f"{record.asctime} - {record.name} - {record.levelname} - {safe_msg}\n"
                    self.stream.write(fallback_msg)
                    self.flush()
                except Exception:
                    pass


def setup_logging() -> logging.Logger:
    """Setup unified application logging with console and single comprehensive file handler."""
    # Always use the root logs directory
    root_dir = Path(__file__).resolve().parents[1]
    log_dir = root_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # Get root logger
    logger = logging.getLogger("video_generator")
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels

    # Clear existing handlers
    logger.handlers.clear()

    # Create unified formatter for all logs
    unified_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)8s] %(name)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler with Windows-safe Unicode handling
    if sys.platform == "win32":
        console_handler = WindowsSafeConsoleHandler(sys.stdout)
    else:
        console_handler = logging.StreamHandler(sys.stdout)

    console_handler.setLevel(logging.INFO)  # Console shows INFO and above
    console_formatter = ColoredConsoleFormatter(
        fmt="%(asctime)s [%(levelname)8s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Single unified file handler - captures ALL logs (DEBUG and above)
    unified_file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "video_generator.log",
        maxBytes=50 * 1024 * 1024,  # 50MB - larger for comprehensive logging
        backupCount=10,  # Keep more backups for debugging
        encoding='utf-8'  # Explicitly set UTF-8 encoding
    )
    unified_file_handler.setLevel(logging.DEBUG)  # File captures everything
    unified_file_handler.setFormatter(unified_formatter)
    logger.addHandler(unified_file_handler)

    # JSON handler for structured logging (if enabled) - also unified
    if os.getenv("ENABLE_JSON_LOGGING", "").lower() == "true":
        json_handler = logging.handlers.RotatingFileHandler(
            log_dir / "video_generator.json.log",
            maxBytes=25 * 1024 * 1024,  # 25MB
            backupCount=5,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.DEBUG)  # Capture all structured logs
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

    # Create child loggers for specific components
    _setup_child_loggers(logger, unified_file_handler, unified_formatter)

    return logger


def _setup_child_loggers(parent_logger: logging.Logger, unified_handler: logging.Handler, formatter: logging.Formatter):
    """Setup child loggers for specific components that inherit the unified logging."""
    child_loggers = [
        "video_generator.api",
        "video_generator.generation",
        "video_generator.job_queue",
        "video_generator.database",
        "video_generator.metrics",
        "video_generator.websocket",
        "video_generator.cache",
        "video_generator.ffmpeg",
        "video_generator.ai_videos",
        "video_generator.brainrot"
    ]

    for logger_name in child_loggers:
        child_logger = logging.getLogger(logger_name)
        child_logger.setLevel(logging.DEBUG)
        # Child loggers will inherit handlers from parent, so no need to add handlers explicitly
        # unless we want different formatting or levels


def get_logger(name: str = "video_generator") -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def log_request(logger: logging.Logger, method: str, path: str,
                status_code: int, duration: float, user_ip: str = "",
                request_size: int = 0, response_size: int = 0,
                user_agent: str = "", request_id: str = "") -> None:
    """Log HTTP request with comprehensive details."""
    # Determine log level based on status code
    if status_code >= 500:
        log_level = logging.ERROR
        log_method = logger.error
    elif status_code >= 400:
        log_level = logging.WARNING
        log_method = logger.warning
    else:
        log_level = logging.INFO
        log_method = logger.info

    # Create detailed message
    message = f"HTTP {method} {path} -> {status_code} ({duration:.3f}s)"
    if request_size > 0:
        message += f" | Req: {request_size} bytes"
    if response_size > 0:
        message += f" | Resp: {response_size} bytes"
    if user_ip:
        message += f" | IP: {user_ip}"

    log_method(
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
            "user_agent": user_agent[:200] if user_agent else "",  # Truncate long user agents
            "http_request": True
        }
    )


def log_job_event(logger: logging.Logger, job_id: str, workflow: str,
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
        log_method = logger.error
    elif event in ["completed", "finished"]:
        log_method = logger.info
    elif event in ["started", "queued", "running"]:
        log_method = logger.info
    else:
        log_method = logger.debug

    log_method(
        message,
        extra={
            "job_id": job_id,
            "workflow": workflow,
            "event": event,
            "job_event": True,
            **kwargs
        }
    )


def log_generation_step(logger: logging.Logger, job_id: str, workflow: str,
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
        log_method = logger.error
    elif status in ["completed", "success"]:
        log_method = logger.info
    elif status == "warning":
        log_method = logger.warning
    else:
        log_method = logger.debug

    log_method(
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


def log_api_call(logger: logging.Logger, service: str, endpoint: str,
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
        log_method = logger.error if status_code >= 500 else logger.warning
    elif status_code >= 400:
        log_method = logger.warning
    else:
        log_method = logger.debug

    log_method(
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


def log_file_operation(logger: logging.Logger, operation: str, file_path: str,
                      file_size: int = 0, duration: float = 0.0, **kwargs) -> None:
    """Log file operations with details."""
    message = f"File {operation}: {file_path}"

    if file_size > 0:
        message += f" ({file_size / (1024*1024):.1f}MB)"
    if duration > 0:
        message += f" ({duration:.3f}s)"

    logger.debug(
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


def log_performance_metric(logger: logging.Logger, metric_name: str,
                          value: float, unit: str = "", **tags) -> None:
    """Log performance metrics."""
    message = f"Performance: {metric_name} = {value}"
    if unit:
        message += f" {unit}"

    logger.info(
        message,
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "performance_metric": True,
            **tags
        }
    )


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = {}) -> None:
    """Log errors with context."""
    logger.error(
        f"Error: {str(error)}",
        exc_info=True,
        extra=context
    )


def log_performance_metric(logger: logging.Logger, metric_name: str, 
                          value: float, unit: str = "", **tags) -> None:
    """Log performance metrics."""
    message = f"Metric: {metric_name} = {value}"
    if unit:
        message += f" {unit}"
    
    logger.info(
        message,
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            **tags
        }
    )


# Security-related logging
def log_security_event(logger: logging.Logger, event_type: str, 
                      user_ip: str = "", details: str = "") -> None:
    """Log security-related events."""
    message = f"Security event: {event_type}"
    if details:
        message += f" - {details}"
    
    logger.warning(
        message,
        extra={
            "security_event": event_type,
            "user_ip": user_ip,
            "details": details
        }
    )


# Export initialization function - don't auto-initialize to avoid duplicates in reload mode
def initialize_logging() -> logging.Logger:
    """Initialize logging system and return the main logger."""
    logger = setup_logging()
    logger.info("Logging system initialized")
    return logger

# Keep backwards compatibility - this will be None until initialized
main_logger = None
