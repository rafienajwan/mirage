"""Detect safe MIRAGE honeytoken interactions in bounded request metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.schemas.honeytoken import HoneytokenKind
from app.schemas.request import InspectRequest


@dataclass(frozen=True)
class HoneytokenMatch:
    """Internal detector result before persistence."""

    token_kind: HoneytokenKind
    token_label: str
    evidence: str


def _configured_tokens() -> list[tuple[HoneytokenKind, str, str]]:
    return [
        ("login_token", "Decoy login token", settings.decoy_login_token),
        ("oauth_token", "Decoy OAuth token", settings.decoy_oauth_token),
        ("service_token", "Decoy service token", settings.decoy_service_token),
        ("database_url", "Decoy database URL", settings.decoy_database_url),
    ]


def _is_placeholder(value: str) -> bool:
    return not value or value.endswith("_NOT_CONFIGURED")


def _request_text(request: InspectRequest) -> str:
    return " ".join(
        [
            request.path,
            request.user_agent,
            request.payload_excerpt,
            " ".join(request.payload_indicators),
        ]
    ).lower()


def detect_honeytokens(request: InspectRequest) -> list[HoneytokenMatch]:
    """Return configured decoy token values observed in request metadata."""
    text = _request_text(request)
    matches: list[HoneytokenMatch] = []
    for token_kind, token_label, token_value in _configured_tokens():
        if _is_placeholder(token_value):
            continue
        if token_value.lower() in text:
            matches.append(
                HoneytokenMatch(
                    token_kind=token_kind,
                    token_label=token_label,
                    evidence=f"{token_label} observed in request metadata",
                )
            )
    return matches
