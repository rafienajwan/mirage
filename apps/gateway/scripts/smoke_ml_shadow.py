"""Smoke-test ML shadow scoring with a local artifact.

This script verifies artifact loading, request inspection, event logging, and
shadow summary generation without changing live routing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--monitor-threshold", type=float, default=0.35)
    parser.add_argument("--redirect-threshold", type=float, default=0.65)
    parser.add_argument(
        "--memory-store",
        action="store_true",
        help="Use the in-memory store instead of the configured DATABASE_URL.",
    )
    return parser.parse_args()


def configure_environment(args: argparse.Namespace) -> None:
    os.environ["MIRAGE_MODEL_ARTIFACT"] = str(args.artifact)
    os.environ["ML_SHADOW_MONITOR_THRESHOLD"] = str(args.monitor_threshold)
    os.environ["ML_SHADOW_REDIRECT_THRESHOLD"] = str(args.redirect_threshold)
    if args.memory_store:
        os.environ["DATABASE_URL"] = "memory"


async def run_smoke() -> dict:
    from app.schemas.request import InspectRequest
    from app.services.inspection import inspect_and_log
    from app.services.ml_shadow_summary import get_ml_shadow_summary
    from app.services.ml_status import get_ml_shadow_status

    status = get_ml_shadow_status()
    requests = [
        InspectRequest(
            ip_address="10.10.0.10",
            method="GET",
            path="/api/products",
            user_agent="Mozilla/5.0",
            request_count=1,
            flow_duration_ms=1200,
            flow_packets_per_second=3.0,
            packet_length_mean=280,
            syn_flag_count=1,
            destination_port=443,
            average_packet_size=300,
        ),
        InspectRequest(
            ip_address="10.10.0.66",
            method="GET",
            path="/.env",
            user_agent="sqlmap/1.8",
            request_count=80,
            payload_indicators=["sql-like", "path-traversal", "encoded"],
            payload_excerpt="union select ../../.env",
            flow_duration_ms=450,
            flow_packets_per_second=2500.0,
            packet_length_mean=1200,
            syn_flag_count=22,
            destination_port=80,
            average_packet_size=1280,
        ),
    ]
    responses = [
        (
            await inspect_and_log(request, event_type="shadow_smoke")
        ).model_dump(mode="json")
        for request in requests
    ]
    summary = await get_ml_shadow_summary(limit=20)
    return {
        "status": status,
        "responses": responses,
        "summary": summary.model_dump(mode="json"),
    }


def main() -> None:
    args = parse_args()
    configure_environment(args)
    result = asyncio.run(run_smoke())
    print(json.dumps(result, indent=2, sort_keys=True))

    status = result["status"]
    summary = result["summary"]
    if status["mode"] != "shadow_ready" or not status["shadow_ready"]:
        raise SystemExit(1)
    if summary["shadow_events"] < 2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
