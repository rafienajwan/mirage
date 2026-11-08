"""Tests for optional ML shadow scoring."""

from pathlib import Path
from types import SimpleNamespace

from fastapi.responses import JSONResponse
import joblib

from app.api.routes import proxy as proxy_route
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
            ml_model_artifact_sha256=None,
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
                ml_model_artifact_sha256=None,
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


def test_ml_shadow_rejects_artifact_that_fails_review(monkeypatch):
    artifact = Path(".test-invalid-shadow-risk-model.joblib")
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    try:
        train_risk_classifier(rows, artifact)
        payload = joblib.load(artifact)
        payload["metrics"] = {}
        joblib.dump(payload, artifact)
        monkeypatch.setattr(
            ml_shadow,
            "settings",
            SimpleNamespace(
                ml_model_artifact_sha256=None,
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

        assert score is None
    finally:
        ml_shadow._load_classifier.cache_clear()
        artifact.unlink(missing_ok=True)


async def test_v2_artifact_disables_shadow_scoring(client, monkeypatch):
    artifact = Path(".test-v2-shadow-risk-model.joblib")
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    try:
        train_risk_classifier(rows, artifact)
        payload = joblib.load(artifact)
        payload["feature_contract_version"] = 2
        joblib.dump(payload, artifact)
        monkeypatch.setattr(
            ml_shadow,
            "settings",
            SimpleNamespace(
                ml_model_artifact_sha256=None,
                ml_model_artifact=str(artifact),
                ml_shadow_monitor_threshold=0.35,
                ml_shadow_redirect_threshold=0.65,
            ),
        )
        ml_shadow._load_classifier.cache_clear()

        assert ml_shadow._load_classifier() is None

        async def fake_forward(request, **kwargs):
            return JSONResponse({"route": "real"})

        monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
        response = await client.get(
            "/api/v1/proxy/api/products",
            headers={"user-agent": "Mozilla/5.0"},
        )
        assert response.status_code == 200
    finally:
        ml_shadow._load_classifier.cache_clear()
        artifact.unlink(missing_ok=True)
