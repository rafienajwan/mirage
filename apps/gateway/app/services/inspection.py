"""Shared request inspection workflow used by API, simulation, and proxy routes."""

from __future__ import annotations

import uuid

from app.schemas.decision import Decision, InspectResponse
from app.schemas.request import InspectRequest
from app.services.anomaly_engine import anomaly_detector
from app.services.decision_engine import make_decision
from app.services.decoy_engine import _infer_decoy_type
from app.services.feature_extraction import extract_features
from app.services.fingerprint import generate_fingerprint
from app.services.logger import log_inspection
from app.services.ml_shadow import score_ml_shadow
from app.services.risk_engine import calculate_risk


async def inspect_and_log(
    request: InspectRequest, *, event_type: str = "inspection"
) -> InspectResponse:
    """Inspect request metadata, persist the result, and return the decision."""
    fingerprint_hash = generate_fingerprint(
        ip_address=request.ip_address,
        user_agent=request.user_agent,
        path=request.path,
        payload_indicators=request.payload_indicators,
    )
    feature_vector = extract_features(request)
    risk = calculate_risk(request)
    anomaly = anomaly_detector.detect(request)
    if anomaly.signals:
        risk.reasons.extend([f"Anomaly: {signal}" for signal in anomaly.signals])

    decision = make_decision(
        risk=risk,
        fingerprint_hash=fingerprint_hash,
        is_anomalous=anomaly.is_anomalous,
        anomaly_confidence=anomaly.confidence,
    )
    ml_shadow = score_ml_shadow(feature_vector, heuristic_decision=decision)
    await log_inspection(
        request,
        risk.score,
        decision,
        feature_vector,
        ml_shadow,
        event_type=event_type,
    )

    decoy_type = (
        _infer_decoy_type(request.path)
        if decision == Decision.REDIRECT_TO_DECOY
        else None
    )
    return InspectResponse(
        request_id=str(uuid.uuid4())[:8],
        risk_score=risk.score,
        risk_level=risk.level,
        decision=decision,
        reasons=risk.reasons,
        fingerprint_hash=fingerprint_hash,
        decoy_type=decoy_type,
        ml_shadow=ml_shadow,
    )
