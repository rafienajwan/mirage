"""Build deterministic API-domain fixture logs for local model experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collect_api_domain_training_data import build_scenarios


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
