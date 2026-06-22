"""Small fixed-window rate limiter for the MVP gateway."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit API requests per client IP over a rolling one-minute window."""

    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self.limit = requests_per_minute
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self.limit <= 0 or not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = monotonic()
        cutoff = now - 60

        async with self.lock:
            bucket = self.requests[client]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)
            remaining = self.limit - len(bucket)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def configure_rate_limit(app: FastAPI) -> None:
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_per_minute,
    )
