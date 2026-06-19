"""Decision engine — routes traffic based on risk score and anomaly data."""

from __future__ import annotations

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
) -> Decision:
    """Decide what to do with a request.

    Rules:
    - low risk → allow
    - medium risk → monitor
    - high/critical risk → redirect_to_decoy
    - known malicious fingerprint → redirect_to_decoy
    """
    # Known malicious fingerprint always redirects
    if fingerprint_hash in _KNOWN_MALICIOUS_FINGERPRINTS:
        return Decision.REDIRECT_TO_DECOY

    # Risk-level based routing
    if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return Decision.REDIRECT_TO_DECOY

    if risk.level == RiskLevel.MEDIUM:
        return Decision.MONITOR

    return Decision.ALLOW
