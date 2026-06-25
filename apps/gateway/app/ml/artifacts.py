"""Review helpers for trained MIRAGE model artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib

from app.services.feature_extraction import FEATURE_NAMES

REQUIRED_METRICS = (
    "precision",
    "recall",
    "f1_score",
    "false_positive_rate",
    "training_rows",
    "test_rows",
)


@dataclass(frozen=True)
class ArtifactReview:
    """Review result for enabling an artifact in ML shadow mode."""

    artifact_path: str
    artifact_version: int | None
    shadow_ready: bool
    metrics: dict[str, float | int]
    blockers: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    return None


def review_model_artifact(
    artifact_path: Path,
    *,
    min_precision: float = 0.5,
    min_recall: float = 0.5,
    min_f1_score: float = 0.5,
    max_false_positive_rate: float = 0.5,
    min_training_rows: int = 15,
    min_test_rows: int = 5,
) -> ArtifactReview:
    """Validate an artifact before enabling model-only shadow scoring."""
    blockers: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, float | int] = {}
    artifact_version: int | None = None

    try:
        artifact = joblib.load(artifact_path)
    except FileNotFoundError:
        return ArtifactReview(
            artifact_path=str(artifact_path),
            artifact_version=None,
            shadow_ready=False,
            metrics={},
            blockers=["Artifact file does not exist"],
            warnings=[],
        )
    except Exception as exc:
        return ArtifactReview(
            artifact_path=str(artifact_path),
            artifact_version=None,
            shadow_ready=False,
            metrics={},
            blockers=[f"Artifact could not be loaded: {exc}"],
            warnings=[],
        )

    if not isinstance(artifact, dict):
        blockers.append("Artifact must be a dictionary payload")
        artifact = {}

    artifact_version_value = artifact.get("artifact_version")
    if isinstance(artifact_version_value, int):
        artifact_version = artifact_version_value
    else:
        blockers.append("Artifact version is missing or invalid")

    if "model" not in artifact:
        blockers.append("Artifact is missing model")

    if tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
        blockers.append("Artifact feature contract does not match the gateway")

    raw_metrics = artifact.get("metrics", {})
    if not isinstance(raw_metrics, dict):
        blockers.append("Artifact metrics must be a dictionary")
        raw_metrics = {}

    for name in REQUIRED_METRICS:
        value = _number(raw_metrics.get(name))
        if value is None:
            blockers.append(f"Metric {name!r} is missing or non-numeric")
        else:
            metrics[name] = value

    if "precision" in metrics and metrics["precision"] < min_precision:
        blockers.append(
            f"Precision {metrics['precision']:.3f} is below {min_precision:.3f}"
        )
    if "recall" in metrics and metrics["recall"] < min_recall:
        blockers.append(f"Recall {metrics['recall']:.3f} is below {min_recall:.3f}")
    if "f1_score" in metrics and metrics["f1_score"] < min_f1_score:
        blockers.append(f"F1 {metrics['f1_score']:.3f} is below {min_f1_score:.3f}")
    if (
        "false_positive_rate" in metrics
        and metrics["false_positive_rate"] > max_false_positive_rate
    ):
        blockers.append(
            "False-positive rate "
            f"{metrics['false_positive_rate']:.3f} is above "
            f"{max_false_positive_rate:.3f}"
        )
    if "training_rows" in metrics and metrics["training_rows"] < min_training_rows:
        blockers.append(
            f"Training rows {metrics['training_rows']} is below {min_training_rows}"
        )
    if "test_rows" in metrics and metrics["test_rows"] < min_test_rows:
        blockers.append(f"Test rows {metrics['test_rows']} is below {min_test_rows}")

    if not blockers and (
        metrics.get("training_rows", 0) < 100 or metrics.get("test_rows", 0) < 25
    ):
        warnings.append(
            "Dataset is small; keep artifact in shadow mode until reviewed manually"
        )

    return ArtifactReview(
        artifact_path=str(artifact_path),
        artifact_version=artifact_version,
        shadow_ready=not blockers,
        metrics=metrics,
        blockers=blockers,
        warnings=warnings,
    )
