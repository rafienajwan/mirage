"""Authenticated dashboard WebSocket stream."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.services.dashboard_stream import (
    build_dashboard_snapshot,
    dashboard_stream,
    dashboard_stream_authorized,
    dashboard_stream_origin_authorized,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.websocket("/ws")
async def dashboard_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Stream new dashboard events and alerts to authenticated operators."""
    if not dashboard_stream_origin_authorized(
        websocket.headers.get("origin")
    ) or not dashboard_stream_authorized(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await dashboard_stream.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "payload": await build_dashboard_snapshot(),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_stream.disconnect(websocket)
    except RuntimeError:
        dashboard_stream.disconnect(websocket)
