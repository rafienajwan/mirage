"""Authenticated dashboard WebSocket stream helpers."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import WebSocket

from app.core.config import settings
from app.services.decoy_engine import FAKE_ENDPOINTS
from app.services.ml_shadow_summary import summarize_ml_shadow_events
from app.services.ml_status import get_ml_shadow_status
from app.services.training_export import training_data_summary
from app.storage import store


class DashboardStreamManager:
    """Track connected dashboard WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for client in list(self._clients):
            try:
                await client.send_json(message)
            except RuntimeError:
                stale.append(client)
        for client in stale:
            self.disconnect(client)


dashboard_stream = DashboardStreamManager()


def dashboard_stream_authorized(token: str | None) -> bool:
    """Validate a browser WebSocket token against the operator API key."""
    if settings.api_key is None:
        return True
    return token is not None and secrets.compare_digest(token, settings.api_key)


async def broadcast_dashboard_update(kind: str, payload: dict[str, Any]) -> None:
    """Broadcast a dashboard update to connected clients."""
    await dashboard_stream.broadcast({"type": kind, "payload": payload})


async def broadcast_dashboard_snapshot() -> None:
    """Broadcast a refreshed dashboard snapshot to connected clients."""
    await broadcast_dashboard_update("snapshot", await build_dashboard_snapshot())


async def build_dashboard_snapshot() -> dict[str, Any]:
    """Build the initial dashboard WebSocket snapshot payload."""
    recent_events = await store.get_recent_events(limit=20)
    recent_alerts = await store.get_alerts(limit=20)
    labeled_events = await store.get_labeled_events(limit=10000)
    last_decoy_trigger = await store.get_last_decoy_trigger()

    return {
        "events": [item.model_dump(mode="json") for item in recent_events],
        "alerts": [item.model_dump(mode="json") for item in recent_alerts],
        "metrics": {
            "total_requests": await store.get_total_requests(),
            "suspicious_requests": await store.get_suspicious_requests(),
            "decoy_redirects": await store.get_decoy_redirects(),
            "active_alerts": await store.get_active_alert_count(),
            "average_risk_score": round(await store.get_average_risk_score(), 1),
        },
        "traffic": await store.get_traffic_breakdown(),
        "risk_history": await store.get_risk_history(limit=20),
        "decoy_status": {
            "active_decoys": len(FAKE_ENDPOINTS),
            "fake_endpoints": FAKE_ENDPOINTS,
            "captured_interactions": await store.get_decoy_redirects(),
            "last_decoy_trigger": (
                last_decoy_trigger.isoformat() if last_decoy_trigger else None
            ),
        },
        "training_summary": training_data_summary(labeled_events),
        "ml_shadow_status": get_ml_shadow_status(),
        "ml_shadow_summary": summarize_ml_shadow_events(
            await store.get_recent_events(limit=200)
        ).model_dump(mode="json"),
    }
