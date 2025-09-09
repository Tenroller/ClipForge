"""
Logging middleware for comprehensive request/response monitoring.
"""

import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..logging_config import get_logger, log_request, log_security_event
from ..metrics import record_request_metrics
from ..utils.error_handling import handle_error

logger = get_logger("middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging and monitoring."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]  # Short request ID for tracking

        # Extract request details
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = str(request.url.path)
        query_params = str(request.url.query)
        user_agent = request.headers.get("User-Agent", "")
        content_length = request.headers.get("Content-Length", "0")

        # Log request start with detailed info
        logger.debug(
            f"REQUEST START: {request_id} | {method} {path} | IP: {client_ip} | UA: {user_agent[:50]}...",
            extra={
                "request_id": request_id,
                "http_request": True,
                "request_start": True
            }
        )

        response = None
        status_code = 500
        response_size = 0

        try:
            response = await call_next(request)
            status_code = response.status_code
            # Try to get response size if available
            if hasattr(response, 'headers') and 'Content-Length' in response.headers:
                try:
                    response_size = int(response.headers['Content-Length'])
                except (ValueError, TypeError):
                    response_size = 0
        except Exception as e:
            # Use standardized error handling
            error_info = handle_error(e, {
                "path": path,
                "method": method,
                "client_ip": client_ip,
                "endpoint": "middleware",
                "request_id": request_id
            })
            raise
        finally:
            # Log request completion with comprehensive details
            duration = time.time() - start_time
            request_size = int(content_length) if content_length.isdigit() else 0

            log_request(
                logger, method, path, status_code, duration, client_ip,
                request_size=request_size, response_size=response_size,
                user_agent=user_agent, request_id=request_id
            )

            # Record metrics
            record_request_metrics(method, path, status_code, duration)

            # Log slow requests with performance details
            if duration > 5.0:
                logger.warning(
                    f"SLOW REQUEST: {request_id} | {method} {path} | {duration:.2f}s",
                    extra={
                        "request_id": request_id,
                        "slow_request": True,
                        "duration": duration,
                        "performance_issue": True
                    }
                )

            # Enhanced security event logging
            if status_code == 401:
                log_security_event(
                    logger, "authentication_failed", client_ip,
                    details=f"{method} {path} - Request ID: {request_id}"
                )
            elif status_code == 429:
                log_security_event(
                    logger, "rate_limit_exceeded", client_ip,
                    details=f"{method} {path} - Request ID: {request_id}"
                )
            elif status_code >= 500:
                logger.error(
                    f"SERVER ERROR: {request_id} | {method} {path} | {status_code}",
                    extra={
                        "request_id": request_id,
                        "server_error": True,
                        "status_code": status_code
                    }
                )

        return response
