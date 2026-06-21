"""Decision engine — routes traffic based on risk score and anomaly data."""

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
    """Decide what to do with a request.

    The redirect threshold is configurable via RISK_THRESHOLD (default 60).

    Rules:
    - known malicious fingerprint → redirect_to_decoy
    - risk level HIGH/CRITICAL → redirect_to_decoy
    - score ≥ threshold + medium risk → redirect_to_decoy
    - anomalous with high confidence (≥0.75) + medium risk → redirect_to_decoy
    - anomalous with high confidence (≥0.75) + low risk → monitor
    - medium risk → monitor
    - score ≥ threshold/2 → monitor
    - else → allow
    """
    threshold = settings.risk_threshold

    # Known malicious fingerprint always redirects
    if fingerprint_hash in _KNOWN_MALICIOUS_FINGERPRINTS:
        return Decision.REDIRECT_TO_DECOY

    # Risk-level based routing
    if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return Decision.REDIRECT_TO_DECOY

    # Score-based override: if score exceeds threshold, escalate to decoy
    if risk.score >= threshold and risk.level == RiskLevel.MEDIUM:
        return Decision.REDIRECT_TO_DECOY

    # Anomaly escalation: high-confidence anomaly + medium risk → redirect
    if is_anomalous and anomaly_confidence >= 0.75 and risk.level == RiskLevel.MEDIUM:
        return Decision.REDIRECT_TO_DECOY

    if risk.level == RiskLevel.MEDIUM:
        return Decision.MONITOR

    # Score-based monitor: if score is above half threshold, monitor
    if risk.score >= threshold / 2:
        return Decision.MONITOR

    # Anomaly escalation: high-confidence anomaly on low-risk request → monitor
    if is_anomalous and anomaly_confidence >= 0.75:
        return Decision.MONITOR

    return Decision.ALLOW
