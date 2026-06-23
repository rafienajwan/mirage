"""ML shadow scoring schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MLShadowScore(BaseModel):
    """Model-only scoring result that never controls live routing."""

    artifact: str
    probability: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=100)
    prediction: str
    shadow_decision: Literal["allow", "monitor", "redirect_to_decoy"]
    agrees_with_decision: bool
