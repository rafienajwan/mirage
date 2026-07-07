"""Collect labeled API-domain training data from a running MIRAGE gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx


AnalystLabel = Literal["normal", "suspicious"]


@dataclass(frozen=True)
class Scenario:
    """One request and analyst label used for local API-domain collection."""

    request: dict
    label: AnalystLabel
    note: str


@dataclass(frozen=True)
class CollectionResult:
    """Exported training data and readiness summary from a collection run."""

    summary: dict
    export_jsonl: str


def build_scenarios(
    *,
    normal_count: int,
    suspicious_count: int,
) -> list[Scenario]:
    """Build deterministic API-domain scenarios for local labeled collection."""
    scenarios: list[Scenario] = []
    for index in range(normal_count):
        scenarios.append(
            Scenario(
                request={
                    "ip_address": f"192.168.10.{index + 10}",
                    "method": "GET",
                    "path": f"/api/v1/products/{index + 1}",
                    "user_agent": "Mozilla/5.0",
                    "request_count": 2 + (index % 3),
                    "payload_indicators": [],
                    "destination_port": 443,
                },
                label="normal",
                note="Reviewed local API-domain benign traffic",
            )
        )

    suspicious_paths = (
        "/.env",
        "/api/v1/admin/users",
        "/api/v1/config",
        "/api/v1/token/debug",
    )
    for index in range(suspicious_count):
        path = suspicious_paths[index % len(suspicious_paths)]
        scenarios.append(
            Scenario(
                request={
                    "ip_address": f"10.20.30.{index + 10}",
                    "method": "POST",
                    "path": f"{path}/{index + 1}",
                    "user_agent": "sqlmap/1.8",
                    "request_count": 75 + index,
                    "payload_indicators": ["sql-like", "path-traversal", "encoded"],
                    "payload_excerpt": "union select ../../.env",
                    "flow_packets_per_second": 1800.0 + index,
                    "packet_length_mean": 900.0,
                    "syn_flag_count": 12 + index,
                    "destination_port": 443,
                    "average_packet_size": 980.0,
                },
                label="suspicious",
                note="Reviewed local API-domain suspicious traffic",
            )
        )
    return scenarios


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"X-Mirage-API-Key": api_key}


def find_event_id(events: list[dict], *, method: str, path: str) -> str | None:
    """Find the newest dashboard event matching a submitted request."""
    for event in events:
        if event.get("method", "").upper() == method.upper() and event.get("path") == path:
            event_id = event.get("event_id")
            return str(event_id) if event_id else None
    return None


async def _label_scenario(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    scenario: Scenario,
) -> None:
    headers = _auth_headers(api_key)
    inspect_response = await client.post(
        _endpoint(base_url, "/api/v1/inspect"),
        headers=headers,
        json=scenario.request,
    )
    inspect_response.raise_for_status()

    events_response = await client.get(_endpoint(base_url, "/api/v1/dashboard/events?limit=200"))
    events_response.raise_for_status()
    event_id = find_event_id(
        events_response.json().get("events", []),
        method=scenario.request["method"],
        path=scenario.request["path"],
    )
    if event_id is None:
        raise RuntimeError(
            f"Could not find event for {scenario.request['method']} {scenario.request['path']}"
        )

    label_response = await client.patch(
        _endpoint(base_url, f"/api/v1/dashboard/events/{event_id}/label"),
        headers=headers,
        json={"label": scenario.label, "note": scenario.note},
    )
    label_response.raise_for_status()


async def collect_training_data(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    scenarios: list[Scenario],
) -> CollectionResult:
    """Submit, label, summarize, and export local API-domain training rows."""
    for scenario in scenarios:
        await _label_scenario(
            client,
            base_url=base_url,
            api_key=api_key,
            scenario=scenario,
        )

    headers = _auth_headers(api_key)
    summary_response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/training-data/summary"),
        headers=headers,
    )
    summary_response.raise_for_status()
    export_response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/training-data/export"),
        headers=headers,
    )
    export_response.raise_for_status()
    return CollectionResult(
        summary=summary_response.json(),
        export_jsonl=export_response.text,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MIRAGE_GATEWAY_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("MIRAGE_API_KEY"),
        help="Operator API key. Defaults to MIRAGE_API_KEY.",
    )
    parser.add_argument("--normal-count", type=int, default=10)
    parser.add_argument("--suspicious-count", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/runtime/api-domain-training-events.jsonl"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/raw/runtime/api-domain-training-summary.json"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()

    if not args.api_key:
        parser.error("--api-key or MIRAGE_API_KEY is required")
    if args.normal_count < 1:
        parser.error("--normal-count must be at least 1")
    if args.suspicious_count < 1:
        parser.error("--suspicious-count must be at least 1")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    return args


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def run(args: argparse.Namespace) -> CollectionResult:
    scenarios = build_scenarios(
        normal_count=args.normal_count,
        suspicious_count=args.suspicious_count,
    )
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        result = await collect_training_data(
            client,
            base_url=args.base_url,
            api_key=args.api_key,
            scenarios=scenarios,
        )
    _write_text(args.output, result.export_jsonl)
    _write_text(
        args.summary_output,
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
    )
    return result


def main() -> None:
    result = asyncio.run(run(parse_args()))
    print(json.dumps(result.summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
