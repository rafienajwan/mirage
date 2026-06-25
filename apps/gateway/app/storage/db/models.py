"""SQLAlchemy ORM models for events and alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db.database import Base


class EventModel(Base):
    """Persisted security event."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512))
    method: Mapped[str] = mapped_column(String(16))
    risk_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64), default="inspection")
    summary: Mapped[str] = mapped_column(Text, default="")
    feature_vector: Mapped[dict] = mapped_column(JSON, default=dict)
    ml_shadow: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyst_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    labeled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class HoneytokenHitModel(Base):
    """Persisted interaction with a decoy token."""

    __tablename__ = "honeytoken_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hit_id: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    event_id: Mapped[str] = mapped_column(String(32), index=True)
    token_kind: Mapped[str] = mapped_column(String(32))
    token_label: Mapped[str] = mapped_column(String(128))
    source_ip: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512))
    method: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[str] = mapped_column(String(256))
