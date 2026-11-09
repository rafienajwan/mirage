"""DatabaseStore aggregates: actor path counts and the traffic chart."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.schemas.dashboard import AlertSeverity
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.storage import store
from app.storage.db.database import get_session
from app.storage.db.models import ActorProfileModel
from app.storage.memory_store import MemoryStore
from app.utils.time import utcnow


def _event(path: str = "/api/products", **overrides) -> EventRecord:
    fields = {
        "event_id": uuid4().hex,
        "timestamp": utcnow(),
        "ip_address": "10.0.***.***",
        "path": path,
        "method": "GET",
        "risk_score": 5.0,
        "decision": Decision.ALLOW,
        "fingerprint_hash": "actor-fingerprint",
        "summary": "",
    }
    fields.update(overrides)
    return EventRecord(**fields)


async def test_actor_path_counts_stop_adding_paths_at_fifty():
    for index in range(60):
        await store.add_event(_event(f"/scan/{index}"))
    await store.add_event(_event("/scan/0"))

    async with get_session() as session:
        profile = (await session.execute(select(ActorProfileModel))).scalar_one()
    assert len(profile.path_counts) == 50
    assert profile.path_counts["/scan/0"] == 2
    assert "/scan/55" not in profile.path_counts
    assert profile.request_count == 61


@pytest.mark.parametrize("backend", [store, MemoryStore()], ids=["database", "memory"])
async def test_traffic_breakdown_only_counts_the_last_twelve_hours(backend):
    now = utcnow()
    await backend.add_event(_event(timestamp=now))
    await backend.add_event(_event(timestamp=now - timedelta(days=1)))

    breakdown = await backend.get_traffic_breakdown()

    assert sum(row["normal"] + row["suspicious"] for row in breakdown) == 1


async def test_stored_timestamps_read_back_as_utc():
    # Pushed alerts carry an aware timestamp; polled ones are read back from
    # the database. Both must serialize the same way, or a browser parses the
    # naive one as local time.
    created = await store.add_alert(
        severity=AlertSeverity.WARNING,
        title="t",
        description="d",
        recommended_action="r",
    )
    polled = (await store.get_alerts(limit=1))[0]
    assert polled.created_at.tzinfo is not None
    assert polled.model_dump(mode="json")["created_at"] == created.model_dump(mode="json")[
        "created_at"
    ]

    await store.add_event(_event())
    event = (await store.get_recent_events(limit=1))[0]
    assert event.timestamp.tzinfo is not None


@pytest.mark.parametrize("backend", [store, MemoryStore()], ids=["database", "memory"])
async def test_labeled_events_newest_first_keeps_the_newest(backend):
    from app.schemas.event import AnalystLabel

    ids = []
    for _ in range(3):
        event = _event()
        await backend.add_event(event)
        await backend.update_event_label(event.event_id, AnalystLabel.NORMAL)
        ids.append(event.event_id)

    oldest = await backend.get_labeled_events(limit=2)
    newest = await backend.get_labeled_events(limit=2, newest_first=True)

    assert [event.event_id for event in oldest] == ids[:2]
    assert [event.event_id for event in newest] == [ids[2], ids[1]]
