"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.security import require_api_key
from app.schemas.dashboard import DashboardOverview, TrainingDataSummary
from app.schemas.event import EventLabelRequest
from app.services.threat_analysis import get_threat_summary
from app.services.training_export import events_to_jsonl, training_data_summary
from app.storage import store

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview():
    """Aggregate statistics for the security dashboard."""
    return DashboardOverview(
        total_requests=await store.get_total_requests(),
        suspicious_requests=await store.get_suspicious_requests(),
        decoy_redirects=await store.get_decoy_redirects(),
        active_alerts=await store.get_active_alert_count(),
        average_risk_score=round(await store.get_average_risk_score(), 1),
    )


@router.get("/events")
async def dashboard_events(limit: int = Query(default=50, ge=1, le=200)):
    """Recent activity events (newest first)."""
    events = await store.get_recent_events(limit=limit)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.patch(
    "/events/{event_id}/label",
    dependencies=[Depends(require_api_key)],
)
async def label_dashboard_event(event_id: str, payload: EventLabelRequest):
    """Apply an analyst label to an existing event."""
    updated = await store.update_event_label(event_id, payload.label, payload.note)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return updated.model_dump(mode="json")


@router.get(
    "/training-data/export",
    dependencies=[Depends(require_api_key)],
)
async def export_training_data(limit: int = Query(default=10000, ge=1, le=50000)):
    """Export analyst-labeled feature vectors as JSON Lines for model training."""
    events = await store.get_labeled_events(limit=limit)
    return Response(
        content=events_to_jsonl(events),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="training_events.jsonl"',
        },
    )


@router.get(
    "/training-data/summary",
    response_model=TrainingDataSummary,
    dependencies=[Depends(require_api_key)],
)
async def training_data_readiness(limit: int = Query(default=10000, ge=1, le=50000)):
    """Summarize whether analyst labels are sufficient for model training."""
    events = await store.get_labeled_events(limit=limit)
    return training_data_summary(events)


@router.get("/alerts")
async def dashboard_alerts(limit: int = Query(default=100, ge=1, le=200)):
    """Active security alerts."""
    alerts = await store.get_alerts(limit=limit)
    return {"alerts": [a.model_dump(mode="json") for a in alerts]}


@router.get("/threat-analysis")
async def dashboard_threat_analysis():
    """Threat analysis summary from logged events."""
    return await get_threat_summary()


@router.get("/traffic")
async def dashboard_traffic():
    """Traffic breakdown by hour for the traffic chart."""
    return {"traffic": await store.get_traffic_breakdown()}


@router.get("/risk-history")
async def dashboard_risk_history(limit: int = Query(default=20, ge=1, le=200)):
    """Recent risk scores for the sparkline chart."""
    return {"history": await store.get_risk_history(limit=limit)}
