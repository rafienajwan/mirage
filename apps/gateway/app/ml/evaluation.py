"""Holdout evaluation for reviewed MIRAGE model artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from app.ml.datasets import normalize_features, normalize_label
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


def _load_holdout_rows(input_path: Path) -> tuple[np.ndarray, np.ndarray]:
    features: list[list[float]] = []
    labels: list[int] = []
    with input_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"holdout row must be an object on line {line_number}")
            normalized = normalize_features(
                record.get("features"),
                line_number=line_number,
            )
            features.append([normalized[name] for name in FEATURE_NAMES])
            labels.append(normalize_label(record.get("label"), line_number=line_number))

    if not labels:
        raise ValueError("holdout input is empty")
    return np.asarray(features, dtype=float), np.asarray(labels, dtype=int)


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
    blockers: list[str] = []
    metrics: dict[str, float | int] = {}

    try:
        artifact = joblib.load(artifact_path)
    except FileNotFoundError:
        return HoldoutEvaluation(
            artifact_path=str(artifact_path),
            input_path=str(input_path),
            holdout_ready=False,
            metrics={},
            blockers=["Artifact file does not exist"],
        )
    except Exception as exc:
        return HoldoutEvaluation(
            artifact_path=str(artifact_path),
            input_path=str(input_path),
            holdout_ready=False,
            metrics={},
            blockers=[f"Artifact could not be loaded: {exc}"],
        )

    if not isinstance(artifact, dict):
        blockers.append("Artifact must be a dictionary payload")
        artifact = {}
    if tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
        blockers.append("Artifact feature contract does not match the gateway")
    model = artifact.get("model")
    if model is None:
        blockers.append("Artifact is missing model")

    try:
        x_holdout, y_holdout = _load_holdout_rows(input_path)
    except FileNotFoundError:
        return HoldoutEvaluation(
            artifact_path=str(artifact_path),
            input_path=str(input_path),
            holdout_ready=False,
            metrics={},
            blockers=["Holdout file does not exist"],
        )
    except ValueError as exc:
        return HoldoutEvaluation(
            artifact_path=str(artifact_path),
            input_path=str(input_path),
            holdout_ready=False,
            metrics={},
            blockers=[str(exc)],
        )

    normal_rows = int((y_holdout == 0).sum())
    suspicious_rows = int((y_holdout == 1).sum())
    metrics["evaluated_rows"] = int(len(y_holdout))
    metrics["normal_rows"] = normal_rows
    metrics["suspicious_rows"] = suspicious_rows

    if len(y_holdout) < min_rows:
        blockers.append(f"Holdout rows {len(y_holdout)} is below {min_rows}")
    if {int(label) for label in y_holdout} != {0, 1}:
        blockers.append("Holdout data must contain both normal and suspicious labels")

    if model is not None and not blockers:
        predictions = model.predict(x_holdout)
        tn, fp, _, _ = confusion_matrix(
            y_holdout,
            predictions,
            labels=[0, 1],
        ).ravel()
        metrics.update(
            {
                "precision": float(
                    precision_score(y_holdout, predictions, zero_division=0)
                ),
                "recall": float(recall_score(y_holdout, predictions, zero_division=0)),
                "f1_score": float(f1_score(y_holdout, predictions, zero_division=0)),
                "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
            }
        )

        if metrics["precision"] < min_precision:
            blockers.append(
                f"Precision {metrics['precision']:.3f} is below {min_precision:.3f}"
            )
        if metrics["recall"] < min_recall:
            blockers.append(f"Recall {metrics['recall']:.3f} is below {min_recall:.3f}")
        if metrics["f1_score"] < min_f1_score:
            blockers.append(f"F1 {metrics['f1_score']:.3f} is below {min_f1_score:.3f}")
        if metrics["false_positive_rate"] > max_false_positive_rate:
            blockers.append(
                "False-positive rate "
                f"{metrics['false_positive_rate']:.3f} is above "
                f"{max_false_positive_rate:.3f}"
            )

    return HoldoutEvaluation(
        artifact_path=str(artifact_path),
        input_path=str(input_path),
        holdout_ready=not blockers,
        metrics=metrics,
        blockers=blockers,
    )
