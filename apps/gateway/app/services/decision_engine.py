"""Route traffic based on risk scores and anomaly data."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.decision import Decision, RiskLevel
from app.services.risk_engine import RiskResult


# Known malicious fingerprints (demo only)
_KNOWN_MALICIOUS_FINGERPRINTS: set[str] = set()


def register_malicious_fingerprint(fingerprint: str) -> None:
    """Mark a fingerprint as known-malicious for future requests."""
    _KNOWN_MALICIOUS_FINGERPRINTS.add(fingerprint)


def make_decision(
    risk: RiskResult,
    fingerprint_hash: str,
    is_anomalous: bool,
    anomaly_confidence: float = 0.0,
) -> Decision:
    """Choose allow, monitor, or decoy routing for an inspected request.

    Risk and anomaly thresholds are configurable through application settings.
    """
    threshold = settings.risk_threshold

    if fingerprint_hash in _KNOWN_MALICIOUS_FINGERPRINTS:
        return Decision.REDIRECT_TO_DECOY

    if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return Decision.REDIRECT_TO_DECOY

    if risk.score >= threshold and risk.level == RiskLevel.MEDIUM:
        return Decision.REDIRECT_TO_DECOY

    if (
        is_anomalous
        and anomaly_confidence >= settings.anomaly_redirect_confidence
        and risk.level == RiskLevel.MEDIUM
    ):
        return Decision.REDIRECT_TO_DECOY

    if risk.level == RiskLevel.MEDIUM:
        return Decision.MONITOR

    if risk.score >= threshold / 2:
        return Decision.MONITOR

    if is_anomalous and anomaly_confidence >= settings.anomaly_redirect_confidence:
        return Decision.MONITOR

    return Decision.ALLOW
