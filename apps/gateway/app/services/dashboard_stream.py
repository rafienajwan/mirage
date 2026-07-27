"""Authenticated dashboard WebSocket stream helpers."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket

from app.core.config import settings
from app.services.decoy_engine import FAKE_ENDPOINTS
from app.services.actor_clusters import (
    get_actor_case_workflows,
    get_actor_cases,
    get_actor_clusters,
)
from app.services.actor_profiles import get_actor_profiles
from app.services.ml_shadow_summary import summarize_ml_shadow_events
from app.services.ml_promotion import evaluate_ml_promotion
from app.services.ml_status import get_ml_shadow_status
from app.services.training_export import training_data_summary
from app.storage import store

logger = logging.getLogger(__name__)

SnapshotBuilder = Callable[[], Awaitable[dict[str, Any]]]
DashboardBroadcaster = Callable[[str, dict[str, Any]], Awaitable[None]]


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


def _decode_ticket_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _dashboard_ticket_authorized(
    token: str,
    secret: str,
    *,
    now: int,
) -> bool:
    if len(secret) < 32:
        return False
    try:
        payload_segment, signature_segment = token.split(".")
        supplied_signature = _decode_ticket_segment(signature_segment)
        expected_signature = hmac.new(
            secret.encode(),
            payload_segment.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False
        payload = json.loads(_decode_ticket_segment(payload_segment))
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
    if not isinstance(payload, dict):
        return False

    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    nonce = payload.get("nonce")
    if (
        payload.get("aud") != "mirage-dashboard-stream"
        or not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or not isinstance(nonce, str)
        or len(nonce) < 16
    ):
        return False
    return (
        issued_at - 5 <= now < expires_at
        and 0 < expires_at - issued_at <= 120
    )


def dashboard_stream_authorized(
    token: str | None,
    *,
    now: int | None = None,
) -> bool:
    """Validate a short-lived production ticket or local legacy token."""
    if token is None:
        return False

    ticket_secret = getattr(settings, "dashboard_stream_ticket_secret", None)
    if ticket_secret and _dashboard_ticket_authorized(
        token,
        ticket_secret,
        now=int(time.time()) if now is None else now,
    ):
        return True

    if getattr(settings, "app_env", "development").lower() == "production":
        return False
    expected = settings.dashboard_stream_token
    if expected is None:
        return False
    return secrets.compare_digest(token, expected)


def dashboard_stream_origin_authorized(origin: str | None) -> bool:
    """Accept dashboard sockets only from the configured browser origin."""
    expected = settings.frontend_origin.rstrip("/")
    if not origin or not expected:
        return False
    return secrets.compare_digest(origin.rstrip("/"), expected)


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
    honeytoken_hits = await store.get_honeytoken_hits(limit=20)
    canary_assignments = await store.get_canary_assignments(limit=50)
    actor_profiles = await get_actor_profiles(limit=20)
    actor_clusters = await get_actor_clusters(limit=20)
    actor_cases = await get_actor_cases(limit=20)
    actor_case_workflows = await get_actor_case_workflows(limit=20)
    shadow_summary = summarize_ml_shadow_events(
        await store.get_recent_events(limit=1000)
    )

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
        "ml_shadow_summary": shadow_summary.model_dump(mode="json"),
        "ml_promotion_readiness": evaluate_ml_promotion(
            shadow_summary=shadow_summary
        ).model_dump(mode="json"),
        "honeytokens": {
            "total_hits": await store.get_honeytoken_hit_count(),
            "hits": [item.model_dump(mode="json") for item in honeytoken_hits],
        },
        "canary_assignments": {
            "total_assignments": len(canary_assignments),
            "assignments": [
                item.model_dump(mode="json") for item in canary_assignments
            ],
        },
        "actor_profiles": actor_profiles.model_dump(mode="json"),
        "actor_clusters": actor_clusters.model_dump(mode="json"),
        "actor_cases": actor_cases.model_dump(mode="json"),
        "actor_case_workflows": actor_case_workflows.model_dump(mode="json"),
    }


class DashboardSnapshotRefreshCoordinator:
    """Coalesce non-blocking dashboard snapshot refresh requests."""

    def __init__(
        self,
        *,
        build_snapshot: SnapshotBuilder = build_dashboard_snapshot,
        broadcast_update: DashboardBroadcaster = broadcast_dashboard_update,
        debounce_seconds: float = 0.1,
    ) -> None:
        self._build_snapshot = build_snapshot
        self._broadcast_update = broadcast_update
        self._debounce_seconds = debounce_seconds
        self._pending = False
        self._task: asyncio.Task[None] | None = None

    def schedule(self) -> asyncio.Task[None]:
        """Schedule one refresh and return the retained background task."""
        self._pending = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self._task

    async def _run(self) -> None:
        try:
            await asyncio.sleep(self._debounce_seconds)
            while self._pending:
                self._pending = False
                try:
                    snapshot = await self._build_snapshot()
                    await self._broadcast_update("snapshot", snapshot)
                except Exception:
                    logger.exception("Dashboard snapshot refresh failed")
                if self._pending:
                    await asyncio.sleep(self._debounce_seconds)
        finally:
            self._task = None


dashboard_snapshot_refresh = DashboardSnapshotRefreshCoordinator()


def schedule_dashboard_snapshot_refresh() -> asyncio.Task[None]:
    """Schedule a coalesced dashboard snapshot refresh."""
    return dashboard_snapshot_refresh.schedule()
