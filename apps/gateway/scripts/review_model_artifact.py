"""Review a trained MIRAGE artifact before enabling ML shadow mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.artifacts import review_model_artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--min-precision", type=float, default=0.5)
    parser.add_argument("--min-recall", type=float, default=0.5)
    parser.add_argument("--min-f1-score", type=float, default=0.5)
    parser.add_argument("--max-false-positive-rate", type=float, default=0.5)
    parser.add_argument("--min-training-rows", type=int, default=15)
    parser.add_argument("--min-test-rows", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review = review_model_artifact(
        args.artifact,
        min_precision=args.min_precision,
        min_recall=args.min_recall,
        min_f1_score=args.min_f1_score,
        max_false_positive_rate=args.max_false_positive_rate,
        min_training_rows=args.min_training_rows,
        min_test_rows=args.min_test_rows,
    )
    print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    if not review.shadow_ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
