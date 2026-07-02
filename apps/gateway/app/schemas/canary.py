"""Canary token assignment schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.honeytoken import HoneytokenKind

CanaryAssignmentStatus = Literal["active", "revoked"]


class CanaryAssignment(BaseModel):
    """Persisted synthetic canary assignment without storing the raw token."""

    assignment_id: str
    actor_id: str
    token_kind: HoneytokenKind
    token_label: str
    token_hash: str
    rotation_epoch: str
    decoy_type: str
    source_path: str
    status: CanaryAssignmentStatus
    issued_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str = ""


class CanaryAssignmentSummary(BaseModel):
    """Dashboard list of canary token assignments."""

    total_assignments: int = Field(ge=0)
    assignments: list[CanaryAssignment]


class CanaryAssignmentRevokeRequest(BaseModel):
    """Operator request to revoke a canary assignment."""

    reason: str = Field(default="", max_length=240)
