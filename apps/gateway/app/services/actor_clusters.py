"""Lightweight actor clustering for dashboard triage."""

from __future__ import annotations

import hashlib

from app.schemas.actor import ActorCluster, ActorClusterSummary, ActorProfile
from app.services.actor_profiles import get_actor_profiles


def _cluster_key(profile: ActorProfile) -> tuple[str, str]:
    primary_path = profile.top_paths[0] if profile.top_paths else "unknown"
    return profile.status, primary_path


def _cluster_id(status: str, primary_path: str) -> str:
    digest = hashlib.sha256(f"{status}|{primary_path}".encode("utf-8")).hexdigest()
    return f"cluster-{digest[:10]}"


async def get_actor_clusters(
    limit: int = 20,
    profile_limit: int = 100,
) -> ActorClusterSummary:
    """Group actor profiles by current status and dominant target path."""
    summary = await get_actor_profiles(limit=profile_limit)
    grouped: dict[tuple[str, str], list[ActorProfile]] = {}
    for profile in summary.profiles:
        grouped.setdefault(_cluster_key(profile), []).append(profile)

    clusters: list[ActorCluster] = []
    for (status, primary_path), profiles in grouped.items():
        profiles.sort(
            key=lambda item: (
                item.honeytoken_hits,
                item.decoy_redirects,
                item.max_risk_score,
                item.last_seen,
            ),
            reverse=True,
        )
        path_counts: dict[str, int] = {}
        for profile in profiles:
            for path in profile.top_paths:
                path_counts[path] = path_counts.get(path, 0) + 1
        shared_paths = [
            path
            for path, _ in sorted(
                path_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:3]
        ]
        honeytoken_hits = sum(profile.honeytoken_hits for profile in profiles)
        decoy_redirects = sum(profile.decoy_redirects for profile in profiles)
        max_risk_score = max(profile.max_risk_score for profile in profiles)
        last_seen = max(profile.last_seen for profile in profiles)

        clusters.append(
            ActorCluster(
                cluster_id=_cluster_id(status, primary_path),
                label=f"{status.replace('_', ' ')} actors targeting {primary_path}",
                status=status,
                actor_count=len(profiles),
                actor_ids=[profile.actor_id for profile in profiles[:10]],
                shared_paths=shared_paths,
                max_risk_score=round(max_risk_score, 1),
                honeytoken_hits=honeytoken_hits,
                decoy_redirects=decoy_redirects,
                last_seen=last_seen,
            )
        )

    clusters.sort(
        key=lambda item: (
            item.honeytoken_hits,
            item.decoy_redirects,
            item.max_risk_score,
            item.actor_count,
            item.last_seen,
        ),
        reverse=True,
    )
    return ActorClusterSummary(total_clusters=len(clusters), clusters=clusters[:limit])
