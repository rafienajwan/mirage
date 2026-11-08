"""Request inspection schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

Indicator = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class InspectRequest(BaseModel):
    """Simulated API request metadata for security inspection."""

    ip_address: str = Field(
        ..., min_length=3, max_length=64, description="Source IP address"
    )
    method: str = Field(
        ...,
        min_length=3,
        max_length=16,
        pattern=r"^[A-Za-z]+$",
        description="HTTP method (GET, POST, etc.)",
    )
    path: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        pattern=r"^/",
        description="Request path (e.g. /api/v1/users)",
    )
    user_agent: str = Field(
        default="", max_length=512, description="User-Agent header value"
    )
    request_count: int = Field(
        default=1, ge=1, le=1_000_000, description="Number of requests from this source"
    )
    payload_indicators: list[Indicator] = Field(
        default_factory=list,
        max_length=20,
        description="Labels describing payload characteristics (e.g. 'sql-like', 'encoded')",
    )
    exempted_indicators: list[Indicator] = Field(
        default_factory=list,
        max_length=20,
        description="Labels removed from routing by a PAYLOAD_EXEMPTIONS rule",
    )
    payload_excerpt: str = Field(
        default="",
        max_length=4096,
        description="Small bounded request excerpt used for decoy/honeytoken matching",
    )
    header_text: str = Field(
        repr=False,
        default="",
        max_length=8192,
        # Holds credentials (Authorization, Cookie): matched, never serialized.
        exclude=True,
        description="Authorization, Cookie and Referer values for honeytoken matching",
    )
    timestamp: Optional[datetime] = Field(
        default=None, description="Request timestamp (auto-filled if omitted)"
    )
