"""In-memory storage for events, alerts, and decoy state.

This module provides a simple, replaceable store. In future iterations it can
be swapped for PostgreSQL, Redis, or any persistent backend.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.dashboard import AlertRecord, AlertSeverity
from app.schemas.event import EventRecord


class MemoryStore:
    """Thread-safe-ish in-memory store (single-process demo only)."""

    def __init__(self) -> None:
        self.events: list[EventRecord] = []
        self.alerts: list[AlertRecord] = []
        self._alert_counter: int = 0

    # ── Events ─────────────────────────────────────────────────

    def add_event(self, event: EventRecord) -> None:
        self.events.append(event)

    def get_recent_events(self, limit: int = 50) -> list[EventRecord]:
        return list(reversed(self.events[-limit:]))

    # ── Alerts ─────────────────────────────────────────────────

    def add_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        recommended_action: str,
    ) -> None:
        self._alert_counter += 1
        alert = AlertRecord(
            alert_id=f"alert-{self._alert_counter:04d}",
            severity=severity,
            title=title,
            description=description,
            recommended_action=recommended_action,
            created_at=datetime.now(timezone.utc),
        )
        self.alerts.append(alert)

    def get_alerts(self) -> list[AlertRecord]:
        return list(reversed(self.alerts))

    @property
    def active_alert_count(self) -> int:
        return len([a for a in self.alerts if a.severity != AlertSeverity.INFO])

    # ── Aggregate stats ────────────────────────────────────────

    @property
    def total_requests(self) -> int:
        return len(self.events)

    @property
    def suspicious_requests(self) -> int:
        from app.schemas.decision import Decision

        return len([e for e in self.events if e.decision != Decision.ALLOW])

    @property
    def decoy_redirects(self) -> int:
        from app.schemas.decision import Decision

        return len(
            [e for e in self.events if e.decision == Decision.REDIRECT_TO_DECOY]
        )

    @property
    def average_risk_score(self) -> float:
        if not self.events:
            return 0.0
        return sum(e.risk_score for e in self.events) / len(self.events)


# Global singleton — fine for demo; replace with DI in production.
store = MemoryStore()
