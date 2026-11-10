"""Operator account and audit trail schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OperatorRole = Literal["analyst", "admin"]

USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{1,31}$"
RESERVED_USERNAMES = frozenset({"api-key"})


class OperatorRecord(BaseModel):
    """A dashboard operator account as stored."""

    username: str
    password_hash: str = Field(repr=False)
    role: OperatorRole
    disabled: bool = False
    created_at: datetime
    updated_at: datetime


class AuditEntry(BaseModel):
    """One state-changing operator action."""

    occurred_at: datetime
    operator: str
    action: str
    target: str = ""
    detail: str = ""
