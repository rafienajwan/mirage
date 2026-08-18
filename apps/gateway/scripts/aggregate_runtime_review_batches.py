"""Aggregate finalized analyst-reviewed runtime batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.runtime_review_batch import (
    FinalizedReviewBatch,
    aggregate_review_batches,
    write_text_exact,
)


def aggregate_batch_files(
    *,
    batch_paths: list[tuple[Path, Path]],
    output: Path,
    summary_output: Path,
) -> FinalizedReviewBatch:
    """Load, validate, and write one aggregate from reviewed batch files."""
    existing = [str(path) for path in (output, summary_output) if path.exists()]
    if existing:
        raise FileExistsError(
            "aggregate output already exists; archive it before rebuilding: "
            + ", ".join(existing)
        )

    batches = [
        FinalizedReviewBatch(
            export_jsonl=events_path.read_bytes().decode("utf-8"),
            summary=json.loads(summary_path.read_bytes().decode("utf-8")),
        )
        for events_path, summary_path in batch_paths
    ]
    result = aggregate_review_batches(batches)
    write_text_exact(output, result.export_jsonl)
    write_text_exact(
        summary_output,
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch",
        action="append",
        nargs=2,
        type=Path,
        required=True,
        metavar=("EVENTS", "SUMMARY"),
        help="Finalized event JSONL and its summary. Repeat for each batch.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/runtime/reviewed-events.jsonl"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/processed/runtime/reviewed-summary.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = aggregate_batch_files(
        batch_paths=args.batch,
        output=args.output,
        summary_output=args.summary_output,
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
