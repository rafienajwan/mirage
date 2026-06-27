"""Schemas for analyst-label retraining workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.dashboard import TrainingDataSummary


class RetrainingArtifactReview(BaseModel):
    """Sanitized review result for a newly trained artifact."""

    artifact_path: str
    artifact_version: int | None
    shadow_ready: bool
    metrics: dict[str, float | int]
    blockers: list[str]
    warnings: list[str]


class RetrainingRun(BaseModel):
    """Result of training an artifact from analyst-labeled events."""

    artifact_path: str
    training_summary: TrainingDataSummary
    metrics: dict[str, float | int]
    review: RetrainingArtifactReview
    next_steps: list[str] = Field(default_factory=list)
