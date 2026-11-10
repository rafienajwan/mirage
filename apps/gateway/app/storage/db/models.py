"""SQLAlchemy ORM models for events and alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.storage.db.database import Base


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetime that always reads back in UTC.

    SQLite stores no offset, so its values come back naive and would
    serialize without one; a browser then parses them as local time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class EventModel(Base):
    """Persisted security event."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512))
    method: Mapped[str] = mapped_column(String(16))
    risk_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(32))
    fingerprint_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="inspection")
    summary: Mapped[str] = mapped_column(Text, default="")
    feature_vector: Mapped[dict] = mapped_column(JSON, default=dict)
    ml_shadow: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyst_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    labeled_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    labeled_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AlertModel(Base):
    """Persisted security alert."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )


class HoneytokenHitModel(Base):
    """Persisted interaction with a decoy token."""

    __tablename__ = "honeytoken_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hit_id: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    event_id: Mapped[str] = mapped_column(String(32), index=True)
    token_kind: Mapped[str] = mapped_column(String(32))
    token_label: Mapped[str] = mapped_column(String(128))
    source_ip: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512))
    method: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[str] = mapped_column(String(256))


class CanaryAssignmentModel(Base):
    """Persisted synthetic canary assignment without raw token storage."""

    __tablename__ = "canary_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(32), index=True)
    token_kind: Mapped[str] = mapped_column(String(32), index=True)
    token_label: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    rotation_epoch: Mapped[str] = mapped_column(String(64), index=True)
    decoy_type: Mapped[str] = mapped_column(String(32))
    source_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    revoke_reason: Mapped[str] = mapped_column(String(240), default="")


class ActorProfileModel(Base):
    """Persisted actor aggregate derived from threat fingerprints."""

    __tablename__ = "actor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_ip: Mapped[str] = mapped_column(String(64))
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    suspicious_requests: Mapped[int] = mapped_column(Integer, default=0)
    decoy_redirects: Mapped[int] = mapped_column(Integer, default=0)
    honeytoken_hits: Mapped[int] = mapped_column(Integer, default=0)
    max_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    path_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    last_decision: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))


class ActorCaseModel(Base):
    """Persisted analyst workflow case derived from an actor cluster."""

    __tablename__ = "actor_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    cluster_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    actor_count: Mapped[int] = mapped_column(Integer, default=0)
    actor_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str] = mapped_column(String(512))
    assigned_to: Mapped[str] = mapped_column(String(120), default="", index=True)
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class OperatorModel(Base):
    """Dashboard operator account."""

    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )


class OperatorAuditModel(Base):
    """Append-only record of state-changing operator actions."""

    __tablename__ = "operator_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    operator: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(48))
    target: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")
