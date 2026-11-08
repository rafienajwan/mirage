"""Build deterministic API-domain fixture logs for local model experiments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Scenario:
    """One generated request and its fixture label (not an analyst label)."""

    request: dict
    label: Literal["normal", "suspicious"]
    note: str


def build_scenarios(
    *,
    normal_count: int,
    suspicious_count: int,
) -> list[Scenario]:
    """Build deterministic API-domain scenarios for local fixture logs."""
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


def build_fixture_rows(*, normal_count: int, suspicious_count: int) -> list[dict]:
    """Return labeled API-log records compatible with the api-log-jsonl adapter."""
    rows: list[dict] = []
    for index, scenario in enumerate(
        build_scenarios(
            normal_count=normal_count,
            suspicious_count=suspicious_count,
        ),
        start=1,
    ):
        rows.append(
            {
                "event_id": f"api-domain-fixture-{index:04d}",
                "label": scenario.label,
                "note": scenario.note,
                "request": scenario.request,
                "source": "local-api-domain-fixture",
            }
        )
    return rows


def write_fixture_jsonl(path: Path, rows: list[dict]) -> None:
    """Write fixture rows as JSON Lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(row, sort_keys=True))
            target.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-count", type=int, default=20)
    parser.add_argument("--suspicious-count", type=int, default=20)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/runtime/api-domain-fixture-events.jsonl"),
    )
    args = parser.parse_args()
    if args.normal_count < 1:
        parser.error("--normal-count must be at least 1")
    if args.suspicious_count < 1:
        parser.error("--suspicious-count must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    rows = build_fixture_rows(
        normal_count=args.normal_count,
        suspicious_count=args.suspicious_count,
    )
    write_fixture_jsonl(args.output, rows)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "total_rows": len(rows),
                "normal_rows": args.normal_count,
                "suspicious_rows": args.suspicious_count,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
