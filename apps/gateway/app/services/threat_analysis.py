"""Threat analysis — basic summaries from logged events."""

from __future__ import annotations

from collections import Counter

from app.schemas.decision import Decision
from app.storage.memory_store import store


def get_threat_summary() -> dict:
    """Generate a summary of threat activity from logged events."""
    events = store.events

    if not events:
        return {
            "total_events": 0,
            "suspicious_endpoints": [],
            "top_source_ips": [],
            "decision_breakdown": {},
            "high_risk_count": 0,
            "decoy_interactions": 0,
        }

    # Count decisions
    decision_counts = Counter(e.decision.value for e in events)

    # Suspicious endpoints (paths that triggered non-allow decisions)
    suspicious_paths = set()
    for e in events:
        if e.decision != Decision.ALLOW:
            suspicious_paths.add(e.path)

    # Top source IPs
    ip_counts = Counter(e.ip_address for e in events)
    top_ips = ip_counts.most_common(5)

    # High-risk events (score >= 60)
    high_risk_count = sum(1 for e in events if e.risk_score >= 60)

    # Decoy interactions
    decoy_interactions = sum(
        1 for e in events if e.decision == Decision.REDIRECT_TO_DECOY
    )

    return {
        "total_events": len(events),
        "suspicious_endpoints": sorted(suspicious_paths),
        "top_source_ips": [{"ip": ip, "count": c} for ip, c in top_ips],
        "decision_breakdown": dict(decision_counts),
        "high_risk_count": high_risk_count,
        "decoy_interactions": decoy_interactions,
    }
