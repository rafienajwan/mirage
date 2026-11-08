"""Tests for inspection event logging side effects."""

import asyncio

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


def _request(path: str = "/.env") -> InspectRequest:
    return InspectRequest(ip_address="10.0.0.1", method="GET", path=path, user_agent="curl/8.5.0")


async def test_concurrent_alerts_and_events_get_unique_ids():
    from app.schemas.dashboard import AlertSeverity
    from app.storage import store

    alerts = await asyncio.gather(
        *(
            store.add_alert(
                severity=AlertSeverity.WARNING,
                title=f"alert {index}",
                description="",
                recommended_action="",
            )
            for index in range(20)
        )
    )
    stored = await store.get_alerts(limit=100)
    assert len({alert.alert_id for alert in stored}) == 20
    assert {alert.alert_id for alert in alerts} == {alert.alert_id for alert in stored}

    events = [
        await logger.log_inspection(_request(), risk_score=5.0, decision=Decision.ALLOW)
        for _ in range(50)
    ]
    # Full 128-bit ids: 8 hex characters collide by the birthday bound.
    assert all(len(event.event_id) == 32 for event in events)
    assert len({event.event_id for event in events}) == 50


async def test_log_inspection_broadcasts_the_alert_it_created(monkeypatch):
    from app.schemas.dashboard import AlertSeverity
    from app.storage import store

    broadcast: list[dict] = []

    async def capture(kind: str, payload: dict) -> None:
        if kind == "alert":
            broadcast.append(payload)

    original_add_alert = store.add_alert

    async def add_alert_then_another_request_adds_one(**kwargs):
        created = await original_add_alert(**kwargs)
        await original_add_alert(
            severity=AlertSeverity.WARNING,
            title="Concurrent request alert",
            description="",
            recommended_action="",
        )
        return created

    monkeypatch.setattr(logger, "broadcast_dashboard_update", capture)
    monkeypatch.setattr(store, "add_alert", add_alert_then_another_request_adds_one)

    await logger.log_inspection(_request(), risk_score=90.0, decision=Decision.REDIRECT_TO_DECOY)

    assert [alert["title"] for alert in broadcast] == ["Decoy redirect: /.env"]
