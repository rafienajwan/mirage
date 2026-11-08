"""Holdout evaluation for reviewed MIRAGE model artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.artifacts import (
    classification_metrics,
    load_checked_artifact,
    threshold_blockers,
)
from app.ml.datasets import load_mirage_jsonl
from app.services.feature_extraction import FEATURE_NAMES


@dataclass(frozen=True)
class HoldoutEvaluation:
    """Result for checking an artifact against a prepared holdout split."""

    artifact_path: str
    input_path: str
    holdout_ready: bool
    metrics: dict[str, float | int]
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_model_artifact(
    artifact_path: Path,
    input_path: Path,
    *,
    min_precision: float = 0.5,
    min_recall: float = 0.5,
    min_f1_score: float = 0.5,
    max_false_positive_rate: float = 0.5,
    min_rows: int = 5,
) -> HoldoutEvaluation:
    """Evaluate a trained artifact on a prepared holdout JSONL split."""

    def result(metrics: dict[str, float | int], blockers: list[str]) -> HoldoutEvaluation:
        return HoldoutEvaluation(
            artifact_path=str(artifact_path),
            input_path=str(input_path),
            holdout_ready=not blockers,
            metrics=metrics,
            blockers=blockers,
        )

    artifact, blockers = load_checked_artifact(artifact_path)
    if artifact is None:
        return result({}, blockers)

    try:
        rows = load_mirage_jsonl(input_path)
    except FileNotFoundError:
        return result({}, ["Holdout file does not exist"])
    except ValueError as exc:
        return result({}, [str(exc)])
    if not rows:
        return result({}, ["holdout input is empty"])

    x_holdout = np.asarray(
        [[row.features[name] for name in FEATURE_NAMES] for row in rows], dtype=float
    )
    y_holdout = np.asarray([row.label for row in rows], dtype=int)
    metrics: dict[str, float | int] = {
        "evaluated_rows": len(rows),
        "normal_rows": int((y_holdout == 0).sum()),
        "suspicious_rows": int((y_holdout == 1).sum()),
    }

    if len(rows) < min_rows:
        blockers.append(f"Holdout rows {len(rows)} is below {min_rows}")
    if set(y_holdout.tolist()) != {0, 1}:
        blockers.append("Holdout data must contain both normal and suspicious labels")

    if not blockers:
        metrics.update(
            classification_metrics(y_holdout, artifact["model"].predict(x_holdout))
        )
        blockers.extend(
            threshold_blockers(
                metrics,
                min_precision=min_precision,
                min_recall=min_recall,
                min_f1_score=min_f1_score,
                max_false_positive_rate=max_false_positive_rate,
            )
        )

    return result(metrics, blockers)
