"""
CSRF protection middleware using the Double Submit Cookie pattern.

On non-safe HTTP methods (POST, PUT, DELETE, PATCH), the middleware verifies
that the ``X-CSRF-Token`` request header matches the ``csrf_token`` cookie.
If the values are missing or do not match, a 403 response is returned.

Exceptions:
- Requests authenticated via ``X-API-Key`` header (machine-to-machine).
- The login endpoint (``/api/auth/login``), which cannot have a token yet.
- Safe (read-only) methods: GET, HEAD, OPTIONS.

The middleware also ensures that every response carries a ``csrf_token``
cookie so the frontend can read it and attach the header on subsequent
mutating requests.
"""

import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


# HTTP methods considered safe (read-only) – no CSRF check needed.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths that are exempt from CSRF validation.
_EXEMPT_PATHS = frozenset({"/api/auth/login", "/api/auth/csrf-token", "/api/jobs/callback"})

# Length in bytes for the random token (32 bytes → 64 hex chars).
_TOKEN_BYTES = 32


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double Submit Cookie CSRF protection."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip CSRF entirely in test environments
        if os.getenv("TESTING") == "1":
            return await call_next(request)

        # --- 1. Decide whether this request requires a CSRF check ----------
        needs_check = (
            request.method not in _SAFE_METHODS
            and request.url.path not in _EXEMPT_PATHS
            and not request.headers.get("x-api-key")
        )

        if needs_check:
            cookie_token = request.cookies.get("csrf_token")
            header_token = request.headers.get("x-csrf-token")

            if not cookie_token or not header_token or cookie_token != header_token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )

        # --- 2. Process the actual request ---------------------------------
        response: Response = await call_next(request)

        # --- 3. Ensure the csrf_token cookie exists on the response --------
        if "csrf_token" not in request.cookies:
            is_debug = os.getenv("DEBUG_MODE", "").lower() in ("true", "1")
            response.set_cookie(
                key="csrf_token",
                value=secrets.token_hex(_TOKEN_BYTES),
                httponly=False,       # Frontend JS must be able to read it
                secure=not is_debug,
                samesite="none" if not is_debug else "lax",
                path="/",
            )

        return response
