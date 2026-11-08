"""Small sliding-window rate limiter for the MVP gateway."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from collections.abc import Callable
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core import config
from app.core.client_ip import client_ip

WINDOW_SECONDS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit API requests per client over a rolling one-minute window.

    State is bounded: emptied buckets are deleted, and at most ``max_clients``
    keys are tracked (expired keys go first, then the least recently used).
    """

    def __init__(
        self,
        app,
        requests_per_minute: int,
        max_clients: int = 10000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        super().__init__(app)
        self.limit = requests_per_minute
        self.max_clients = max(1, max_clients)
        self.clock = clock
        self.requests: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = asyncio.Lock()
        self._last_sweep = clock()

    def _purge_expired(self, cutoff: float) -> None:
        expired = [key for key, bucket in self.requests.items() if bucket[-1] <= cutoff]
        for key in expired:
            del self.requests[key]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self.limit <= 0 or not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        client = client_ip(request)
        now = self.clock()
        cutoff = now - WINDOW_SECONDS

        async with self.lock:
            # Sweep idle clients at most once per window (amortized O(1)).
            if now - self._last_sweep >= WINDOW_SECONDS:
                self._purge_expired(cutoff)
                self._last_sweep = now
            bucket = self.requests.get(client)
            if bucket is not None:
                self.requests.move_to_end(client)
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
            if bucket is None or not bucket:
                self.requests.pop(client, None)
                if len(self.requests) >= self.max_clients:
                    self._purge_expired(cutoff)
                while len(self.requests) >= self.max_clients:
                    self.requests.popitem(last=False)
                bucket = deque()
                self.requests[client] = bucket
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
        requests_per_minute=config.settings.rate_limit_per_minute,
        max_clients=config.settings.rate_limit_max_clients,
    )
