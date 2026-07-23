"""Create a privacy-safe quality and provenance review for custom API logs."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from app.ml.api_log_review import (
    APILogReviewMetadata,
    review_api_log_source,
    write_api_log_source_review,
)


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("must include a timezone")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-origin", required=True)
    parser.add_argument("--collection-started-at", type=_timestamp, required=True)
    parser.add_argument("--collection-ended-at", type=_timestamp, required=True)
    parser.add_argument("--labeling-method", required=True)
    parser.add_argument("--sanitized", action="store_true")
    parser.add_argument("--approved-for-training", action="store_true")
    parser.add_argument("--minimum-rows", type=int, default=20)
    parser.add_argument("--minimum-rows-per-class", type=int, default=2)
    args = parser.parse_args()
    if args.minimum_rows < 1:
        parser.error("--minimum-rows must be at least 1")
    if args.minimum_rows_per_class < 1:
        parser.error("--minimum-rows-per-class must be at least 1")
    if not args.data_origin.strip():
        parser.error("--data-origin must not be empty")
    if not args.labeling_method.strip():
        parser.error("--labeling-method must not be empty")
    return args


def main() -> None:
    args = parse_args()
    review = review_api_log_source(
        args.input,
        APILogReviewMetadata(
            data_origin=args.data_origin.strip(),
            collection_started_at=args.collection_started_at,
            collection_ended_at=args.collection_ended_at,
            labeling_method=args.labeling_method.strip(),
            sanitized=args.sanitized,
            approved_for_training=args.approved_for_training,
        ),
        minimum_rows=args.minimum_rows,
        minimum_rows_per_class=args.minimum_rows_per_class,
    )
    write_api_log_source_review(args.output, review)
    print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    if not review.ready_for_preparation:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
