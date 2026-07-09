"""Tests for dashboard WebSocket stream helpers."""

from types import SimpleNamespace

import pytest

from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.services import dashboard_stream
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


def test_dashboard_stream_auth_requires_token_when_api_key_is_configured(monkeypatch):
    monkeypatch.setattr(
        dashboard_stream,
        "settings",
        SimpleNamespace(api_key="operator-key"),
    )

    assert dashboard_stream.dashboard_stream_authorized(None) is False
    assert dashboard_stream.dashboard_stream_authorized("wrong") is False
    assert dashboard_stream.dashboard_stream_authorized("operator-key") is True


def test_dashboard_stream_auth_allows_dev_without_api_key(monkeypatch):
    monkeypatch.setattr(
        dashboard_stream,
        "settings",
        SimpleNamespace(api_key=None),
    )

    assert dashboard_stream.dashboard_stream_authorized(None) is True


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
