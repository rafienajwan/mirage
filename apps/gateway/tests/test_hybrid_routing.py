"""Tests for hybrid and ML-only routing modes in decision engine."""

from app.schemas.decision import Decision, RiskLevel
from app.schemas.ml import MLShadowScore
from app.services.decision_engine import make_decision
from app.services.risk_engine import RiskResult


def _mock_ml_shadow(probability: float, shadow_decision: str) -> MLShadowScore:
    return MLShadowScore(
        artifact="test_model.joblib",
        probability=probability,
        score=round(probability * 100, 2),
        prediction="suspicious" if probability >= 0.5 else "normal",
        shadow_decision=shadow_decision,  # type: ignore
        agrees_with_decision=True,
    )


def test_heuristic_mode_ignores_ml_score():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    ml_shadow = _mock_ml_shadow(probability=0.9, shadow_decision="redirect_to_decoy")

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=ml_shadow,
        routing_mode="heuristic",
    )
    assert decision == Decision.ALLOW


def test_hybrid_mode_promotes_high_ml_probability_to_decoy():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    ml_shadow = _mock_ml_shadow(probability=0.8, shadow_decision="redirect_to_decoy")

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=ml_shadow,
        routing_mode="hybrid",
    )
    assert decision == Decision.REDIRECT_TO_DECOY


def test_hybrid_mode_promotes_moderate_ml_probability_to_monitor():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    ml_shadow = _mock_ml_shadow(probability=0.45, shadow_decision="monitor")

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=ml_shadow,
        routing_mode="hybrid",
    )
    assert decision == Decision.MONITOR


def test_hybrid_mode_allows_low_ml_and_low_risk():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    ml_shadow = _mock_ml_shadow(probability=0.1, shadow_decision="allow")

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=ml_shadow,
        routing_mode="hybrid",
    )
    assert decision == Decision.ALLOW


def test_ml_only_mode_follows_model_prediction():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    ml_shadow = _mock_ml_shadow(probability=0.75, shadow_decision="redirect_to_decoy")

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=ml_shadow,
        routing_mode="ml_only",
    )
    assert decision == Decision.REDIRECT_TO_DECOY


def test_ml_only_mode_falls_back_if_no_model():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])

    decision = make_decision(
        risk,
        fingerprint_hash="abc",
        is_anomalous=False,
        ml_shadow=None,
        routing_mode="ml_only",
    )
    assert decision == Decision.ALLOW
