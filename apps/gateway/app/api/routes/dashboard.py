"""Dashboard API endpoints."""

from fastapi import APIRouter

from app.schemas.dashboard import DashboardOverview
from app.services.threat_analysis import get_threat_summary
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
async def dashboard_events(limit: int = 50):
    """Recent activity events (newest first)."""
    events = await store.get_recent_events(limit=limit)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/alerts")
async def dashboard_alerts():
    """Active security alerts."""
    alerts = await store.get_alerts()
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
async def dashboard_risk_history(limit: int = 20):
    """Recent risk scores for the sparkline chart."""
    return {"history": await store.get_risk_history(limit=limit)}
