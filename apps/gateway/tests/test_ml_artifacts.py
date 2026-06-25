"""Tests for trained model artifact review."""

from pathlib import Path

import joblib

from app.ml.artifacts import review_model_artifact
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services.feature_extraction import FEATURE_NAMES


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_review_model_artifact_marks_valid_shadow_ready(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    train_risk_classifier(rows, artifact)

    review = review_model_artifact(artifact)

    assert review.shadow_ready is True
    assert review.artifact_version == 1
    assert review.blockers == []
    assert review.metrics["training_rows"] == 30
    assert review.metrics["test_rows"] == 10


def test_review_model_artifact_rejects_feature_contract_mismatch(tmp_path):
    artifact = tmp_path / "bad_model.joblib"
    joblib.dump(
        {
            "artifact_version": 1,
            "feature_names": ("unexpected",),
            "metrics": {
                "precision": 1.0,
                "recall": 1.0,
                "f1_score": 1.0,
                "false_positive_rate": 0.0,
                "training_rows": 30,
                "test_rows": 10,
            },
            "model": object(),
        },
        artifact,
    )

    review = review_model_artifact(artifact)

    assert review.shadow_ready is False
    assert "Artifact feature contract does not match the gateway" in review.blockers


def test_review_model_artifact_reports_missing_file(tmp_path):
    review = review_model_artifact(Path(tmp_path / "missing.joblib"))

    assert review.shadow_ready is False
    assert review.blockers == ["Artifact file does not exist"]
