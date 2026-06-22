"""Validated loading and inference for trained MIRAGE artifacts."""

from __future__ import annotations

from pathlib import Path

import joblib

from app.services.feature_extraction import FEATURE_NAMES, FeatureVector


class RiskClassifier:
    def __init__(self, artifact_path: Path) -> None:
        artifact = joblib.load(artifact_path)
        if tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
            raise ValueError("Model feature contract does not match the gateway")
        self.model = artifact["model"]
        self.metrics = artifact.get("metrics", {})

    def suspicious_probability(self, features: FeatureVector) -> float:
        row = [[features.get(name, 0.0) for name in FEATURE_NAMES]]
        classes = list(self.model.classes_)
        suspicious_index = classes.index(1)
        return float(self.model.predict_proba(row)[0][suspicious_index])
