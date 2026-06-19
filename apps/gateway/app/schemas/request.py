"""Request inspection schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InspectRequest(BaseModel):
    """Simulated API request metadata for security inspection."""

    ip_address: str = Field(..., description="Source IP address")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    path: str = Field(..., description="Request path (e.g. /api/v1/users)")
    user_agent: str = Field(default="", description="User-Agent header value")
    request_count: int = Field(
        default=1, ge=1, description="Number of requests from this source"
    )
    payload_indicators: list[str] = Field(
        default_factory=list,
        description="Labels describing payload characteristics (e.g. 'sql-like', 'encoded')",
    )
    timestamp: Optional[datetime] = Field(
        default=None, description="Request timestamp (auto-filled if omitted)"
    )
