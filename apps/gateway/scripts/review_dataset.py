"""Review a prepared MIRAGE dataset before model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.datasets import review_prepared_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--min-total-rows", type=int, default=20)
    parser.add_argument("--min-train-rows", type=int, default=15)
    parser.add_argument("--min-test-rows", type=int, default=5)
    parser.add_argument("--min-rows-per-class", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review = review_prepared_dataset(
        args.manifest,
        min_total_rows=args.min_total_rows,
        min_train_rows=args.min_train_rows,
        min_test_rows=args.min_test_rows,
        min_rows_per_class=args.min_rows_per_class,
    )
    print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    if not review.ready_for_training:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
