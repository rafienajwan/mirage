"""DatabaseStore — async persistent replacement for MemoryStore.

Implements the same public API as MemoryStore but backed by SQLAlchemy.
All methods are async.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, extract, func, select

from app.schemas.dashboard import AlertRecord, AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import AnalystLabel, EventRecord
from app.schemas.honeytoken import HoneytokenHit
from app.storage.db.database import get_session
from app.storage.db.models import AlertModel, EventModel, HoneytokenHitModel


class DatabaseStore:
    """Async persistent store backed by SQLAlchemy."""

    # ── Events ─────────────────────────────────────────────────

    async def add_event(self, event: EventRecord) -> None:
        async with get_session() as session:
            row = EventModel(
                event_id=event.event_id,
                timestamp=event.timestamp,
                ip_address=event.ip_address,
                path=event.path,
                method=event.method,
                risk_score=event.risk_score,
                decision=event.decision.value,
                fingerprint_hash=event.fingerprint_hash,
                event_type=event.event_type,
                summary=event.summary,
                feature_vector=event.feature_vector,
                ml_shadow=(
                    event.ml_shadow.model_dump(mode="json")
                    if event.ml_shadow
                    else None
                ),
                analyst_label=(
                    event.analyst_label.value if event.analyst_label else None
                ),
                analyst_note=event.analyst_note,
                labeled_at=event.labeled_at,
            )
            session.add(row)

    async def get_recent_events(self, limit: int = 50) -> list[EventRecord]:
        async with get_session() as session:
            stmt = (
                select(EventModel)
                .order_by(EventModel.id.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                EventRecord(
                    event_id=r.event_id,
                    timestamp=r.timestamp,
                    ip_address=r.ip_address,
                    path=r.path,
                    method=r.method,
                    risk_score=r.risk_score,
                    decision=Decision(r.decision),
                    fingerprint_hash=r.fingerprint_hash or "",
                    event_type=r.event_type,
                    summary=r.summary,
                    feature_vector=r.feature_vector or {},
                    ml_shadow=r.ml_shadow,
                    analyst_label=(
                        AnalystLabel(r.analyst_label)
                        if r.analyst_label
                        else None
                    ),
                    analyst_note=r.analyst_note or "",
                    labeled_at=r.labeled_at,
                )
                for r in rows
            ]

    async def update_event_label(
        self,
        event_id: str,
        label: AnalystLabel,
        note: str = "",
    ) -> EventRecord | None:
        async with get_session() as session:
            result = await session.execute(
                select(EventModel).where(EventModel.event_id == event_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.analyst_label = label.value
            row.analyst_note = note
            row.labeled_at = datetime.now(timezone.utc)
            return EventRecord(
                event_id=row.event_id,
                timestamp=row.timestamp,
                ip_address=row.ip_address,
                path=row.path,
                method=row.method,
                risk_score=row.risk_score,
                decision=Decision(row.decision),
                fingerprint_hash=row.fingerprint_hash or "",
                event_type=row.event_type,
                summary=row.summary,
                feature_vector=row.feature_vector or {},
                ml_shadow=row.ml_shadow,
                analyst_label=label,
                analyst_note=row.analyst_note or "",
                labeled_at=row.labeled_at,
            )

    async def get_labeled_events(self, limit: int = 10000) -> list[EventRecord]:
        async with get_session() as session:
            stmt = (
                select(EventModel)
                .where(EventModel.analyst_label.is_not(None))
                .order_by(EventModel.id.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                EventRecord(
                    event_id=r.event_id,
                    timestamp=r.timestamp,
                    ip_address=r.ip_address,
                    path=r.path,
                    method=r.method,
                    risk_score=r.risk_score,
                    decision=Decision(r.decision),
                    fingerprint_hash=r.fingerprint_hash or "",
                    event_type=r.event_type,
                    summary=r.summary,
                    feature_vector=r.feature_vector or {},
                    ml_shadow=r.ml_shadow,
                    analyst_label=(
                        AnalystLabel(r.analyst_label)
                        if r.analyst_label
                        else None
                    ),
                    analyst_note=r.analyst_note or "",
                    labeled_at=r.labeled_at,
                )
                for r in rows
            ]

    # ── Alerts ─────────────────────────────────────────────────

    async def add_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        recommended_action: str,
    ) -> None:
        async with get_session() as session:
            # Get the next alert ID
            count_stmt = select(func.count()).select_from(AlertModel)
            count_result = await session.execute(count_stmt)
            count = count_result.scalar() or 0

            alert = AlertModel(
                alert_id=f"alert-{count + 1:04d}",
                severity=severity.value,
                title=title,
                description=description,
                recommended_action=recommended_action,
                created_at=datetime.now(timezone.utc),
            )
            session.add(alert)

    async def get_alerts(self, limit: int = 100) -> list[AlertRecord]:
        async with get_session() as session:
            stmt = select(AlertModel).order_by(AlertModel.id.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                AlertRecord(
                    alert_id=r.alert_id,
                    severity=AlertSeverity(r.severity),
                    title=r.title,
                    description=r.description,
                    recommended_action=r.recommended_action,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    async def get_active_alert_count(self) -> int:
        async with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(AlertModel)
                .where(AlertModel.severity != AlertSeverity.INFO.value)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def add_honeytoken_hit(self, hit: HoneytokenHit) -> None:
        async with get_session() as session:
            session.add(
                HoneytokenHitModel(
                    hit_id=hit.hit_id,
                    timestamp=hit.timestamp,
                    event_id=hit.event_id,
                    token_kind=hit.token_kind,
                    token_label=hit.token_label,
                    source_ip=hit.source_ip,
                    path=hit.path,
                    method=hit.method,
                    evidence=hit.evidence,
                )
            )

    async def get_honeytoken_hits(self, limit: int = 50) -> list[HoneytokenHit]:
        async with get_session() as session:
            stmt = (
                select(HoneytokenHitModel)
                .order_by(HoneytokenHitModel.id.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [
                HoneytokenHit(
                    hit_id=row.hit_id,
                    timestamp=row.timestamp,
                    event_id=row.event_id,
                    token_kind=row.token_kind,
                    token_label=row.token_label,
                    source_ip=row.source_ip,
                    path=row.path,
                    method=row.method,
                    evidence=row.evidence,
                )
                for row in result.scalars().all()
            ]

    async def get_honeytoken_hit_count(self) -> int:
        async with get_session() as session:
            stmt = select(func.count()).select_from(HoneytokenHitModel)
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ── Aggregate stats ────────────────────────────────────────

    async def get_total_requests(self) -> int:
        async with get_session() as session:
            stmt = select(func.count()).select_from(EventModel)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_suspicious_requests(self) -> int:
        async with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(EventModel)
                .where(EventModel.decision != Decision.ALLOW.value)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_decoy_redirects(self) -> int:
        async with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(EventModel)
                .where(EventModel.decision == Decision.REDIRECT_TO_DECOY.value)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_average_risk_score(self) -> float:
        async with get_session() as session:
            stmt = select(func.avg(EventModel.risk_score))
            result = await session.execute(stmt)
            avg = result.scalar()
            return float(avg) if avg is not None else 0.0

    # ── Chart data ────────────────────────────────────────────

    async def get_traffic_breakdown(self) -> list[dict]:
        """Group events by hour into normal/suspicious buckets (last 12 hours)."""
        async with get_session() as session:
            is_suspicious = EventModel.decision != Decision.ALLOW.value
            stmt = (
                select(
                    extract("hour", EventModel.timestamp).label("hour"),
                    func.sum(case((~is_suspicious, 1), else_=0)).label("normal"),
                    func.sum(case((is_suspicious, 1), else_=0)).label("suspicious"),
                )
                .group_by("hour")
                .order_by("hour")
            )
            result = await session.execute(stmt)
            return [
                {"hour": int(r.hour), "normal": int(r.normal), "suspicious": int(r.suspicious)}
                for r in result.all()
            ]

    async def get_risk_history(self, limit: int = 20) -> list[dict]:
        """Recent risk scores ordered chronologically for sparkline chart."""
        async with get_session() as session:
            recent_stmt = (
                select(EventModel.timestamp, EventModel.risk_score)
                .order_by(EventModel.id.desc())
                .limit(limit)
            )
            result = await session.execute(recent_stmt)
            rows = list(reversed(result.all()))
            return [
                {"timestamp": r.timestamp.isoformat(), "risk_score": r.risk_score}
                for r in rows
            ]

    async def get_last_decoy_trigger(self) -> datetime | None:
        """Timestamp of the most recent decoy redirect event."""
        async with get_session() as session:
            stmt = (
                select(func.max(EventModel.timestamp))
                .where(EventModel.decision == Decision.REDIRECT_TO_DECOY.value)
            )
            result = await session.execute(stmt)
            return result.scalar()
