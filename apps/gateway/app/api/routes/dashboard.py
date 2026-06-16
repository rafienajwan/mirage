"""Dashboard API endpoints."""

from fastapi import APIRouter

from app.schemas.dashboard import DashboardOverview
from app.services.threat_analysis import get_threat_summary
from app.storage.memory_store import store

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview():
    """Aggregate statistics for the security dashboard."""
    return DashboardOverview(
        total_requests=store.total_requests,
        suspicious_requests=store.suspicious_requests,
        decoy_redirects=store.decoy_redirects,
        active_alerts=store.active_alert_count,
        average_risk_score=round(store.average_risk_score, 1),
    )


@router.get("/events")
async def dashboard_events(limit: int = 50):
    """Recent activity events (newest first)."""
    events = store.get_recent_events(limit=limit)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/alerts")
async def dashboard_alerts():
    """Active security alerts."""
    alerts = store.get_alerts()
    return {"alerts": [a.model_dump(mode="json") for a in alerts]}


@router.get("/threat-analysis")
async def dashboard_threat_analysis():
    """Threat analysis summary from logged events."""
    return get_threat_summary()
