"""Time utilities."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)
