"""Tests for optional ML shadow scoring."""

from types import SimpleNamespace
from pathlib import Path

from app.ml.training import LabeledFeatures, train_risk_classifier
from app.schemas.decision import Decision
from app.services import ml_shadow
from app.services.feature_extraction import FEATURE_NAMES


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_ml_shadow_is_disabled_without_artifact(monkeypatch):
    monkeypatch.setattr(
        ml_shadow,
        "settings",
        SimpleNamespace(
            ml_model_artifact=None,
            ml_shadow_monitor_threshold=0.35,
            ml_shadow_redirect_threshold=0.65,
        ),
    )
    ml_shadow._load_classifier.cache_clear()

    assert ml_shadow.score_ml_shadow({}, heuristic_decision=Decision.ALLOW) is None


def test_ml_shadow_scores_with_valid_artifact(monkeypatch):
    artifact = Path(".test-shadow-risk-model.joblib")
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    try:
        train_risk_classifier(rows, artifact)
        monkeypatch.setattr(
            ml_shadow,
            "settings",
            SimpleNamespace(
                ml_model_artifact=str(artifact),
                ml_shadow_monitor_threshold=0.35,
                ml_shadow_redirect_threshold=0.65,
            ),
        )
        ml_shadow._load_classifier.cache_clear()

        score = ml_shadow.score_ml_shadow(
            _row(1, 20).features,
            heuristic_decision=Decision.REDIRECT_TO_DECOY,
        )

        assert score is not None
        assert score.artifact == ".test-shadow-risk-model.joblib"
        assert score.prediction == "suspicious"
        assert score.score > 50
    finally:
        ml_shadow._load_classifier.cache_clear()
        artifact.unlink(missing_ok=True)
