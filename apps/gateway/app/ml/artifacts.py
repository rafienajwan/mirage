"""Review helpers for trained MIRAGE model artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
import math
from pathlib import Path
import re
from typing import Any

import joblib
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from app.ml.artifact_integrity import ArtifactIntegrityError, verify_artifact_digest
from app.services.feature_extraction import FEATURE_CONTRACT_VERSION, FEATURE_NAMES

REQUIRED_METRICS = (
    "precision",
    "recall",
    "f1_score",
    "false_positive_rate",
    "training_rows",
    "test_rows",
)
DATASET_LINEAGE_FIELDS = (
    "dataset_name",
    "dataset_version",
    "source_kind",
    "manifest_sha256",
    "train_sha256",
    "test_sha256",
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
    feature_contract_version: int | None = None
    dataset_lineage: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value if math.isfinite(value) else None
    return None


def _review_dataset_lineage(
    raw_lineage: object,
    artifact_version: int | None,
    blockers: list[str],
) -> dict[str, str] | None:
    if raw_lineage is None and artifact_version == 1:
        return None
    if not isinstance(raw_lineage, dict):
        blockers.append("Artifact dataset lineage is missing or invalid")
        return None

    lineage: dict[str, str] = {}
    for field_name in DATASET_LINEAGE_FIELDS:
        value = raw_lineage.get(field_name)
        if not isinstance(value, str) or not value:
            blockers.append(f"Artifact dataset lineage {field_name} is invalid")
            continue
        if field_name.endswith("_sha256") and re.fullmatch(
            r"[0-9a-fA-F]{64}", value
        ) is None:
            blockers.append(f"Artifact dataset lineage {field_name} is invalid")
            continue
        lineage[field_name] = value
    return lineage


def load_checked_artifact(
    artifact_path: Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Load an artifact (after the optional pin check) and check its contract.

    Returns (None, blockers) when the file cannot be loaded at all, otherwise
    the payload (``{}`` if it is not a dictionary) and its contract blockers.
    """
    try:
        if expected_sha256 is not None:
            verify_artifact_digest(artifact_path, expected_sha256)
        artifact = joblib.load(artifact_path)
    except ArtifactIntegrityError:
        return None, ["Artifact SHA-256 does not match MIRAGE_MODEL_ARTIFACT_SHA256"]
    except FileNotFoundError:
        return None, ["Artifact file does not exist"]
    except Exception as exc:
        return None, [f"Artifact could not be loaded: {exc}"]

    blockers: list[str] = []
    if not isinstance(artifact, dict):
        blockers.append("Artifact must be a dictionary payload")
        artifact = {}
    if artifact.get("model") is None:
        blockers.append("Artifact is missing model")
    if artifact.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
        blockers.append("Artifact feature contract version does not match the gateway")
    if tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
        blockers.append("Artifact feature contract does not match the gateway")
    return artifact, blockers


def classification_metrics(y_true: Any, predictions: Any) -> dict[str, float]:
    """Precision, recall, F1 and false-positive rate for binary labels."""
    tn, fp, _, _ = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1_score": float(f1_score(y_true, predictions, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
    }


def threshold_blockers(
    metrics: dict[str, float | int],
    *,
    min_precision: float,
    min_recall: float,
    min_f1_score: float,
    max_false_positive_rate: float,
) -> list[str]:
    """Blockers for metrics outside the thresholds; absent metrics are skipped."""
    blockers: list[str] = []
    for key, name, minimum in (
        ("precision", "Precision", min_precision),
        ("recall", "Recall", min_recall),
        ("f1_score", "F1", min_f1_score),
    ):
        if key in metrics and metrics[key] < minimum:
            blockers.append(f"{name} {metrics[key]:.3f} is below {minimum:.3f}")
    rate = metrics.get("false_positive_rate")
    if rate is not None and rate > max_false_positive_rate:
        blockers.append(
            f"False-positive rate {rate:.3f} is above {max_false_positive_rate:.3f}"
        )
    return blockers


def review_model_artifact(
    artifact_path: Path,
    *,
    expected_sha256: str | None = None,
    min_precision: float = 0.5,
    min_recall: float = 0.5,
    min_f1_score: float = 0.5,
    max_false_positive_rate: float = 0.5,
    min_training_rows: int = 15,
    min_test_rows: int = 5,
) -> ArtifactReview:
    """Validate an artifact before enabling model-only shadow scoring."""
    warnings: list[str] = []
    metrics: dict[str, float | int] = {}

    artifact, blockers = load_checked_artifact(
        artifact_path, expected_sha256=expected_sha256
    )
    if artifact is None:
        return ArtifactReview(
            artifact_path=str(artifact_path),
            artifact_version=None,
            shadow_ready=False,
            metrics={},
            blockers=blockers,
            warnings=[],
        )

    artifact_version = artifact.get("artifact_version")
    if not isinstance(artifact_version, int):
        artifact_version = None
        blockers.append("Artifact version is missing or invalid")
    feature_contract_version = artifact.get("feature_contract_version")
    if not isinstance(feature_contract_version, int):
        feature_contract_version = None

    dataset_lineage = _review_dataset_lineage(
        artifact.get("dataset_lineage"),
        artifact_version,
        blockers,
    )

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

    blockers.extend(
        threshold_blockers(
            metrics,
            min_precision=min_precision,
            min_recall=min_recall,
            min_f1_score=min_f1_score,
            max_false_positive_rate=max_false_positive_rate,
        )
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
        feature_contract_version=feature_contract_version,
        dataset_lineage=dataset_lineage,
    )


def file_stamp(path: Path) -> tuple[int, int]:
    """Return (mtime_ns, size) so caches notice a replaced file."""
    try:
        stat = path.stat()
    except OSError:
        return -1, -1
    return stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=8)
def _cached_review(
    reviewer: Callable[..., ArtifactReview],
    path_value: str,
    _stamp: tuple[int, int],
    expected_sha256: str | None,
) -> ArtifactReview:
    return reviewer(Path(path_value), expected_sha256=expected_sha256)


def cached_artifact_review(
    artifact_path: Path,
    *,
    expected_sha256: str | None = None,
    reviewer: Callable[..., ArtifactReview] | None = None,
) -> ArtifactReview:
    """Review an artifact once per (path, mtime, size, pinned digest)."""
    return _cached_review(
        reviewer or review_model_artifact,
        str(artifact_path),
        file_stamp(artifact_path),
        expected_sha256,
    )
