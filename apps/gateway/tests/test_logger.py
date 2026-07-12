"""Tests for inspection event logging side effects."""

import pytest

from app.schemas.decision import Decision
from app.schemas.request import InspectRequest
from app.services import logger


@pytest.mark.asyncio
async def test_log_inspection_broadcasts_event_then_schedules_snapshot(monkeypatch):
    calls: list[str] = []

    async def fake_broadcast_dashboard_update(kind: str, payload: dict) -> None:
        calls.append(kind)

    def fake_schedule_dashboard_snapshot_refresh() -> None:
        calls.append("snapshot")

    monkeypatch.setattr(
        logger,
        "broadcast_dashboard_update",
        fake_broadcast_dashboard_update,
    )
    monkeypatch.setattr(
        logger,
        "schedule_dashboard_snapshot_refresh",
        fake_schedule_dashboard_snapshot_refresh,
    )

    await logger.log_inspection(
        InspectRequest(
            ip_address="10.0.0.1",
            method="GET",
            path="/api/products",
            user_agent="Mozilla/5.0",
        ),
        risk_score=5.0,
        decision=Decision.ALLOW,
    )

    assert calls == ["event", "snapshot"]
