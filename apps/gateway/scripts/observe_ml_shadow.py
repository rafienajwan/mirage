"""Collect longer ML shadow observation snapshots from a running gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.services.ml_shadow_observation import (
    build_observation_record,
    summarize_observation_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MIRAGE_GATEWAY_URL", "http://localhost:8000"),
        help="Gateway base URL. Defaults to MIRAGE_GATEWAY_URL or localhost:8000.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=10,
        help="Number of observation snapshots to collect.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=30.0,
        help="Delay between samples. Use 0 for a quick local check.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Recent events limit passed to the ML shadow summary endpoint.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="HTTP timeout for each dashboard request.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSONL file for append-only observation snapshots.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        help="Optional JSON file for the final aggregate observation summary.",
    )
    args = parser.parse_args()

    if args.samples < 1:
        parser.error("--samples must be at least 1")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds cannot be negative")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    return args


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


async def fetch_observation_snapshot(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    limit: int,
) -> dict[str, Any]:
    """Fetch and normalize one ML shadow status/summary observation."""
    status_response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/ml-shadow/status")
    )
    status_response.raise_for_status()
    summary_response = await client.get(
        _endpoint(base_url, f"/api/v1/dashboard/ml-shadow/summary?limit={limit}")
    )
    summary_response.raise_for_status()
    return build_observation_record(
        status=status_response.json(),
        summary=summary_response.json(),
    )


async def collect_observations(args: argparse.Namespace) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        for index in range(args.samples):
            record = await fetch_observation_snapshot(
                client,
                base_url=args.base_url,
                limit=args.limit,
            )
            records.append(record)
            if args.output:
                _append_jsonl(args.output, record)
            if index < args.samples - 1:
                await asyncio.sleep(args.interval_seconds)

    summary = summarize_observation_records(records)
    if args.summary_output:
        _write_json(args.summary_output, summary)
    return summary


def main() -> None:
    args = parse_args()
    summary = asyncio.run(collect_observations(args))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
