"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.security import require_api_key
from app.schemas.dashboard import (
    ActorCaseSummary,
    ActorCaseWorkflowSummary,
    DashboardOverview,
    ActorClusterSummary,
    ActorProfileSummary,
    HoneytokenSummary,
    MLShadowStatus,
    TrainingDataSummary,
)
from app.schemas.actor import ActorCaseOpenRequest, ActorCaseUpdateRequest
from app.schemas.event import EventLabelRequest
from app.schemas.retraining import RetrainingRun
from app.services.ml_status import get_ml_shadow_status
from app.services.actor_clusters import (
    get_actor_cases,
    get_actor_clusters,
    get_filtered_actor_case_workflows,
    open_actor_case_from_recommendation,
    update_actor_case_workflow,
)
from app.services.actor_profiles import get_actor_profiles
from app.services.retraining import train_from_labeled_events
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


@router.post(
    "/training-data/retrain",
    response_model=RetrainingRun,
    dependencies=[Depends(require_api_key)],
)
async def retrain_from_training_data(
    limit: int = Query(default=10000, ge=20, le=50000),
):
    """Train a local shadow-mode candidate from analyst-labeled events."""
    return await train_from_labeled_events(limit=limit)


@router.get("/ml-shadow/status", response_model=MLShadowStatus)
async def ml_shadow_status():
    """Current artifact and threshold status for model-only shadow scoring."""
    return get_ml_shadow_status()


@router.get("/honeytokens", response_model=HoneytokenSummary)
async def dashboard_honeytokens(limit: int = Query(default=20, ge=1, le=100)):
    """Recent interactions with decoy tokens."""
    hits = await store.get_honeytoken_hits(limit=limit)
    return {
        "total_hits": await store.get_honeytoken_hit_count(),
        "hits": [hit.model_dump(mode="json") for hit in hits],
    }


@router.get("/actors", response_model=ActorProfileSummary)
async def dashboard_actors(limit: int = Query(default=20, ge=1, le=100)):
    """Recent actor profiles from fingerprints, events, and honeytokens."""
    return await get_actor_profiles(limit=limit)


@router.get("/actor-clusters", response_model=ActorClusterSummary)
async def dashboard_actor_clusters(limit: int = Query(default=20, ge=1, le=100)):
    """Lightweight actor clusters for threat-hunting triage."""
    return await get_actor_clusters(limit=limit)


@router.get("/actor-cases", response_model=ActorCaseSummary)
async def dashboard_actor_cases(limit: int = Query(default=20, ge=1, le=100)):
    """Read-only recommended cases derived from actor clusters."""
    return await get_actor_cases(limit=limit)


@router.get("/actor-case-workflows", response_model=ActorCaseWorkflowSummary)
async def dashboard_actor_case_workflows(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to: str | None = Query(default=None, max_length=120),
):
    """Persisted actor case workflow records."""
    return await get_filtered_actor_case_workflows(
        limit=limit,
        status=status_filter,
        assigned_to=assigned_to,
    )


@router.post(
    "/actor-cases/{case_id}/open",
    dependencies=[Depends(require_api_key)],
)
async def open_dashboard_actor_case(case_id: str, payload: ActorCaseOpenRequest):
    """Open a recommended actor case as a persisted workflow record."""
    opened = await open_actor_case_from_recommendation(case_id, payload)
    if opened is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommended actor case not found",
        )
    return opened.model_dump(mode="json")


@router.patch(
    "/actor-case-workflows/{case_id}",
    dependencies=[Depends(require_api_key)],
)
async def update_dashboard_actor_case(case_id: str, payload: ActorCaseUpdateRequest):
    """Update a persisted actor case workflow status."""
    updated = await update_actor_case_workflow(case_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor case workflow not found",
        )
    return updated.model_dump(mode="json")


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
