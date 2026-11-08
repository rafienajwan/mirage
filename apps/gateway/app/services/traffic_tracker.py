"""Rolling per-source request counts used by the risk feature pipeline."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from time import monotonic


class TrafficTracker:
    def __init__(
        self,
        window_seconds: int = 60,
        max_sources: int = 10_000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.clock = clock
        self.window_seconds = window_seconds
        self.max_sources = max_sources
        self.requests: dict[str, deque[float]] = {}
        self.lock = asyncio.Lock()
        self._last_sweep = clock()

    def _prune_sources(self, cutoff: float) -> None:
        stale = [
            source
            for source, bucket in self.requests.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for source in stale:
            del self.requests[source]

    async def record(self, source: str) -> int:
        now = self.clock()
        cutoff = now - self.window_seconds
        async with self.lock:
            # Sweep idle sources at most once per window (amortized O(1)).
            if now - self._last_sweep >= self.window_seconds:
                self._prune_sources(cutoff)
                self._last_sweep = now
            bucket = self.requests.get(source)
            if bucket is None:
                while len(self.requests) >= self.max_sources:
                    del self.requests[next(iter(self.requests))]
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
