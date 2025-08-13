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
            log_entry["job_id"] = record.job_id
        
        if hasattr(record, "workflow"):
            log_entry["workflow"] = record.workflow
        
        if hasattr(record, "user_ip"):
            log_entry["user_ip"] = record.user_ip
        
        if hasattr(record, "duration"):
            log_entry["duration"] = record.duration
        
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


def setup_logging() -> logging.Logger:
    """Setup application logging with console and file handlers."""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get root logger
    logger = logging.getLogger("video_generator")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredConsoleFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # JSON handler for structured logging (if enabled)
    if os.getenv("ENABLE_JSON_LOGGING", "").lower() == "true":
        json_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.json.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)
    
    # Error-only handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    return logger


def get_logger(name: str = "video_generator") -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def log_request(logger: logging.Logger, method: str, path: str, 
                status_code: int, duration: float, user_ip: str = "") -> None:
    """Log HTTP request with timing."""
    logger.info(
        f"{method} {path} - {status_code} - {duration:.3f}s",
        extra={
            "user_ip": user_ip,
            "duration": duration,
            "status_code": status_code,
            "method": method,
            "path": path
        }
    )


def log_job_event(logger: logging.Logger, job_id: str, workflow: str, 
                  event: str, **kwargs) -> None:
    """Log job-related events."""
    message = f"Job {job_id} ({workflow}): {event}"
    if kwargs:
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        message += f" - {details}"
    
    logger.info(
        message,
        extra={
            "job_id": job_id,
            "workflow": workflow,
            "event": event,
            **kwargs
        }
    )


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None) -> None:
    """Log errors with context."""
    context = context or {}
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


# Initialize logging when module is imported
main_logger = setup_logging()
main_logger.info("Logging system initialized")
