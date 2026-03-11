"""
Rate limiting middleware using an in-process sliding window counter.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-IP rate limiter using a sliding window.
    Set `requests_per_minute=0` to disable.
    """

    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if self.requests_per_minute <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = 60.0  # 1 minute

        # Prune expired entries
        hits = self._hits[client_ip]
        cutoff = now - window
        self._hits[client_ip] = hits = [t for t in hits if t > cutoff]

        if len(hits) >= self.requests_per_minute:
            retry_after = int(hits[0] - cutoff) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
