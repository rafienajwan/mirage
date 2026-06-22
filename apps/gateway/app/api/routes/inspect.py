"""Request inspection endpoint."""

import uuid

from fastapi import APIRouter, Depends

from app.schemas.decision import Decision, InspectResponse
from app.schemas.request import InspectRequest
from app.services.anomaly_engine import anomaly_detector
from app.services.decision_engine import make_decision
from app.services.fingerprint import generate_fingerprint
from app.services.logger import log_inspection
from app.services.risk_engine import calculate_risk
from app.services.decoy_engine import _infer_decoy_type
from app.services.feature_extraction import extract_features
from app.core.security import require_api_key

router = APIRouter()


@router.post(
    "/inspect",
    response_model=InspectResponse,
    dependencies=[Depends(require_api_key)],
)
async def inspect_request(request: InspectRequest):
    """Inspect a simulated API request and return a security decision."""
    # 1. Generate fingerprint
    fingerprint_hash = generate_fingerprint(
        ip_address=request.ip_address,
        user_agent=request.user_agent,
        path=request.path,
        payload_indicators=request.payload_indicators,
    )

    # 2. Calculate risk score
    feature_vector = extract_features(request)
    risk = calculate_risk(request)

    # 3. Detect anomalies
    anomaly = anomaly_detector.detect(request)
    if anomaly.signals:
        risk.reasons.extend([f"Anomaly: {s}" for s in anomaly.signals])

    # 4. Make decision
    decision = make_decision(
        risk=risk,
        fingerprint_hash=fingerprint_hash,
        is_anomalous=anomaly.is_anomalous,
        anomaly_confidence=anomaly.confidence,
    )

    # 5. Log the inspection
    await log_inspection(request, risk.score, decision, feature_vector)

    # 6. Determine decoy type if redirecting
    decoy_type = None
    if decision == Decision.REDIRECT_TO_DECOY:
        decoy_type = _infer_decoy_type(request.path)

    return InspectResponse(
        request_id=str(uuid.uuid4())[:8],
        risk_score=risk.score,
        risk_level=risk.level,
        decision=decision,
        reasons=risk.reasons,
        fingerprint_hash=fingerprint_hash,
        decoy_type=decoy_type,
    )
