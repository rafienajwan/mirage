"""Shared actor profile identity and status helpers."""

from __future__ import annotations

import hashlib

from app.schemas.actor import ActorStatus
from app.schemas.decision import Decision
from app.schemas.event import EventRecord


def actor_key(event: EventRecord) -> str:
    """Stable grouping key for an event."""
    if event.fingerprint_hash:
        return event.fingerprint_hash
    return f"source:{event.ip_address}"


def actor_id_from_key(key: str) -> str:
    """Privacy-safe actor identifier derived from a grouping key."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return f"actor-{digest}"


def actor_status(
    honeytoken_hits: int,
    decoy_redirects: int,
    suspicious_requests: int,
    max_risk_score: float,
) -> ActorStatus:
    """Classify actor severity from aggregate counters."""
    if honeytoken_hits:
        return "confirmed_interaction"
    if decoy_redirects or max_risk_score >= 80:
        return "suspicious"
    if suspicious_requests:
        return "watch"
    return "quiet"


def is_suspicious_decision(decision: Decision) -> bool:
    return decision != Decision.ALLOW
