"""Storage engine isolation between concurrent sessions."""

from sqlalchemy import func, select

from app.storage.db.database import async_session_factory, get_session
from app.storage.db.models import EventModel


def _event() -> EventModel:
    return EventModel(
        event_id="evt-isolation",
        ip_address="10.0.0.1",
        path="/isolation",
        method="GET",
        risk_score=0.0,
        decision="allow",
    )


async def test_closing_another_session_does_not_discard_pending_write():
    # A background reader (e.g. the dashboard snapshot task) closing its
    # session mid-request must not roll back the request's flushed insert.
    async with get_session() as writer:
        writer.add(_event())
        await writer.flush()

        reader = async_session_factory()
        await reader.execute(select(EventModel.id))
        await reader.close()

    async with get_session() as check:
        stored = (await check.execute(select(func.count(EventModel.id)))).scalar_one()
    assert stored == 1
