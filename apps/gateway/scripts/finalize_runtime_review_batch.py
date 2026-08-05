"""Finalize one manually labeled runtime batch into sanitized training JSONL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from app.ml.runtime_review_batch import (
    FinalizedReviewBatch,
    finalize_review_batch,
)


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


async def fetch_finalized_review_batch(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    queue_text: str,
    manifest: dict,
    approved_for_training: bool,
) -> FinalizedReviewBatch:
    """Fetch labeled rows and finalize only the event IDs in the review queue."""
    response = await client.get(
        _endpoint(base_url, "/api/v1/dashboard/training-data/export?limit=50000"),
        headers={"X-Mirage-API-Key": api_key},
    )
    response.raise_for_status()
    return finalize_review_batch(
        queue_text=queue_text,
        manifest=manifest,
        export_jsonl=response.text,
        approved_for_training=approved_for_training,
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
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("data/raw/runtime/manual-review-queue.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/raw/runtime/manual-review-manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/runtime/manual-reviewed-events.jsonl"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/raw/runtime/manual-reviewed-summary.json"),
    )
    parser.add_argument("--approved-for-training", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()
    if not args.api_key:
        parser.error("--api-key or MIRAGE_API_KEY is required")
    if not args.approved_for_training:
        parser.error("--approved-for-training is required")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    return args


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def run(args: argparse.Namespace) -> FinalizedReviewBatch:
    queue_text = args.queue.read_text(encoding="utf-8")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        result = await fetch_finalized_review_batch(
            client,
            base_url=args.base_url,
            api_key=args.api_key,
            queue_text=queue_text,
            manifest=manifest,
            approved_for_training=args.approved_for_training,
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
