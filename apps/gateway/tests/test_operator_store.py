"""Operator accounts and audit trail storage, on both store backends."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.passwords import hash_password
from app.schemas.actor import ActorCase
from app.schemas.decision import Decision
from app.schemas.event import AnalystLabel, EventRecord
from app.schemas.operator import AuditEntry, OperatorRecord
from app.storage import store
from app.storage.memory_store import MemoryStore
from app.utils.time import utcnow

BACKENDS = pytest.mark.parametrize(
    "backend", [store, MemoryStore()], ids=["database", "memory"]
)


def _operator(username: str = "alice", role: str = "analyst") -> OperatorRecord:
    now = utcnow()
    return OperatorRecord(
        username=username,
        password_hash=hash_password("correct horse battery"),
        role=role,
        created_at=now,
        updated_at=now,
    )


def _unique(name: str) -> str:
    return f"{name}{uuid4().hex[:6]}"


@BACKENDS
async def test_create_get_list_operator(backend):
    name = _unique("alice")
    await backend.create_operator(_operator(name))

    fetched = await backend.get_operator(name)
    assert fetched is not None and fetched.role == "analyst"
    assert name in [o.username for o in await backend.list_operators()]
    assert await backend.get_operator("nobody-here") is None


@BACKENDS
async def test_duplicate_operator_rejected(backend):
    name = _unique("dup")
    await backend.create_operator(_operator(name))
    with pytest.raises(ValueError, match="Operator already exists"):
        await backend.create_operator(_operator(name))


@BACKENDS
async def test_update_operator_disables_and_bumps_updated_at(backend):
    name = _unique("carol")
    record = _operator(name)
    record = record.model_copy(update={"updated_at": utcnow() - timedelta(days=1)})
    await backend.create_operator(record)

    updated = await backend.update_operator(name, disabled=True, role="admin")
    assert updated is not None
    assert updated.disabled is True and updated.role == "admin"
    assert updated.updated_at > record.updated_at
    assert updated.password_hash == record.password_hash

    new_hash = hash_password("another long password")
    again = await backend.update_operator(name, password_hash=new_hash)
    assert again.password_hash == new_hash and again.disabled is True
    assert await backend.update_operator("ghost-user", disabled=True) is None


@BACKENDS
async def test_list_operators_sorted_by_username(backend):
    names = sorted(_unique(prefix) for prefix in ("zed", "abe", "mel"))
    for name in reversed(names):
        await backend.create_operator(_operator(name))
    listed = [o.username for o in await backend.list_operators() if o.username in names]
    assert listed == names


@BACKENDS
async def test_audit_newest_first(backend):
    base = utcnow()
    tag = _unique("act")
    for index in range(3):
        await backend.record_audit(
            AuditEntry(
                occurred_at=base + timedelta(seconds=index),
                operator="alice",
                action=f"{tag}-{index}",
                target="t",
                detail="d",
            )
        )
    entries = await backend.get_audit(2)
    assert [e.action for e in entries] == [f"{tag}-2", f"{tag}-1"]


@BACKENDS
async def test_label_records_author(backend):
    event_id = uuid4().hex
    await backend.add_event(
        EventRecord(
            event_id=event_id,
            timestamp=utcnow(),
            ip_address="10.0.***.***",
            path="/api/x",
            method="GET",
            risk_score=5.0,
            decision=Decision.ALLOW,
            fingerprint_hash="fp-label",
            summary="",
        )
    )
    labeled = await backend.update_event_label(
        event_id, AnalystLabel.SUSPICIOUS, "", labeled_by="alice"
    )
    assert labeled.labeled_by == "alice"
    recent = await backend.get_recent_events(5)
    assert [e.labeled_by for e in recent if e.event_id == event_id] == ["alice"]


@BACKENDS
async def test_case_update_records_author(backend):
    case_id = uuid4().hex[:16]
    recommendation = ActorCase(
        case_id=case_id,
        cluster_id="cluster-1",
        title="Scanner cluster",
        severity="high",
        status="recommended",
        actor_count=1,
        actor_ids=["actor-1"],
        evidence=["probe"],
        recommended_action="watch",
        last_seen=utcnow(),
    )
    opened = await backend.open_actor_case(recommendation, updated_by="alice")
    assert opened.updated_by == "alice"
    updated = await backend.update_actor_case(case_id, "investigating", updated_by="bob")
    assert updated.updated_by == "bob"


def test_password_hash_not_in_repr():
    assert "scrypt" not in repr(_operator())
