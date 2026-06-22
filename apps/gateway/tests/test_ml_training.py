"""Smoke tests for the real ML training and inference path."""

from pathlib import Path

from app.ml.inference import RiskClassifier
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services.feature_extraction import FEATURE_NAMES


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_train_and_load_classifier():
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    artifact = Path(".test-risk-model.joblib")
    try:
        metrics = train_risk_classifier(rows, artifact)
        classifier = RiskClassifier(artifact)

        assert artifact.exists()
        assert metrics.training_rows == 30
        assert metrics.test_rows == 10
        assert classifier.suspicious_probability(_row(1, 20).features) > 0.5
    finally:
        artifact.unlink(missing_ok=True)
