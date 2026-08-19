"""Collect proxy traffic into a local queue for independent manual review."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.ml.runtime_review_batch import (
    serialize_review_queue,
    sha256_text,
    write_text_exact,
)


@dataclass(frozen=True)
class ProxyScenario:
    """One staging request sent through the real routing path."""

    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""


def build_proxy_scenarios(
    *,
    normal_count: int,
    suspicious_count: int,
    borderline_count: int = 0,
) -> list[ProxyScenario]:
    """Build varied staging requests without assigning training labels."""
    scenarios = [
        ProxyScenario(
            method="GET",
            path=f"/api/catalog/items/{index + 1}",
            headers={"User-Agent": "Mozilla/5.0 MIRAGE-Staging-Review"},
        )
        for index in range(normal_count)
    ]
    scenarios.extend(
        ProxyScenario(
            method="GET",
            path=f"/api/search?q=runtime-review-{index + 1}%20status%3Aactive",
            headers={"User-Agent": "curl/8.0 MIRAGE-Staging-Review"},
        )
        for index in range(borderline_count)
    )
    suspicious_roots = (
        "/.env/runtime-review",
        "/api/admin/users/runtime-review",
        "/api/config/runtime-review",
        "/debug/token/runtime-review",
    )
    scenarios.extend(
        ProxyScenario(
            method="POST",
            path=f"{suspicious_roots[index % len(suspicious_roots)]}/{index + 1}",
            headers={
                "User-Agent": "sqlmap MIRAGE-Staging-Review",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            content=b"query=union select ../../.env",
        )
        for index in range(suspicious_count)
    )
    return scenarios


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _queue_entry(event: dict) -> dict[str, str]:
    fields = ("event_id", "timestamp", "method", "path")
    entry = {field: event.get(field) for field in fields}
    if any(not isinstance(value, str) or not value for value in entry.values()):
        raise RuntimeError("dashboard event is missing queue identity fields")
    if event.get("analyst_label") is not None:
        raise RuntimeError(f"event {entry['event_id']} was already labeled")
    return entry


def _find_new_event(
    events: list[dict],
    *,
    scenario: ProxyScenario,
    used_event_ids: set[str],
) -> dict | None:
    for event in events:
        event_id = event.get("event_id")
        if (
            isinstance(event_id, str)
            and event_id not in used_event_ids
            and str(event.get("method", "")).upper() == scenario.method.upper()
            and event.get("path") == scenario.path
        ):
            return event
    return None


async def collect_review_batch(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    scenarios: list[ProxyScenario],
    batch_id: str,
) -> tuple[dict, dict]:
    """Send proxy requests and return an unlabeled queue plus hash manifest."""
    started_at = _utc_now()
    entries: list[dict[str, str]] = []
    dashboard_headers = {"X-Mirage-API-Key": api_key}

    baseline_response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/events?limit=200"),
        headers=dashboard_headers,
    )
    baseline_response.raise_for_status()
    used_event_ids = {
        str(event["event_id"])
        for event in baseline_response.json().get("events", [])
        if event.get("event_id")
    }

    for scenario in scenarios:
        proxy_response = await client.request(
            scenario.method,
            _endpoint(base_url, f"/api/v1/proxy{scenario.path}"),
            headers=scenario.headers,
            content=scenario.content,
        )
        proxy_response.raise_for_status()

    events_response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/events?limit=200"),
        headers=dashboard_headers,
    )
    events_response.raise_for_status()
    events = events_response.json().get("events", [])
    for scenario in scenarios:
        event = _find_new_event(
            events,
            scenario=scenario,
            used_event_ids=used_event_ids,
        )
        if event is None:
            raise RuntimeError(
                f"could not find runtime event for {scenario.method} {scenario.path}"
            )
        entry = _queue_entry(event)
        entries.append(entry)
        used_event_ids.add(entry["event_id"])

    queue = {
        "schema_version": 1,
        "batch_id": batch_id,
        "entries": entries,
    }
    queue_text = serialize_review_queue(queue)
    manifest = {
        "schema_version": 1,
        "batch_id": batch_id,
        "collection_started_at": started_at,
        "collection_ended_at": _utc_now(),
        "event_count": len(entries),
        "queue_sha256": sha256_text(queue_text),
    }
    return queue, manifest


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
    parser.add_argument("--normal-count", type=int, default=20)
    parser.add_argument("--borderline-count", type=int, default=20)
    parser.add_argument("--suspicious-count", type=int, default=20)
    parser.add_argument("--batch-id", default=f"runtime-{uuid.uuid4().hex[:12]}")
    parser.add_argument(
        "--queue-output",
        type=Path,
        default=Path("data/raw/runtime/manual-review-queue.json"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/raw/runtime/manual-review-manifest.json"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()
    if not args.api_key:
        parser.error("--api-key or MIRAGE_API_KEY is required")
    if args.normal_count < 1 or args.suspicious_count < 1:
        parser.error("normal and suspicious counts must each be at least 1")
    if args.borderline_count < 0:
        parser.error("borderline count cannot be negative")
    if args.normal_count + args.borderline_count + args.suspicious_count > 100:
        parser.error("review batches are limited to 100 events")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    return args


def ensure_outputs_available(*paths: Path) -> None:
    """Protect an in-progress manual review from accidental replacement."""
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "review output already exists; archive it before collecting again: "
            + ", ".join(existing)
        )


async def run(args: argparse.Namespace) -> tuple[dict, dict]:
    ensure_outputs_available(args.queue_output, args.manifest_output)
    scenarios = build_proxy_scenarios(
        normal_count=args.normal_count,
        borderline_count=args.borderline_count,
        suspicious_count=args.suspicious_count,
    )
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        queue, manifest = await collect_review_batch(
            client,
            base_url=args.base_url,
            api_key=args.api_key,
            scenarios=scenarios,
            batch_id=args.batch_id,
        )
    write_text_exact(args.queue_output, serialize_review_queue(queue))
    write_text_exact(
        args.manifest_output,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    return queue, manifest


def main() -> None:
    _, manifest = asyncio.run(run(parse_args()))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
