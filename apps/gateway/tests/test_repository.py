"""DatabaseStore aggregates: actor path counts and the traffic chart."""


from uuid import uuid4

from sqlalchemy import select

from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.storage import store
from app.storage.db.database import get_session
from app.storage.db.models import ActorProfileModel
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
