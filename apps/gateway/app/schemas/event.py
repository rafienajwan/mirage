"""Activity event schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.decision import Decision


class EventRecord(BaseModel):
    """Single logged security event."""

    event_id: str
    timestamp: datetime
    ip_address: str = Field(description="Masked/partial IP for privacy")
    path: str
    method: str
    risk_score: float
    decision: Decision
    event_type: str = Field(default="inspection")
    summary: str = ""
    feature_vector: dict[str, float] = Field(default_factory=dict)
