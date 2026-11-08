"""Evaluate a MIRAGE model artifact on a prepared holdout split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.artifacts import (
    REVIEW_MAX_FALSE_POSITIVE_RATE,
    REVIEW_MIN_F1_SCORE,
    REVIEW_MIN_PRECISION,
    REVIEW_MIN_RECALL,
)
from app.ml.evaluation import evaluate_model_artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    for flag, kind, default in (
        ("--min-precision", float, REVIEW_MIN_PRECISION),
        ("--min-recall", float, REVIEW_MIN_RECALL),
        ("--min-f1-score", float, REVIEW_MIN_F1_SCORE),
        ("--max-false-positive-rate", float, REVIEW_MAX_FALSE_POSITIVE_RATE),
        ("--min-rows", int, 5),
    ):
        parser.add_argument(flag, type=kind, default=default, help="default: %(default)s")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluation = evaluate_model_artifact(
        args.artifact,
        args.input,
        min_precision=args.min_precision,
        min_recall=args.min_recall,
        min_f1_score=args.min_f1_score,
        max_false_positive_rate=args.max_false_positive_rate,
        min_rows=args.min_rows,
    )
    print(json.dumps(evaluation.to_dict(), indent=2, sort_keys=True))
    if not evaluation.holdout_ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
