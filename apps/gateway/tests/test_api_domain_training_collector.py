"""Tests for local API-domain training data collection tooling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_api_domain_training_data import (  # noqa: E402
    build_scenarios,
    collect_training_data,
    find_event_id,
)


def test_build_scenarios_creates_balanced_unique_api_domain_requests():
    scenarios = build_scenarios(normal_count=3, suspicious_count=2)

    assert [scenario.label for scenario in scenarios].count("normal") == 3
    assert [scenario.label for scenario in scenarios].count("suspicious") == 2
    assert len({scenario.request["path"] for scenario in scenarios}) == 5
    assert all(scenario.request["path"].startswith("/") for scenario in scenarios)


def test_find_event_id_matches_path_and_method():
    events = [
        {"event_id": "evt-other", "method": "GET", "path": "/api/other"},
        {"event_id": "evt-match", "method": "POST", "path": "/.env"},
    ]

    assert find_event_id(events, method="post", path="/.env") == "evt-match"
    assert find_event_id(events, method="GET", path="/missing") is None


@pytest.mark.asyncio
async def test_collect_training_data_labels_and_exports_rows():
    events: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/inspect":
            payload = json.loads(request.content.decode("utf-8"))
            event = {
                "event_id": f"evt-{len(events) + 1}",
                "method": payload["method"],
                "path": payload["path"],
                "analyst_label": None,
            }
            events.insert(0, event)
            return httpx.Response(200, json={"decision": "allow"})

        if request.method == "GET" and request.url.path == "/api/v1/dashboard/events":
            return httpx.Response(200, json={"events": events})

        if request.method == "PATCH" and "/api/v1/dashboard/events/" in request.url.path:
            event_id = request.url.path.rsplit("/", 2)[-2]
            payload = json.loads(request.content.decode("utf-8"))
            for event in events:
                if event["event_id"] == event_id:
                    event["analyst_label"] = payload["label"]
                    return httpx.Response(200, json=event)
            return httpx.Response(404, json={"detail": "Event not found"})

        if request.method == "GET" and request.url.path == "/api/v1/dashboard/training-data/summary":
            return httpx.Response(
                200,
                json={
                    "labeled_rows": len(events),
                    "exportable_rows": len(events),
                    "normal_rows": 1,
                    "suspicious_rows": 1,
                    "ready_for_training": False,
                },
            )

        if request.method == "GET" and request.url.path == "/api/v1/dashboard/training-data/export":
            content = "".join(
                json.dumps({"event_id": event["event_id"], "label": 0}) + "\n"
                for event in events
            )
            return httpx.Response(200, content=content)

        return httpx.Response(500, json={"detail": "unexpected request"})

    transport = httpx.MockTransport(handler)
    scenarios = build_scenarios(normal_count=1, suspicious_count=1)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await collect_training_data(
            client,
            base_url="http://test",
            api_key="local-key",
            scenarios=scenarios,
        )

    assert [event["analyst_label"] for event in events] == ["suspicious", "normal"]
    assert result.summary["labeled_rows"] == 2
    assert result.export_jsonl.count("\n") == 2
