"""Guarded, read-only ML promotion-readiness evaluation."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings as app_settings
from app.ml.artifacts import ArtifactReview, review_model_artifact
from app.ml.datasets import DatasetReview, DatasetValidationError, review_prepared_dataset
from app.schemas.dashboard import MLPromotionGate, MLPromotionReadiness, MLShadowSummary

ArtifactReviewer = Callable[..., ArtifactReview]
DatasetReviewer = Callable[..., DatasetReview]


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


@lru_cache(maxsize=8)
def _cached_artifact_review(
    reviewer: ArtifactReviewer,
    path_value: str,
    _modified_at: int,
) -> ArtifactReview:
    return reviewer(Path(path_value))


@lru_cache(maxsize=8)
def _cached_dataset_review(
    reviewer: DatasetReviewer,
    path_value: str,
    _modified_at: int,
    min_total_rows: int,
    min_rows_per_class: int,
) -> DatasetReview:
    return reviewer(
        Path(path_value),
        min_total_rows=min_total_rows,
        min_rows_per_class=min_rows_per_class,
    )


def _gate(
    code: str,
    passed: bool,
    message: str,
    *,
    actual: float | int | str | None = None,
    required: float | int | str | None = None,
) -> MLPromotionGate:
    return MLPromotionGate(
        code=code,
        passed=passed,
        message=message,
        actual=actual,
        required=required,
    )


def evaluate_ml_promotion(
    *,
    shadow_summary: MLShadowSummary | Any,
    settings: Any = app_settings,
    artifact_reviewer: ArtifactReviewer = review_model_artifact,
    dataset_reviewer: DatasetReviewer = review_prepared_dataset,
) -> MLPromotionReadiness:
    """Evaluate prerequisites without changing the active routing policy."""
    artifact_path = (
        Path(settings.ml_model_artifact) if settings.ml_model_artifact else None
    )
    manifest_path = (
        Path(settings.ml_dataset_manifest) if settings.ml_dataset_manifest else None
    )
    gates: list[MLPromotionGate] = []
    warnings: list[str] = []

    if artifact_path is None:
        gates.append(
            _gate(
                "artifact_not_configured",
                False,
                "A reviewed model artifact is not configured",
            )
        )
    if manifest_path is None:
        gates.append(
            _gate(
                "dataset_not_configured",
                False,
                "A prepared dataset manifest is not configured",
            )
        )
    if artifact_path is None or manifest_path is None:
        return MLPromotionReadiness(
            status="unavailable",
            artifact=artifact_path.name if artifact_path else None,
            dataset_manifest=manifest_path.name if manifest_path else None,
            gates=gates,
            warnings=warnings,
        )

    threshold_checks = (
        (
            "invalid_min_total_rows",
            settings.ml_promotion_min_total_rows >= 1,
            "Minimum total rows must be at least 1",
            settings.ml_promotion_min_total_rows,
            1,
        ),
        (
            "invalid_min_rows_per_class",
            settings.ml_promotion_min_rows_per_class >= 1,
            "Minimum rows per class must be at least 1",
            settings.ml_promotion_min_rows_per_class,
            1,
        ),
        (
            "invalid_min_shadow_events",
            settings.ml_promotion_min_shadow_events >= 1,
            "Minimum shadow events must be at least 1",
            settings.ml_promotion_min_shadow_events,
            1,
        ),
        (
            "invalid_min_agreement_rate",
            0 <= settings.ml_promotion_min_agreement_rate <= 1,
            "Minimum agreement rate must be between 0 and 1",
            settings.ml_promotion_min_agreement_rate,
            "0..1",
        ),
    )
    for code, passed, message, actual, required in threshold_checks:
        if not passed:
            gates.append(
                _gate(
                    code,
                    False,
                    message,
                    actual=actual,
                    required=required,
                )
            )
    if gates:
        return MLPromotionReadiness(
            status="blocked",
            artifact=artifact_path.name,
            dataset_manifest=manifest_path.name,
            gates=gates,
            warnings=warnings,
        )

    artifact_review = _cached_artifact_review(
        artifact_reviewer,
        str(artifact_path),
        _mtime(artifact_path),
    )
    gates.append(
        _gate(
            "artifact_review",
            artifact_review.shadow_ready,
            "Artifact review passed"
            if artifact_review.shadow_ready
            else "Artifact review failed",
        )
    )
    warnings.extend(artifact_review.warnings)

    dataset_review: DatasetReview | None = None
    try:
        dataset_review = _cached_dataset_review(
            dataset_reviewer,
            str(manifest_path),
            _mtime(manifest_path),
            settings.ml_promotion_min_total_rows,
            settings.ml_promotion_min_rows_per_class,
        )
        gates.append(
            _gate(
                "dataset_review",
                dataset_review.ready_for_training,
                "Dataset review passed"
                if dataset_review.ready_for_training
                else "Dataset review failed",
                actual=dataset_review.total_rows,
                required=settings.ml_promotion_min_total_rows,
            )
        )
        warnings.extend(dataset_review.warnings)
    except (DatasetValidationError, OSError, ValueError):
        gates.append(
            _gate(
                "dataset_review",
                False,
                "Dataset manifest could not be reviewed",
            )
        )

    shadow_events = shadow_summary.shadow_events
    agreement_rate = shadow_summary.agreement_rate
    gates.extend(
        [
            _gate(
                "shadow_event_count",
                shadow_events >= settings.ml_promotion_min_shadow_events,
                "Shadow observation volume is sufficient"
                if shadow_events >= settings.ml_promotion_min_shadow_events
                else "More shadow observations are required",
                actual=shadow_events,
                required=settings.ml_promotion_min_shadow_events,
            ),
            _gate(
                "shadow_agreement_rate",
                agreement_rate >= settings.ml_promotion_min_agreement_rate,
                "Shadow agreement is within the compatibility threshold"
                if agreement_rate >= settings.ml_promotion_min_agreement_rate
                else "Shadow agreement needs operator investigation",
                actual=agreement_rate,
                required=settings.ml_promotion_min_agreement_rate,
            ),
        ]
    )

    review_failed = any(
        not gate.passed
        for gate in gates
        if gate.code in {"artifact_review", "dataset_review"}
    )
    observation_failed = any(
        not gate.passed
        for gate in gates
        if gate.code in {"shadow_event_count", "shadow_agreement_rate"}
    )
    if review_failed:
        status = "blocked"
    elif observation_failed:
        status = "needs_observation"
    else:
        status = "eligible"

    return MLPromotionReadiness(
        status=status,
        artifact=artifact_path.name,
        dataset_manifest=manifest_path.name,
        dataset_name=dataset_review.dataset_name if dataset_review else None,
        dataset_version=dataset_review.dataset_version if dataset_review else None,
        gates=gates,
        warnings=warnings,
    )
