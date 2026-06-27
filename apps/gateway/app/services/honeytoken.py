"""Detect safe MIRAGE honeytoken interactions in bounded request metadata."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.config import settings
from app.schemas.honeytoken import HoneytokenKind
from app.schemas.request import InspectRequest


@dataclass(frozen=True)
class HoneytokenMatch:
    """Internal detector result before persistence."""

    token_kind: HoneytokenKind
    token_label: str
    evidence: str


_ISSUED_TOKEN_PATTERN = re.compile(
    r"\bmirage-issued-(login|oauth|service|database)-canary-[a-f0-9]{12}\b",
    re.IGNORECASE,
)

_ISSUED_TOKEN_LABELS: dict[str, tuple[HoneytokenKind, str]] = {
    "login": ("login_token", "Issued decoy login token"),
    "oauth": ("oauth_token", "Issued decoy OAuth token"),
    "service": ("service_token", "Issued decoy service token"),
    "database": ("database_url", "Issued decoy database token"),
}


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
    seen_kinds = {match.token_kind for match in matches}
    for issued in _ISSUED_TOKEN_PATTERN.finditer(text):
        issued_kind = issued.group(1).lower()
        token_kind, token_label = _ISSUED_TOKEN_LABELS[issued_kind]
        if token_kind in seen_kinds:
            continue
        matches.append(
            HoneytokenMatch(
                token_kind=token_kind,
                token_label=token_label,
                evidence=f"{token_label} observed in request metadata",
            )
        )
        seen_kinds.add(token_kind)
    return matches
