"""Security decision schemas."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(str, Enum):
    ALLOW = "allow"
    MONITOR = "monitor"
    REDIRECT_TO_DECOY = "redirect_to_decoy"


class InspectResponse(BaseModel):
    """Security decision returned after inspecting a request."""

    request_id: str = Field(..., description="Unique identifier for this inspection")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score 0–100")
    risk_level: RiskLevel
    decision: Decision
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable reasons for the score"
    )
    fingerprint_hash: str = Field(
        ..., description="Privacy-safe hash of request metadata"
    )
    decoy_type: Optional[str] = Field(
        default=None, description="Type of decoy response if redirected"
    )
