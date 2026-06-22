"""Activity logger — persists inspection events and generates alerts."""

from __future__ import annotations

import uuid

from app.schemas.dashboard import AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.schemas.request import InspectRequest
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
    *,
    event_type: str = "inspection",
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
        event_type=event_type,
        feature_vector=feature_vector or {},
        summary=f"{request.method} {request.path} → {decision.value} (score: {risk_score})",
    )
    await store.add_event(event)

    # Create alert for redirected traffic
    if decision == Decision.REDIRECT_TO_DECOY:
        await store.add_alert(
            severity=AlertSeverity.CRITICAL,
            title=f"Decoy redirect: {request.path}",
            description=(
                f"Suspicious request from {_mask_ip(request.ip_address)} "
                f"with risk score {risk_score} was redirected to decoy."
            ),
            recommended_action="Review threat fingerprint and consider IP block.",
        )
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

    return event
