"""Actor profile aggregation from recent events and honeytoken hits."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from app.schemas.actor import ActorProfile, ActorProfileSummary, ActorStatus
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.storage import store


def _actor_key(event: EventRecord) -> str:
    if event.fingerprint_hash:
        return event.fingerprint_hash
    return f"source:{event.ip_address}"


def _actor_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return f"actor-{digest}"


def _status(
    honeytoken_hits: int,
    decoy_redirects: int,
    suspicious_requests: int,
    max_risk_score: float,
) -> ActorStatus:
    if honeytoken_hits:
        return "confirmed_interaction"
    if decoy_redirects or max_risk_score >= 80:
        return "suspicious"
    if suspicious_requests:
        return "watch"
    return "quiet"


async def get_actor_profiles(limit: int = 20, event_limit: int = 500) -> ActorProfileSummary:
    """Build actor profiles from the newest stored events."""
    events = await store.get_recent_events(limit=event_limit)
    honeytoken_hits = await store.get_honeytoken_hits(limit=event_limit)
    honeytoken_hits_by_event = Counter(hit.event_id for hit in honeytoken_hits)

    groups: dict[str, list[EventRecord]] = defaultdict(list)
    for event in events:
        groups[_actor_key(event)].append(event)

    profiles: list[ActorProfile] = []
    for key, actor_events in groups.items():
        ordered = sorted(actor_events, key=lambda item: item.timestamp)
        latest = ordered[-1]
        risk_scores = [event.risk_score for event in ordered]
        suspicious_requests = sum(
            1 for event in ordered if event.decision != Decision.ALLOW
        )
        decoy_redirects = sum(
            1 for event in ordered if event.decision == Decision.REDIRECT_TO_DECOY
        )
        honeytoken_count = sum(
            honeytoken_hits_by_event[event.event_id] for event in ordered
        )
        max_risk_score = max(risk_scores)
        path_counts = Counter(event.path for event in ordered)

        profiles.append(
            ActorProfile(
                actor_id=_actor_id(key),
                fingerprint_hash=latest.fingerprint_hash,
                source_ip=latest.ip_address,
                first_seen=ordered[0].timestamp,
                last_seen=latest.timestamp,
                request_count=len(ordered),
                suspicious_requests=suspicious_requests,
                decoy_redirects=decoy_redirects,
                honeytoken_hits=honeytoken_count,
                max_risk_score=round(max_risk_score, 1),
                average_risk_score=round(sum(risk_scores) / len(risk_scores), 1),
                top_paths=[path for path, _ in path_counts.most_common(3)],
                last_decision=latest.decision,
                status=_status(
                    honeytoken_count,
                    decoy_redirects,
                    suspicious_requests,
                    max_risk_score,
                ),
            )
        )

    profiles.sort(
        key=lambda profile: (
            profile.honeytoken_hits,
            profile.decoy_redirects,
            profile.max_risk_score,
            profile.last_seen,
        ),
        reverse=True,
    )
    return ActorProfileSummary(total_actors=len(profiles), profiles=profiles[:limit])
