"""Persistent lifecycle records for issued canary tokens."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from app.core.config import settings
from app.schemas.canary import CanaryAssignment
from app.schemas.honeytoken import HoneytokenKind
from app.services.actor_identity import actor_id_from_key
from app.services.honeytoken import ISSUED_TOKEN_LABELS, ISSUED_TOKEN_PATTERN
from app.storage import store


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


async def record_canary_assignments(
    *,
    actor_hint: str,
    decoy_type: str,
    source_path: str,
    response_text: str,
) -> list[CanaryAssignment]:
    """Persist an assignment for each issued token the decoy actually returned."""
    if not actor_hint:
        return []
    rotation_epoch = getattr(settings, "decoy_canary_epoch", "v1")
    now = datetime.now(timezone.utc)
    assignments: list[CanaryAssignment] = []
    issued = ISSUED_TOKEN_PATTERN.finditer(response_text)
    tokens = {match.group(0): match.group(1) for match in issued}
    for raw_token, raw_kind in tokens.items():
        token_kind, token_label = ISSUED_TOKEN_LABELS[raw_kind.lower()]
        assignments.append(
            await store.upsert_canary_assignment(
                assignment=CanaryAssignment(
                    assignment_id=assignment_id(actor_hint, token_kind, rotation_epoch),
                    actor_id=actor_id_from_key(actor_hint),
                    token_kind=token_kind,
                    token_label=token_label,
                    token_hash=token_hash(raw_token),
                    rotation_epoch=rotation_epoch,
                    decoy_type=decoy_type,
                    source_path=source_path,
                    status="active",
                    issued_at=now,
                    last_seen_at=now,
                )
            )
        )
    return assignments
