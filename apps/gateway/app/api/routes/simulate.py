"""Simulation endpoints — generate safe demo events for testing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.schemas.request import InspectRequest
from app.schemas.decision import Decision, InspectResponse
from app.services.anomaly_engine import anomaly_detector
from app.services.decision_engine import make_decision
from app.services.fingerprint import generate_fingerprint
from app.services.logger import log_inspection
from app.services.risk_engine import calculate_risk
from app.services.decoy_engine import _infer_decoy_type

router = APIRouter(prefix="/simulate", tags=["simulate"])


async def _process_simulation(request: InspectRequest) -> InspectResponse:
    """Shared logic for processing a simulated request."""
    fingerprint_hash = generate_fingerprint(
        ip_address=request.ip_address,
        user_agent=request.user_agent,
        path=request.path,
        payload_indicators=request.payload_indicators,
    )
    risk = calculate_risk(request)
    anomaly = anomaly_detector.detect(request)
    if anomaly.signals:
        risk.reasons.extend([f"Anomaly: {s}" for s in anomaly.signals])

    decision = make_decision(
        risk=risk,
        fingerprint_hash=fingerprint_hash,
        is_anomalous=anomaly.is_anomalous,
    )
    await log_inspection(request, risk.score, decision)

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


@router.post("/normal", response_model=InspectResponse)
async def simulate_normal():
    """Generate a safe normal traffic event for demo purposes."""
    request = InspectRequest(
        ip_address="192.168.1.42",
        method="GET",
        path="/api/v1/products",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
        request_count=3,
        payload_indicators=[],
    )
    return await _process_simulation(request)


@router.post("/suspicious", response_model=InspectResponse)
async def simulate_suspicious():
    """Generate a safe suspicious traffic event for demo purposes."""
    request = InspectRequest(
        ip_address="10.0.0.99",
        method="POST",
        path="/.env",
        user_agent="sqlmap/1.7",
        request_count=85,
        payload_indicators=["sql-like", "path-traversal"],
    )
    return await _process_simulation(request)
