"""Honeytoken detection schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

HoneytokenKind = Literal["login_token", "oauth_token", "service_token", "database_url"]


class HoneytokenHit(BaseModel):
    """Single detected interaction with a MIRAGE decoy token."""

    hit_id: str
    timestamp: datetime
    event_id: str
    token_kind: HoneytokenKind
    token_label: str
    source_ip: str
    path: str
    method: str
    evidence: str = Field(max_length=256)
