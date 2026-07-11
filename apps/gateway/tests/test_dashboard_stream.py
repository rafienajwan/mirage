"""Tests for dashboard WebSocket stream helpers."""

import asyncio
import json

from types import SimpleNamespace

import pytest

from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.services import actor_clusters, actor_profiles, dashboard_stream
from app.storage.memory_store import MemoryStore
from app.utils.time import utcnow


class FakeWebSocket:
    def __init__(self, fail: bool = False) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("closed")
        self.messages.append(message)


def test_dashboard_stream_auth_requires_dedicated_token(monkeypatch):
    monkeypatch.setattr(
        dashboard_stream,
        "settings",
        SimpleNamespace(
            api_key="operator-key",
            dashboard_stream_token="stream-key",
        ),
    )

    assert dashboard_stream.dashboard_stream_authorized(None) is False
    assert dashboard_stream.dashboard_stream_authorized("operator-key") is False
    assert dashboard_stream.dashboard_stream_authorized("wrong") is False
    assert dashboard_stream.dashboard_stream_authorized("stream-key") is True


def test_dashboard_stream_auth_is_disabled_without_stream_token(monkeypatch):
    monkeypatch.setattr(
        dashboard_stream,
        "settings",
        SimpleNamespace(api_key="operator-key", dashboard_stream_token=None),
    )

    assert dashboard_stream.dashboard_stream_authorized(None) is False
    assert dashboard_stream.dashboard_stream_authorized("operator-key") is False


@pytest.mark.asyncio
async def test_dashboard_stream_broadcasts_and_drops_closed_clients():
    manager = dashboard_stream.DashboardStreamManager()
    live = FakeWebSocket()
    closed = FakeWebSocket(fail=True)

    await manager.connect(live)  # type: ignore[arg-type]
    await manager.connect(closed)  # type: ignore[arg-type]
    await manager.broadcast({"type": "event", "payload": {"event_id": "evt-1"}})
    await manager.broadcast({"type": "alert", "payload": {"alert_id": "alert-1"}})

    assert live.accepted is True
    assert closed.accepted is True
    assert live.messages == [
        {"type": "event", "payload": {"event_id": "evt-1"}},
        {"type": "alert", "payload": {"alert_id": "alert-1"}},
    ]


@pytest.mark.asyncio
async def test_dashboard_stream_snapshot_includes_dashboard_metrics(monkeypatch):
    memory_store = MemoryStore()
    await memory_store.add_event(
        EventRecord(
            event_id="evt-1",
            timestamp=utcnow(),
            ip_address="10.0.0.1",
            path="/api/products",
            method="GET",
            risk_score=5.0,
            decision=Decision.ALLOW,
            event_type="inspection",
            summary="GET /api/products",
        )
    )

    monkeypatch.setattr(dashboard_stream, "store", memory_store)
    monkeypatch.setattr(actor_profiles, "store", memory_store)
    monkeypatch.setattr(actor_clusters, "store", memory_store)

    snapshot = await dashboard_stream.build_dashboard_snapshot()

    assert snapshot["events"][0]["event_id"] == "evt-1"
    assert snapshot["metrics"]["total_requests"] == 1
    assert snapshot["traffic"] == [
        {
            "hour": snapshot["traffic"][0]["hour"],
            "normal": 1,
            "suspicious": 0,
        }
    ]
    assert snapshot["risk_history"][0]["risk_score"] == 5.0
    assert snapshot["decoy_status"]["captured_interactions"] == 0
    assert snapshot["training_summary"]["ready_for_training"] is False
    assert snapshot["ml_shadow_status"]["mode"] in {
        "disabled",
        "missing",
        "invalid",
        "shadow_ready",
    }
    assert snapshot["ml_shadow_summary"]["inspected_events"] == 1
    assert snapshot["honeytokens"] == {"total_hits": 0, "hits": []}
    assert snapshot["canary_assignments"] == {
        "total_assignments": 0,
        "assignments": [],
    }
    assert snapshot["actor_profiles"]["total_actors"] == 1
    assert len(snapshot["actor_profiles"]["profiles"]) == 1
    assert "clusters" in snapshot["actor_clusters"]
    assert "cases" in snapshot["actor_cases"]
    assert snapshot["actor_case_workflows"] == {"total_cases": 0, "cases": []}
    json.dumps(snapshot)


@pytest.mark.asyncio
async def test_snapshot_refresh_coalesces_while_build_is_running():
    started = asyncio.Event()
    release = asyncio.Event()
    builds = 0
    active = 0
    max_active = 0
    messages: list[dict] = []

    async def build_snapshot() -> dict:
        nonlocal builds, active, max_active
        builds += 1
        active += 1
        max_active = max(max_active, active)
        started.set()
        await release.wait()
        active -= 1
        return {"build": builds}

    async def broadcast_update(kind: str, payload: dict) -> None:
        messages.append({"type": kind, "payload": payload})

    coordinator = dashboard_stream.DashboardSnapshotRefreshCoordinator(
        build_snapshot=build_snapshot,
        broadcast_update=broadcast_update,
        debounce_seconds=0,
    )
    task = coordinator.schedule()
    await started.wait()
    assert coordinator.schedule() is task
    assert coordinator.schedule() is task
    release.set()
    await task

    assert builds == 2
    assert max_active == 1
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_snapshot_refresh_recovers_after_build_failure():
    attempts = 0
    messages: list[dict] = []

    async def build_snapshot() -> dict:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("snapshot failed")
        return {"attempt": attempts}

    async def broadcast_update(kind: str, payload: dict) -> None:
        messages.append({"type": kind, "payload": payload})

    coordinator = dashboard_stream.DashboardSnapshotRefreshCoordinator(
        build_snapshot=build_snapshot,
        broadcast_update=broadcast_update,
        debounce_seconds=0,
    )

    await coordinator.schedule()
    await coordinator.schedule()

    assert attempts == 2
    assert messages == [{"type": "snapshot", "payload": {"attempt": 2}}]
