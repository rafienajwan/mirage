"""Route traffic based on risk scores, anomaly data, and optional ML shadow scores."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.decision import Decision, RiskLevel
from app.schemas.ml import MLShadowScore
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
    ml_shadow: MLShadowScore | None = None,
    routing_mode: str | None = None,
    live_routing_approved: bool | None = None,
) -> Decision:
    """Choose allow, monitor, or decoy routing for an inspected request.

    Supports 'heuristic', 'hybrid', and 'ml_only' routing modes.
    """
    mode = (routing_mode or settings.ml_routing_mode or "heuristic").lower()
    approved = (
        settings.ml_live_routing_approved
        if live_routing_approved is None
        else live_routing_approved
    )
    if mode not in {"heuristic", "hybrid", "ml_only"}:
        mode = "heuristic"
    if mode != "heuristic" and not approved:
        mode = "heuristic"
    threshold = settings.risk_threshold

    if fingerprint_hash in _KNOWN_MALICIOUS_FINGERPRINTS:
        return Decision.REDIRECT_TO_DECOY

    # Mode: ml_only (if ML shadow score is available, use ML prediction)
    if mode == "ml_only" and ml_shadow is not None:
        if ml_shadow.shadow_decision == Decision.REDIRECT_TO_DECOY.value:
            return Decision.REDIRECT_TO_DECOY
        if ml_shadow.shadow_decision == Decision.MONITOR.value:
            return Decision.MONITOR
        return Decision.ALLOW

    # Mode: hybrid (combines heuristic risk and ML shadow score)
    if mode == "hybrid" and ml_shadow is not None:
        ml_prob = ml_shadow.probability
        # High/critical risk or high ML probability => REDIRECT
        if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return Decision.REDIRECT_TO_DECOY
        if ml_prob >= settings.ml_shadow_redirect_threshold:
            return Decision.REDIRECT_TO_DECOY
        if risk.score >= threshold and risk.level == RiskLevel.MEDIUM:
            return Decision.REDIRECT_TO_DECOY
        if (
            is_anomalous
            and anomaly_confidence >= settings.anomaly_redirect_confidence
            and risk.level == RiskLevel.MEDIUM
        ):
            return Decision.REDIRECT_TO_DECOY

        # Moderate ML probability or medium risk => MONITOR
        if ml_prob >= settings.ml_shadow_monitor_threshold:
            return Decision.MONITOR
        if risk.level == RiskLevel.MEDIUM or risk.score >= threshold / 2:
            return Decision.MONITOR
        if is_anomalous and anomaly_confidence >= settings.anomaly_redirect_confidence:
            return Decision.MONITOR

        return Decision.ALLOW

    # Default / Fallback Mode: heuristic
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
