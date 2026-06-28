"""In-memory async storage for events, alerts, and decoy state.

Drop-in replacement for DatabaseStore — all methods are async.
"""

from __future__ import annotations

from datetime import datetime, timezone
from collections import defaultdict

from app.schemas.actor import ActorProfile
from app.schemas.dashboard import AlertRecord, AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import AnalystLabel, EventRecord
from app.schemas.honeytoken import HoneytokenHit
from app.services.actor_identity import actor_id_from_key, actor_key, actor_status


class MemoryStore:
    """Thread-safe-ish in-memory store (single-process demo only)."""

    def __init__(self) -> None:
        self.events: list[EventRecord] = []
        self.alerts: list[AlertRecord] = []
        self.honeytoken_hits: list[HoneytokenHit] = []
        self.actor_profiles: dict[str, dict] = {}
        self._alert_counter: int = 0

    # ── Events ─────────────────────────────────────────────────

    async def add_event(self, event: EventRecord) -> None:
        self.events.append(event)
        self._upsert_actor_event(event)

    async def get_recent_events(self, limit: int = 50) -> list[EventRecord]:
        return list(reversed(self.events[-limit:]))

    async def update_event_label(
        self,
        event_id: str,
        label: AnalystLabel,
        note: str = "",
    ) -> EventRecord | None:
        for index, event in enumerate(self.events):
            if event.event_id == event_id:
                updated = event.model_copy(
                    update={
                        "analyst_label": label,
                        "analyst_note": note,
                        "labeled_at": datetime.now(timezone.utc),
                    }
                )
                self.events[index] = updated
                return updated
        return None

    async def get_labeled_events(self, limit: int = 10000) -> list[EventRecord]:
        labeled = [event for event in self.events if event.analyst_label is not None]
        return labeled[:limit]

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

    async def get_alerts(self, limit: int = 100) -> list[AlertRecord]:
        return list(reversed(self.alerts[-limit:]))

    async def get_active_alert_count(self) -> int:
        return len([a for a in self.alerts if a.severity != AlertSeverity.INFO])

    async def add_honeytoken_hit(self, hit: HoneytokenHit) -> None:
        self.honeytoken_hits.append(hit)
        event = next((item for item in self.events if item.event_id == hit.event_id), None)
        if event is not None:
            key = actor_key(event)
            actor_id = actor_id_from_key(key)
            profile = self.actor_profiles.get(actor_id)
            if profile is not None:
                profile["honeytoken_hits"] += 1
                profile["status"] = actor_status(
                    profile["honeytoken_hits"],
                    profile["decoy_redirects"],
                    profile["suspicious_requests"],
                    profile["max_risk_score"],
                )

    async def get_honeytoken_hits(self, limit: int = 50) -> list[HoneytokenHit]:
        return list(reversed(self.honeytoken_hits[-limit:]))

    async def get_honeytoken_hit_count(self) -> int:
        return len(self.honeytoken_hits)

    async def get_actor_profiles(self, limit: int = 20) -> list[ActorProfile]:
        profiles = [self._profile_to_schema(item) for item in self.actor_profiles.values()]
        profiles.sort(
            key=lambda profile: (
                profile.honeytoken_hits,
                profile.decoy_redirects,
                profile.max_risk_score,
                profile.last_seen,
            ),
            reverse=True,
        )
        return profiles[:limit]

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
        recent = self.events[-limit:]
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

    def _upsert_actor_event(self, event: EventRecord) -> None:
        key = actor_key(event)
        actor_id = actor_id_from_key(key)
        profile = self.actor_profiles.get(actor_id)
        if profile is None:
            profile = {
                "actor_id": actor_id,
                "fingerprint_hash": event.fingerprint_hash,
                "source_ip": event.ip_address,
                "first_seen": event.timestamp,
                "last_seen": event.timestamp,
                "request_count": 0,
                "suspicious_requests": 0,
                "decoy_redirects": 0,
                "honeytoken_hits": 0,
                "max_risk_score": 0.0,
                "total_risk_score": 0.0,
                "path_counts": defaultdict(int),
                "last_decision": event.decision,
                "status": "quiet",
            }
            self.actor_profiles[actor_id] = profile

        profile["source_ip"] = event.ip_address
        profile["last_seen"] = event.timestamp
        profile["request_count"] += 1
        profile["total_risk_score"] += event.risk_score
        profile["max_risk_score"] = max(profile["max_risk_score"], event.risk_score)
        profile["last_decision"] = event.decision
        profile["path_counts"][event.path] += 1
        if event.decision != Decision.ALLOW:
            profile["suspicious_requests"] += 1
        if event.decision == Decision.REDIRECT_TO_DECOY:
            profile["decoy_redirects"] += 1
        profile["status"] = actor_status(
            profile["honeytoken_hits"],
            profile["decoy_redirects"],
            profile["suspicious_requests"],
            profile["max_risk_score"],
        )

    def _profile_to_schema(self, profile: dict) -> ActorProfile:
        path_counts = profile["path_counts"]
        top_paths = [
            path
            for path, _ in sorted(
                path_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
        ]
        return ActorProfile(
            actor_id=profile["actor_id"],
            fingerprint_hash=profile["fingerprint_hash"],
            source_ip=profile["source_ip"],
            first_seen=profile["first_seen"],
            last_seen=profile["last_seen"],
            request_count=profile["request_count"],
            suspicious_requests=profile["suspicious_requests"],
            decoy_redirects=profile["decoy_redirects"],
            honeytoken_hits=profile["honeytoken_hits"],
            max_risk_score=round(profile["max_risk_score"], 1),
            average_risk_score=round(
                profile["total_risk_score"] / profile["request_count"],
                1,
            ),
            top_paths=top_paths,
            last_decision=profile["last_decision"],
            status=profile["status"],
        )


# Global singleton — fine for demo; replace with DI in production.
store = MemoryStore()
