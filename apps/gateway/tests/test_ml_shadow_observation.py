"""Tests for longer ML shadow observation reporting."""

from __future__ import annotations

import httpx
import pytest

from app.services.ml_shadow_observation import (
    build_observation_record,
    summarize_observation_records,
)
from scripts.observe_ml_shadow import fetch_observation_snapshot


def _status(mode: str = "shadow_ready") -> dict:
    return {
        "mode": mode,
        "shadow_ready": mode == "shadow_ready",
        "artifact": "risk_model.joblib",
        "monitor_threshold": 0.35,
        "redirect_threshold": 0.65,
        "metrics": {},
        "blockers": [],
        "warnings": [],
    }


def _summary(
    *,
    shadow_events: int,
    agreements: int,
    disagreements: int,
) -> dict:
    return {
        "inspected_events": shadow_events,
        "shadow_events": shadow_events,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": round(agreements / shadow_events, 6)
        if shadow_events
        else 0.0,
        "average_probability": 0.42,
        "average_score": 42.0,
        "live_decisions": {"allow": 1, "monitor": 2, "redirect_to_decoy": 3},
        "shadow_decisions": {"allow": 3, "monitor": 2, "redirect_to_decoy": 1},
    }


@pytest.mark.asyncio
async def test_fetch_observation_snapshot_sends_operator_api_key():
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Mirage-API-Key") == "operator-key"
        requested_paths.append(request.url.path)
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json=_status())
        return httpx.Response(
            200,
            json=_summary(shadow_events=2, agreements=1, disagreements=1),
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        record = await fetch_observation_snapshot(
            client,
            base_url="http://test",
            limit=200,
            api_key="operator-key",
        )

    assert requested_paths == [
        "/api/v1/dashboard/ml-shadow/status",
        "/api/v1/dashboard/ml-shadow/summary",
    ]
    assert record["shadow_events"] == 2


def test_build_observation_record_normalizes_rates_and_decision_counts():
    record = build_observation_record(
        status=_status(),
        summary=_summary(shadow_events=8, agreements=6, disagreements=2),
        observed_at="2026-07-04T00:00:00+00:00",
    )

    assert record["observed_at"] == "2026-07-04T00:00:00+00:00"
    assert record["mode"] == "shadow_ready"
    assert record["shadow_ready"] is True
    assert record["shadow_events"] == 8
    assert record["agreement_rate"] == 0.75
    assert record["disagreement_rate"] == 0.25
    assert record["live_decisions"]["redirect_to_decoy"] == 3
    assert record["shadow_decisions"]["allow"] == 3


def test_summarize_observation_records_reports_latest_and_delta():
    records = [
        build_observation_record(
            status=_status(),
            summary=_summary(shadow_events=5, agreements=4, disagreements=1),
            observed_at="2026-07-04T00:00:00+00:00",
        ),
        build_observation_record(
            status=_status("invalid"),
            summary=_summary(shadow_events=9, agreements=6, disagreements=3),
            observed_at="2026-07-04T00:01:00+00:00",
        ),
    ]

    summary = summarize_observation_records(records)

    assert summary["samples"] == 2
    assert summary["started_at"] == "2026-07-04T00:00:00+00:00"
    assert summary["ended_at"] == "2026-07-04T00:01:00+00:00"
    assert summary["mode_counts"] == {"invalid": 1, "shadow_ready": 1}
    assert summary["shadow_ready_samples"] == 1
    assert summary["shadow_event_delta"] == 4
    assert summary["latest_shadow_events"] == 9
    assert summary["latest_disagreements"] == 3
    assert summary["latest_disagreement_rate"] == 0.333333
    assert summary["max_disagreement_rate"] == 0.333333


def test_summarize_observation_records_handles_empty_input():
    summary = summarize_observation_records([])

    assert summary["samples"] == 0
    assert summary["started_at"] is None
    assert summary["ended_at"] is None
    assert summary["shadow_event_delta"] == 0
    assert summary["latest_agreement_rate"] == 0.0
