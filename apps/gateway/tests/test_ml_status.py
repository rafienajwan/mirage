"""Tests for ML shadow status reporting."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services import ml_status
from app.services.feature_extraction import FEATURE_NAMES


def _settings(artifact: str | None):
    return SimpleNamespace(
        ml_model_artifact=artifact,
        ml_shadow_monitor_threshold=0.35,
        ml_shadow_redirect_threshold=0.65,
    )


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_ml_shadow_status_disabled(monkeypatch):
    monkeypatch.setattr(ml_status, "settings", _settings(None))

    status = ml_status.get_ml_shadow_status()

    assert status["mode"] == "disabled"
    assert status["shadow_ready"] is False
    assert status["artifact"] is None


def test_ml_shadow_status_missing_artifact(monkeypatch, tmp_path):
    missing = tmp_path / "missing.joblib"
    monkeypatch.setattr(ml_status, "settings", _settings(str(missing)))

    status = ml_status.get_ml_shadow_status()

    assert status["mode"] == "missing"
    assert status["artifact"] == "missing.joblib"
    assert status["shadow_ready"] is False


def test_ml_shadow_status_ready_artifact(monkeypatch, tmp_path):
    artifact = Path(tmp_path / "risk_model.joblib")
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    train_risk_classifier(rows, artifact)
    monkeypatch.setattr(ml_status, "settings", _settings(str(artifact)))

    status = ml_status.get_ml_shadow_status()

    assert status["mode"] == "shadow_ready"
    assert status["artifact"] == "risk_model.joblib"
    assert status["shadow_ready"] is True
    assert status["metrics"]["training_rows"] == 30
