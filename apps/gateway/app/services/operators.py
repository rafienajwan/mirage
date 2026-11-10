"""Operator accounts: creation, authentication and audit helpers."""

from __future__ import annotations

import re

from app.core.passwords import (
    DUMMY_HASH,
    hash_password,
    validate_password,
    verify_password,
)
from app.core.security import Operator
from app.schemas.operator import (
    RESERVED_USERNAMES,
    USERNAME_PATTERN,
    AuditEntry,
    OperatorRecord,
    OperatorRole,
)
from app.storage import store
from app.utils.time import utcnow

_USERNAME = re.compile(USERNAME_PATTERN)


def normalize_username(value: str) -> str:
    """Strip and lowercase a username; reject invalid or reserved names."""
    name = value.strip().lower()
    if not _USERNAME.fullmatch(name) or name in RESERVED_USERNAMES:
        raise ValueError(
            "Username must be 2-32 characters (a-z, 0-9, '.', '_', '-') "
            "starting with a letter or digit, and not reserved"
        )
    return name


async def create_operator(username: str, password: str, role: OperatorRole) -> OperatorRecord:
    name = normalize_username(username)
    validate_password(password)
    now = utcnow()
    record = OperatorRecord(
        username=name,
        password_hash=hash_password(password),
        role=role,
        created_at=now,
        updated_at=now,
    )
    await store.create_operator(record)
    return record


async def authenticate(username: str, password: str) -> Operator | None:
    """Verify credentials with exactly one hash check, whatever the outcome."""
    try:
        name = normalize_username(username)
    except ValueError:
        name = None
    record = await store.get_operator(name) if name else None
    usable = record is not None and not record.disabled
    matched = verify_password(password, record.password_hash if usable else DUMMY_HASH)
    if usable and matched:
        return Operator(record.username, record.role)
    return None


async def audit(operator: Operator, action: str, target: str = "", detail: str = "") -> None:
    await store.record_audit(
        AuditEntry(
            occurred_at=utcnow(),
            operator=operator.username,
            action=action,
            target=target[:128],
            detail=detail[:500],
        )
    )
