"""Actor profile schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.decision import Decision

ActorStatus = Literal["quiet", "watch", "suspicious", "confirmed_interaction"]
CaseSeverity = Literal["low", "medium", "high", "critical"]
CaseWorkflowStatus = Literal["open", "investigating", "closed"]


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


class ActorCluster(BaseModel):
    """Lightweight grouping of actors with similar operator-facing traits."""

    cluster_id: str
    label: str
    status: ActorStatus
    actor_count: int = Field(ge=0)
    actor_ids: list[str]
    shared_paths: list[str]
    max_risk_score: float = Field(ge=0, le=100)
    honeytoken_hits: int = Field(ge=0)
    decoy_redirects: int = Field(ge=0)
    last_seen: datetime


class ActorClusterSummary(BaseModel):
    """Actor cluster summary for threat-hunting triage."""

    total_clusters: int = Field(ge=0)
    clusters: list[ActorCluster]


class ActorCase(BaseModel):
    """Read-only case recommendation derived from actor clusters."""

    case_id: str
    cluster_id: str
    title: str
    severity: CaseSeverity
    status: Literal["recommended"]
    actor_count: int = Field(ge=0)
    actor_ids: list[str]
    evidence: list[str]
    recommended_action: str
    last_seen: datetime


class ActorCaseSummary(BaseModel):
    """Recommended actor cases for analyst triage."""

    total_cases: int = Field(ge=0)
    cases: list[ActorCase]


class ActorCaseOpenRequest(BaseModel):
    """Request to persist a recommended actor case."""

    note: str = Field(default="", max_length=500)
    assigned_to: str = Field(default="", max_length=120)


class ActorCaseUpdateRequest(BaseModel):
    """Operator update for a persisted actor case."""

    status: CaseWorkflowStatus
    note: str = Field(default="", max_length=500)
    assigned_to: str | None = Field(default=None, max_length=120)


class ActorCaseWorkflow(BaseModel):
    """Persisted actor case workflow record."""

    case_id: str
    cluster_id: str
    title: str
    severity: CaseSeverity
    status: CaseWorkflowStatus
    actor_count: int = Field(ge=0)
    actor_ids: list[str]
    evidence: list[str]
    recommended_action: str
    assigned_to: str = ""
    analyst_note: str = ""
    opened_at: datetime
    updated_at: datetime
    last_seen: datetime


class ActorCaseWorkflowSummary(BaseModel):
    """Persisted actor case workflow summary."""

    total_cases: int = Field(ge=0)
    cases: list[ActorCaseWorkflow]
