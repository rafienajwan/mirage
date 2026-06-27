"""Authenticated dashboard WebSocket stream."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.services.dashboard_stream import (
    dashboard_stream,
    dashboard_stream_authorized,
)
from app.storage import store

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.websocket("/ws")
async def dashboard_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Stream new dashboard events and alerts to authenticated operators."""
    if not dashboard_stream_authorized(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await dashboard_stream.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "payload": {
                    "events": [
                        item.model_dump(mode="json")
                        for item in await store.get_recent_events(limit=20)
                    ],
                    "alerts": [
                        item.model_dump(mode="json")
                        for item in await store.get_alerts(limit=20)
                    ],
                },
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_stream.disconnect(websocket)
    except RuntimeError:
        dashboard_stream.disconnect(websocket)
