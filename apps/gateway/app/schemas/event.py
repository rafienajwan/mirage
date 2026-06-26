"""Activity event schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.decision import Decision
from app.schemas.ml import MLShadowScore


class AnalystLabel(str, Enum):
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class EventLabelRequest(BaseModel):
    """Analyst correction applied to a stored event."""

    label: AnalystLabel
    note: str = Field(default="", max_length=500)


class EventRecord(BaseModel):
    """Single logged security event."""

    event_id: str
    timestamp: datetime
    ip_address: str = Field(description="Masked/partial IP for privacy")
    path: str
    method: str
    risk_score: float
    decision: Decision
    fingerprint_hash: str = ""
    event_type: str = Field(default="inspection")
    summary: str = ""
    feature_vector: dict[str, float] = Field(default_factory=dict)
    ml_shadow: MLShadowScore | None = None
    analyst_label: AnalystLabel | None = None
    analyst_note: str = ""
    labeled_at: datetime | None = None
