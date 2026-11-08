"""Validated loading and inference for trained MIRAGE artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ml.artifact_integrity import load_verified_artifact
from app.services.feature_extraction import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_NAMES,
    FeatureVector,
)


class RiskClassifier:
    def __init__(self, artifact_path: Path, *, expected_sha256: str | None = None) -> None:
        self._use(load_verified_artifact(artifact_path, expected_sha256))

    @classmethod
    def from_artifact(cls, artifact: dict[str, Any]) -> RiskClassifier:
        """Build a classifier from an artifact that was already loaded and checked."""
        classifier = cls.__new__(cls)
        classifier._use(artifact)
        return classifier

    def _use(self, artifact: dict[str, Any]) -> None:
        if artifact.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
            raise ValueError(
                "Model feature contract version does not match the gateway"
            )
        if tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
            raise ValueError("Model feature contract does not match the gateway")
        self.model = artifact["model"]
        # One-row predictions: a per-call thread pool costs far more than it saves.
        if hasattr(self.model, "n_jobs"):
            self.model.n_jobs = 1
        self.metrics = artifact.get("metrics", {})

    def suspicious_probability(self, features: FeatureVector) -> float:
        row = [[features.get(name, 0.0) for name in FEATURE_NAMES]]
        classes = list(self.model.classes_)
        suspicious_index = classes.index(1)
        return float(self.model.predict_proba(row)[0][suspicious_index])
