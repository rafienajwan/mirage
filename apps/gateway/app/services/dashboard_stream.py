"""Authenticated dashboard WebSocket stream helpers."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import WebSocket

from app.core.config import settings


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
