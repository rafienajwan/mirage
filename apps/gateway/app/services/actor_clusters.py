"""Lightweight actor clustering for dashboard triage."""

from __future__ import annotations

import hashlib

from app.schemas.actor import (
    ActorCase,
    ActorCaseOpenRequest,
    ActorCaseSummary,
    ActorCaseUpdateRequest,
    ActorCaseWorkflow,
    ActorCaseWorkflowSummary,
    ActorCluster,
    ActorClusterSummary,
    ActorProfile,
)
from app.services.actor_profiles import get_actor_profiles
from app.storage import store


def _cluster_key(profile: ActorProfile) -> tuple[str, str]:
    primary_path = profile.top_paths[0] if profile.top_paths else "unknown"
    return profile.status, primary_path


def _cluster_id(status: str, primary_path: str) -> str:
    digest = hashlib.sha256(f"{status}|{primary_path}".encode("utf-8")).hexdigest()
    return f"cluster-{digest[:10]}"


def _case_severity(cluster: ActorCluster) -> str:
    if cluster.honeytoken_hits > 0:
        return "critical"
    if cluster.decoy_redirects > 0 or cluster.max_risk_score >= 80:
        return "high"
    if cluster.status in {"suspicious", "watch"} or cluster.max_risk_score >= 60:
        return "medium"
    return "low"


def _case_action(cluster: ActorCluster) -> str:
    if cluster.honeytoken_hits > 0:
        return "Investigate issued canary reuse and preserve related request evidence."
    if cluster.decoy_redirects > 0:
        return "Review redirected proxy traffic and compare shared target paths."
    if cluster.max_risk_score >= 60:
        return "Review clustered requests and decide whether to label events for training."
    return "Monitor for repeated activity before opening a manual incident."


def _case_evidence(cluster: ActorCluster) -> list[str]:
    evidence = [
        f"{cluster.actor_count} actor profile(s) grouped under {cluster.label}",
        f"max risk score {cluster.max_risk_score}",
    ]
    if cluster.shared_paths:
        evidence.append(f"shared target paths: {', '.join(cluster.shared_paths)}")
    if cluster.honeytoken_hits:
        evidence.append(f"{cluster.honeytoken_hits} honeytoken hit(s)")
    if cluster.decoy_redirects:
        evidence.append(f"{cluster.decoy_redirects} decoy redirect(s)")
    return evidence


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


async def get_actor_cases(limit: int = 20) -> ActorCaseSummary:
    """Recommend read-only investigation cases from actor clusters."""
    cluster_summary = await get_actor_clusters(limit=100)
    cases: list[ActorCase] = []
    for cluster in cluster_summary.clusters:
        severity = _case_severity(cluster)
        if severity == "low" and cluster.actor_count < 2:
            continue
        case_digest = hashlib.sha256(cluster.cluster_id.encode("utf-8")).hexdigest()
        cases.append(
            ActorCase(
                case_id=f"case-{case_digest[:10]}",
                cluster_id=cluster.cluster_id,
                title=f"Review {cluster.label}",
                severity=severity,
                status="recommended",
                actor_count=cluster.actor_count,
                actor_ids=cluster.actor_ids,
                evidence=_case_evidence(cluster),
                recommended_action=_case_action(cluster),
                last_seen=cluster.last_seen,
            )
        )

    severity_order = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    cases.sort(
        key=lambda item: (
            severity_order[item.severity],
            item.actor_count,
            item.last_seen,
        ),
        reverse=True,
    )
    return ActorCaseSummary(total_cases=len(cases), cases=cases[:limit])


async def get_actor_case_workflows(limit: int = 20) -> ActorCaseWorkflowSummary:
    """Return persisted actor case workflow records."""
    if not hasattr(store, "get_actor_case_workflows"):
        return ActorCaseWorkflowSummary(total_cases=0, cases=[])
    cases = await store.get_actor_case_workflows(limit=limit)
    return ActorCaseWorkflowSummary(total_cases=len(cases), cases=cases)


async def open_actor_case_from_recommendation(
    case_id: str,
    payload: ActorCaseOpenRequest,
) -> ActorCaseWorkflow | None:
    """Persist a recommended actor case if it still exists."""
    recommendations = await get_actor_cases(limit=100)
    recommendation = next(
        (item for item in recommendations.cases if item.case_id == case_id),
        None,
    )
    if recommendation is None or not hasattr(store, "open_actor_case"):
        return None
    return await store.open_actor_case(recommendation, payload.note)


async def update_actor_case_workflow(
    case_id: str,
    payload: ActorCaseUpdateRequest,
) -> ActorCaseWorkflow | None:
    """Update an existing persisted actor case workflow."""
    if not hasattr(store, "update_actor_case"):
        return None
    return await store.update_actor_case(case_id, payload.status, payload.note)
