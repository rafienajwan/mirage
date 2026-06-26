"""Actor profile schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.decision import Decision

ActorStatus = Literal["quiet", "watch", "suspicious", "confirmed_interaction"]


class ActorProfile(BaseModel):
    """Operator-facing summary for a repeated threat fingerprint."""

    actor_id: str
    fingerprint_hash: str
    source_ip: str
    first_seen: datetime
    last_seen: datetime
    request_count: int = Field(ge=0)
    suspicious_requests: int = Field(ge=0)
    decoy_redirects: int = Field(ge=0)
    honeytoken_hits: int = Field(ge=0)
    max_risk_score: float = Field(ge=0, le=100)
    average_risk_score: float = Field(ge=0, le=100)
    top_paths: list[str]
    last_decision: Decision
    status: ActorStatus


class ActorProfileSummary(BaseModel):
    """Recent actor profile summary for the dashboard."""

    total_actors: int = Field(ge=0)
    profiles: list[ActorProfile]
