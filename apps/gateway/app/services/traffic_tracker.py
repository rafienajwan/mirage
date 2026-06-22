"""Rolling per-source request counts used by the risk feature pipeline."""

from __future__ import annotations

import asyncio
from collections import deque
from time import monotonic


class TrafficTracker:
    def __init__(self, window_seconds: int = 60, max_sources: int = 10_000) -> None:
        self.window_seconds = window_seconds
        self.max_sources = max_sources
        self.requests: dict[str, deque[float]] = {}
        self.lock = asyncio.Lock()

    def _prune_sources(self, cutoff: float) -> None:
        stale = [
            source
            for source, bucket in self.requests.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for source in stale:
            del self.requests[source]

        while len(self.requests) >= self.max_sources:
            del self.requests[next(iter(self.requests))]

    async def record(self, source: str) -> int:
        now = monotonic()
        cutoff = now - self.window_seconds
        async with self.lock:
            bucket = self.requests.get(source)
            if bucket is None:
                self._prune_sources(cutoff)
                bucket = deque()
                self.requests[source] = bucket
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            bucket.append(now)
            return len(bucket)

    async def clear(self) -> None:
        async with self.lock:
            self.requests.clear()


traffic_tracker = TrafficTracker()
