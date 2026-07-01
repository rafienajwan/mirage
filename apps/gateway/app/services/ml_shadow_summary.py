"""Aggregate recent model-only shadow scoring observations."""

from __future__ import annotations

from app.schemas.dashboard import MLShadowDecisionBreakdown, MLShadowSummary
from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.storage import store


def _empty_breakdown() -> dict[str, int]:
    return {decision.value: 0 for decision in Decision}


def _breakdown_model(counts: dict[str, int]) -> MLShadowDecisionBreakdown:
    return MLShadowDecisionBreakdown(
        allow=counts[Decision.ALLOW.value],
        monitor=counts[Decision.MONITOR.value],
        redirect_to_decoy=counts[Decision.REDIRECT_TO_DECOY.value],
    )


def summarize_ml_shadow_events(events: list[EventRecord]) -> MLShadowSummary:
    """Summarize agreement between live heuristic and model-only decisions."""
    live_counts = _empty_breakdown()
    shadow_counts = _empty_breakdown()
    shadow_events = [event for event in events if event.ml_shadow is not None]
    agreements = 0
    probability_total = 0.0
    score_total = 0.0

    for event in shadow_events:
        shadow = event.ml_shadow
        if shadow is None:
            continue
        live_counts[event.decision.value] += 1
        shadow_counts[shadow.shadow_decision] += 1
        agreements += int(shadow.agrees_with_decision)
        probability_total += shadow.probability
        score_total += shadow.score

    shadow_count = len(shadow_events)
    disagreements = shadow_count - agreements
    return MLShadowSummary(
        inspected_events=len(events),
        shadow_events=shadow_count,
        agreements=agreements,
        disagreements=disagreements,
        agreement_rate=round(agreements / shadow_count, 6) if shadow_count else 0.0,
        average_probability=round(probability_total / shadow_count, 6)
        if shadow_count
        else 0.0,
        average_score=round(score_total / shadow_count, 2) if shadow_count else 0.0,
        live_decisions=_breakdown_model(live_counts),
        shadow_decisions=_breakdown_model(shadow_counts),
    )


async def get_ml_shadow_summary(limit: int = 200) -> MLShadowSummary:
    """Return recent model-only agreement summary for operator review."""
    events = await store.get_recent_events(limit=limit)
    return summarize_ml_shadow_events(events)
