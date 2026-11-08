"""Actor profiles, maintained by the store as each event is logged."""

from __future__ import annotations

from app.schemas.actor import ActorProfileSummary
from app.storage import store


async def get_actor_profiles(limit: int = 20) -> ActorProfileSummary:
    """Return the highest-priority actor profiles."""
    profiles = await store.get_actor_profiles(limit=limit)
    return ActorProfileSummary(total_actors=len(profiles), profiles=profiles)
