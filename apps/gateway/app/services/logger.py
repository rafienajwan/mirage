"""Activity logger — persists inspection events and generates alerts."""

from __future__ import annotations

import uuid

from app.schemas.dashboard import AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.schemas.honeytoken import HoneytokenHit
from app.schemas.ml import MLShadowScore
from app.schemas.request import InspectRequest
from app.services.dashboard_stream import broadcast_dashboard_update
from app.services.honeytoken import HoneytokenMatch
from app.storage import store
from app.utils.time import utcnow


def _mask_ip(ip: str) -> str:
    """Partially anonymize an IP address for logging."""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.***"
    return ip[:8] + "..."


async def log_inspection(
    request: InspectRequest,
    risk_score: float,
    decision: Decision,
    feature_vector: dict[str, float] | None = None,
    ml_shadow: MLShadowScore | None = None,
    *,
    fingerprint_hash: str = "",
    event_type: str = "inspection",
    honeytoken_matches: list[HoneytokenMatch] | None = None,
) -> EventRecord:
    """Log an inspection event and create an alert if needed."""
    event = EventRecord(
        event_id=str(uuid.uuid4())[:8],
        timestamp=utcnow(),
        ip_address=_mask_ip(request.ip_address),
        path=request.path,
        method=request.method,
        risk_score=risk_score,
        decision=decision,
        fingerprint_hash=fingerprint_hash,
        event_type=event_type,
        feature_vector=feature_vector or {},
        ml_shadow=ml_shadow,
        summary=f"{request.method} {request.path} → {decision.value} (score: {risk_score})",
    )
    await store.add_event(event)
    await broadcast_dashboard_update("event", event.model_dump(mode="json"))

    for match in honeytoken_matches or []:
        hit = HoneytokenHit(
            hit_id=str(uuid.uuid4())[:8],
            timestamp=utcnow(),
            event_id=event.event_id,
            token_kind=match.token_kind,
            token_label=match.token_label,
            source_ip=_mask_ip(request.ip_address),
            path=request.path,
            method=request.method,
            evidence=match.evidence,
        )
        await store.add_honeytoken_hit(hit)
        await store.add_alert(
            severity=AlertSeverity.CRITICAL,
            title=f"Honeytoken touched: {match.token_label}",
            description=(
                f"Request from {_mask_ip(request.ip_address)} interacted with "
                f"{match.token_label} on {request.method} {request.path}."
            ),
            recommended_action="Treat as high-confidence deception interaction and review attacker activity.",
        )
        await _broadcast_latest_alert()

    # Create alert for redirected traffic
    if decision == Decision.REDIRECT_TO_DECOY:
        await store.add_alert(
            severity=AlertSeverity.CRITICAL,
            title=f"Decoy redirect: {request.path}",
            description=(
                f"Suspicious request from {_mask_ip(request.ip_address)} "
                f"with risk score {risk_score} was redirected to decoy."
            ),
            recommended_action="Review actor profile and consider IP block.",
        )
        await _broadcast_latest_alert()
    elif decision == Decision.MONITOR:
        await store.add_alert(
            severity=AlertSeverity.WARNING,
            title=f"Monitoring: {request.path}",
            description=(
                f"Request from {_mask_ip(request.ip_address)} flagged for monitoring "
                f"(risk score: {risk_score})."
            ),
            recommended_action="Continue monitoring for escalation.",
        )
        await _broadcast_latest_alert()

    return event


async def _broadcast_latest_alert() -> None:
    alerts = await store.get_alerts(limit=1)
    if alerts:
        await broadcast_dashboard_update("alert", alerts[0].model_dump(mode="json"))
