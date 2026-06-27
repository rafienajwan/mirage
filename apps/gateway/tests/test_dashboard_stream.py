"""Tests for dashboard WebSocket stream helpers."""

from types import SimpleNamespace

import pytest

from app.services import dashboard_stream


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
