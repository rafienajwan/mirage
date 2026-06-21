"""In-memory async storage for events, alerts, and decoy state.

Drop-in replacement for DatabaseStore — all methods are async.
"""

from __future__ import annotations

from datetime import datetime, timezone
from collections import defaultdict

from app.schemas.dashboard import AlertRecord, AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import EventRecord


class MemoryStore:
    """Thread-safe-ish in-memory store (single-process demo only)."""

    def __init__(self) -> None:
        self.events: list[EventRecord] = []
        self.alerts: list[AlertRecord] = []
        self._alert_counter: int = 0

    # ── Events ─────────────────────────────────────────────────

    async def add_event(self, event: EventRecord) -> None:
        self.events.append(event)

    async def get_recent_events(self, limit: int = 50) -> list[EventRecord]:
        return list(reversed(self.events[-limit:]))

    # ── Alerts ─────────────────────────────────────────────────

    async def add_alert(
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

    async def get_alerts(self) -> list[AlertRecord]:
        return list(reversed(self.alerts))

    async def get_active_alert_count(self) -> int:
        return len([a for a in self.alerts if a.severity != AlertSeverity.INFO])

    # ── Aggregate stats ────────────────────────────────────────

    async def get_total_requests(self) -> int:
        return len(self.events)

    async def get_suspicious_requests(self) -> int:
        return len([e for e in self.events if e.decision != Decision.ALLOW])

    async def get_decoy_redirects(self) -> int:
        return len(
            [e for e in self.events if e.decision == Decision.REDIRECT_TO_DECOY]
        )

    async def get_average_risk_score(self) -> float:
        if not self.events:
            return 0.0
        return sum(e.risk_score for e in self.events) / len(self.events)

    # ── Chart data ────────────────────────────────────────────

    async def get_traffic_breakdown(self) -> list[dict]:
        """Group events by hour into normal/suspicious buckets."""
        buckets: dict[int, dict] = defaultdict(lambda: {"normal": 0, "suspicious": 0})
        for e in self.events:
            hour = e.timestamp.hour
            if e.decision == Decision.ALLOW:
                buckets[hour]["normal"] += 1
            else:
                buckets[hour]["suspicious"] += 1
        return [
            {"hour": h, **buckets[h]} for h in sorted(buckets.keys())
        ]

    async def get_risk_history(self, limit: int = 20) -> list[dict]:
        """Recent risk scores ordered chronologically for sparkline chart."""
        recent = self.events[:limit]
        return [
            {"timestamp": e.timestamp.isoformat(), "risk_score": e.risk_score}
            for e in recent
        ]

    async def get_last_decoy_trigger(self) -> datetime | None:
        """Timestamp of the most recent decoy redirect event."""
        for e in reversed(self.events):
            if e.decision == Decision.REDIRECT_TO_DECOY:
                return e.timestamp
        return None


# Global singleton — fine for demo; replace with DI in production.
store = MemoryStore()
