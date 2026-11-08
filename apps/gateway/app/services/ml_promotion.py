"""Guarded, read-only ML promotion-readiness evaluation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from app.core.config import settings as app_settings
from app.ml.artifact_integrity import UNPINNED_BLOCKER, pinned_digest, sha256_file
from app.ml.artifacts import (
    ArtifactReview,
    cached_artifact_review,
    file_stamp,
    review_model_artifact,
)
from app.ml.dataset_review import DatasetReview, review_prepared_dataset
from app.ml.errors import DatasetValidationError
from app.schemas.dashboard import MLPromotionGate, MLPromotionReadiness, MLShadowSummary
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.services.training_export import LABEL_TO_BINARY

ArtifactReviewer = Callable[..., ArtifactReview]
DatasetReviewer = Callable[..., DatasetReview]
LineageReviewer = Callable[[ArtifactReview, DatasetReview, Path], bool]


def _dataset_stamp(manifest_path: Path) -> tuple[tuple[int, int], ...]:
    """Stamp the manifest and every file it lists, so replacing a split re-reviews."""
    stamps = [file_stamp(manifest_path)]
    try:
        files = json.loads(manifest_path.read_text(encoding="utf-8")).get("files")
    except (OSError, ValueError, AttributeError):
        files = None
    if isinstance(files, dict):
        stamps.extend(
            file_stamp(manifest_path.parent / str(name))
            for _, name in sorted(files.items())
        )
    return tuple(stamps)


@lru_cache(maxsize=8)
def _cached_dataset_review(
    reviewer: DatasetReviewer,
    path_value: str,
    _stamp: tuple[tuple[int, int], ...],
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


def _artifact_matches_dataset(
    artifact_review: ArtifactReview,
    dataset_review: DatasetReview,
    manifest_path: Path,
) -> bool:
    lineage = artifact_review.dataset_lineage
    if not lineage:
        return False
    try:
        manifest_sha256 = sha256_file(manifest_path)
    except OSError:
        return False
    return (
        lineage.get("dataset_name") == dataset_review.dataset_name
        and lineage.get("dataset_version") == dataset_review.dataset_version
        and lineage.get("source_kind") == dataset_review.source_kind
        and lineage.get("manifest_sha256") == manifest_sha256
    )


@dataclass(frozen=True)
class ClassifierRates:
    """Rates are None when their denominator is zero (undefined, not 0)."""

    precision: float | None
    recall: float | None
    false_positive_rate: float | None


@dataclass(frozen=True)
class LabeledComparison:
    events: int
    model: ClassifierRates
    heuristic: ClassifierRates
    positives: int = 0
    negatives: int = 0


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _rates(pairs: list[tuple[bool, bool]]) -> ClassifierRates:
    """Rates from (is_suspicious, predicted_redirect) pairs."""
    tp = sum(truth and predicted for truth, predicted in pairs)
    fp = sum(predicted and not truth for truth, predicted in pairs)
    fn = sum(truth and not predicted for truth, predicted in pairs)
    tn = sum(not truth and not predicted for truth, predicted in pairs)
    return ClassifierRates(
        precision=_rate(tp, tp + fp),
        recall=_rate(tp, tp + fn),
        false_positive_rate=_rate(fp, fp + tn),
    )


def labeled_shadow_comparison(events: Iterable[EventRecord]) -> LabeledComparison:
    """Compare model and heuristic redirects against analyst labels."""
    redirect = Decision.REDIRECT_TO_DECOY.value
    model: list[tuple[bool, bool]] = []
    heuristic: list[tuple[bool, bool]] = []
    for event in events:
        if event.analyst_label is None or event.ml_shadow is None:
            continue
        truth = LABEL_TO_BINARY[event.analyst_label] == 1
        heuristic_decision = event.ml_shadow.heuristic_decision or event.decision.value
        model.append((truth, event.ml_shadow.shadow_decision == redirect))
        heuristic.append((truth, heuristic_decision == redirect))
    positives = sum(truth for truth, _ in model)
    return LabeledComparison(
        events=len(model),
        model=_rates(model),
        heuristic=_rates(heuristic),
        positives=positives,
        negatives=len(model) - positives,
    )


def _labeled_gate(comparison: LabeledComparison, minimum: int) -> MLPromotionGate:
    model, heuristic = comparison.model, comparison.heuristic
    on_events = f"on {comparison.events} analyst-labeled events"
    if not (comparison.positives and comparison.negatives):
        passed = False
        message = (
            "Analyst labels must include at least one suspicious and one normal "
            f"event; found {comparison.positives} suspicious and "
            f"{comparison.negatives} normal {on_events}"
        )
    elif not model.recall:
        # Recall is defined (positives exist), so 0 means no true positive.
        passed = False
        message = f"Model redirected none of the suspicious events {on_events}"
    else:
        # Model precision is defined here; an undefined heuristic precision
        # (it never redirected) counts as 0.
        passed = (
            comparison.events >= minimum
            and (model.precision or 0.0) >= (heuristic.precision or 0.0)
            and model.recall >= (heuristic.recall or 0.0)
        )
        message = (
            f"Model precision {model.precision} vs heuristic {heuristic.precision}, "
            f"model recall {model.recall} vs heuristic {heuristic.recall} "
            f"{on_events}"
        )
    return _gate(
        "labeled_model_vs_heuristic",
        passed,
        message,
        actual=comparison.events,
        required=minimum,
    )


def evaluate_ml_promotion(
    *,
    shadow_summary: MLShadowSummary | Any,
    labeled_events: Iterable[EventRecord] = (),
    settings: Any = app_settings,
    artifact_reviewer: ArtifactReviewer = review_model_artifact,
    dataset_reviewer: DatasetReviewer = review_prepared_dataset,
    lineage_reviewer: LineageReviewer = _artifact_matches_dataset,
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
            "invalid_min_labeled_events",
            settings.ml_promotion_min_labeled_events >= 1,
            "Minimum labeled events must be at least 1",
            settings.ml_promotion_min_labeled_events,
            1,
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

    expected_sha256, may_load = pinned_digest(settings)
    artifact_review = (
        cached_artifact_review(
            artifact_path,
            expected_sha256=expected_sha256,
            reviewer=artifact_reviewer,
        )
        if may_load
        else ArtifactReview(
            artifact_path=str(artifact_path),
            artifact_version=None,
            shadow_ready=False,
            metrics={},
            blockers=[UNPINNED_BLOCKER],
            warnings=[],
        )
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
            _dataset_stamp(manifest_path),
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

    lineage_ready = bool(
        dataset_review
        and lineage_reviewer(artifact_review, dataset_review, manifest_path)
    )
    gates.append(
        _gate(
            "dataset_lineage",
            lineage_ready,
            "Artifact dataset lineage matches the configured manifest"
            if lineage_ready
            else "Artifact dataset lineage does not match the configured manifest",
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
            # Informational: agreeing with the heuristic is not the goal.
            _gate(
                "shadow_agreement_rate",
                True,
                "Shadow agreement with the heuristic (informational only)",
                actual=agreement_rate,
            ),
            _labeled_gate(
                labeled_shadow_comparison(labeled_events),
                settings.ml_promotion_min_labeled_events,
            ),
        ]
    )

    review_failed = any(
        not gate.passed
        for gate in gates
        if gate.code in {"artifact_review", "dataset_review", "dataset_lineage"}
    )
    observation_failed = any(
        not gate.passed
        for gate in gates
        if gate.code in {"shadow_event_count", "labeled_model_vs_heuristic"}
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
