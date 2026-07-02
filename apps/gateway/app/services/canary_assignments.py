"""Persistent lifecycle records for issued canary tokens."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.canary import CanaryAssignment
from app.schemas.honeytoken import HoneytokenKind
from app.services.actor_identity import actor_id_from_key
from app.storage import store


@dataclass(frozen=True)
class CanaryTokenAssignment:
    """Generated canary token metadata before persistence."""

    token_kind: HoneytokenKind
    token_label: str
    raw_token: str
    rotation_epoch: str


TOKEN_KIND_LABELS: dict[str, tuple[HoneytokenKind, str]] = {
    "login": ("login_token", "Issued decoy login token"),
    "oauth": ("oauth_token", "Issued decoy OAuth token"),
    "service": ("service_token", "Issued decoy service token"),
    "database": ("database_url", "Issued decoy database token"),
}

DECOY_TOKEN_KINDS: dict[str, tuple[str, ...]] = {
    "login": ("login",),
    "config": ("service",),
    "token": ("oauth",),
    "database": ("database",),
}


def assigned_token(
    actor_hint: str,
    token_kind: str,
    *,
    canary_epoch: str | None = None,
    service_token: str | None = None,
) -> str:
    """Build the deterministic synthetic canary token for an actor."""
    epoch = canary_epoch or getattr(settings, "decoy_canary_epoch", "v1")
    service_seed = service_token or settings.decoy_service_token
    seed = f"{actor_hint}:{token_kind}:{epoch}:{service_seed}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"mirage-issued-{token_kind}-canary-{digest}"


def token_hash(raw_token: str) -> str:
    """Hash a canary value for persistence without storing the raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def assignment_id(actor_hint: str, token_kind: HoneytokenKind, rotation_epoch: str) -> str:
    """Return a stable ID for one actor/kind/epoch assignment."""
    actor_id = actor_id_from_key(actor_hint)
    seed = f"{actor_id}:{token_kind}:{rotation_epoch}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"canary-{digest}"


def canary_tokens_for_decoy(
    decoy_type: str,
    actor_hint: str,
) -> list[CanaryTokenAssignment]:
    """Return canary tokens issued by a decoy type for an actor."""
    if not actor_hint:
        return []
    rotation_epoch = getattr(settings, "decoy_canary_epoch", "v1")
    tokens: list[CanaryTokenAssignment] = []
    for raw_kind in DECOY_TOKEN_KINDS.get(decoy_type, ()):
        token_kind, token_label = TOKEN_KIND_LABELS[raw_kind]
        tokens.append(
            CanaryTokenAssignment(
                token_kind=token_kind,
                token_label=token_label,
                raw_token=assigned_token(actor_hint, raw_kind),
                rotation_epoch=rotation_epoch,
            )
        )
    return tokens


async def record_canary_assignments(
    *,
    actor_hint: str,
    decoy_type: str,
    source_path: str,
) -> list[CanaryAssignment]:
    """Persist canary assignment records for a decoy response."""
    assignments: list[CanaryAssignment] = []
    now = datetime.now(timezone.utc)
    for token in canary_tokens_for_decoy(decoy_type, actor_hint):
        assignments.append(
            await store.upsert_canary_assignment(
                assignment=CanaryAssignment(
                    assignment_id=assignment_id(
                        actor_hint,
                        token.token_kind,
                        token.rotation_epoch,
                    ),
                    actor_id=actor_id_from_key(actor_hint),
                    token_kind=token.token_kind,
                    token_label=token.token_label,
                    token_hash=token_hash(token.raw_token),
                    rotation_epoch=token.rotation_epoch,
                    decoy_type=decoy_type,
                    source_path=source_path,
                    status="active",
                    issued_at=now,
                    last_seen_at=now,
                )
            )
        )
    return assignments
