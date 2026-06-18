"""DatabaseStore — async persistent replacement for MemoryStore.

Implements the same public API as MemoryStore but backed by SQLAlchemy.
All methods are async.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.schemas.dashboard import AlertRecord, AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.storage.db.database import get_session
from app.storage.db.models import AlertModel, EventModel


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
                event_type=event.event_type,
                summary=event.summary,
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
                    event_type=r.event_type,
                    summary=r.summary,
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

    async def get_alerts(self) -> list[AlertRecord]:
        async with get_session() as session:
            stmt = select(AlertModel).order_by(AlertModel.id.desc())
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
