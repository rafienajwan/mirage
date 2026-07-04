"""Utilities for longer ML shadow observation runs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable


DECISION_KEYS = ("allow", "monitor", "redirect_to_decoy")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    return default


def _decision_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {key: 0 for key in DECISION_KEYS}
    return {key: _as_int(value.get(key)) for key in DECISION_KEYS}


def build_observation_record(
    *,
    status: dict[str, Any],
    summary: dict[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Normalize one status/summary pair into an append-only observation row."""
    shadow_events = _as_int(summary.get("shadow_events"))
    disagreements = _as_int(summary.get("disagreements"))
    disagreement_rate = (
        round(disagreements / shadow_events, 6) if shadow_events else 0.0
    )

    return {
        "observed_at": observed_at or _utc_now_iso(),
        "mode": str(status.get("mode", "unknown")),
        "shadow_ready": bool(status.get("shadow_ready", False)),
        "artifact": status.get("artifact"),
        "blockers": list(status.get("blockers", [])),
        "warnings": list(status.get("warnings", [])),
        "monitor_threshold": _as_float(status.get("monitor_threshold")),
        "redirect_threshold": _as_float(status.get("redirect_threshold")),
        "inspected_events": _as_int(summary.get("inspected_events")),
        "shadow_events": shadow_events,
        "agreements": _as_int(summary.get("agreements")),
        "disagreements": disagreements,
        "agreement_rate": _as_float(summary.get("agreement_rate")),
        "disagreement_rate": disagreement_rate,
        "average_probability": _as_float(summary.get("average_probability")),
        "average_score": _as_float(summary.get("average_score")),
        "live_decisions": _decision_counts(summary.get("live_decisions")),
        "shadow_decisions": _decision_counts(summary.get("shadow_decisions")),
    }


def summarize_observation_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize append-only ML shadow observation records for review."""
    rows = list(records)
    if not rows:
        return {
            "samples": 0,
            "started_at": None,
            "ended_at": None,
            "mode_counts": {},
            "shadow_ready_samples": 0,
            "shadow_event_delta": 0,
            "latest_shadow_events": 0,
            "latest_agreement_rate": 0.0,
            "latest_disagreement_rate": 0.0,
            "latest_disagreements": 0,
            "max_disagreement_rate": 0.0,
        }

    first = rows[0]
    latest = rows[-1]
    mode_counts = Counter(str(row.get("mode", "unknown")) for row in rows)

    return {
        "samples": len(rows),
        "started_at": first.get("observed_at"),
        "ended_at": latest.get("observed_at"),
        "mode_counts": dict(sorted(mode_counts.items())),
        "shadow_ready_samples": sum(1 for row in rows if row.get("shadow_ready")),
        "shadow_event_delta": _as_int(latest.get("shadow_events"))
        - _as_int(first.get("shadow_events")),
        "latest_shadow_events": _as_int(latest.get("shadow_events")),
        "latest_agreement_rate": _as_float(latest.get("agreement_rate")),
        "latest_disagreement_rate": _as_float(latest.get("disagreement_rate")),
        "latest_disagreements": _as_int(latest.get("disagreements")),
        "max_disagreement_rate": max(
            _as_float(row.get("disagreement_rate")) for row in rows
        ),
    }
