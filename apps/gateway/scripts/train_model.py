"""Train a MIRAGE risk model from labeled JSON Lines records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.datasets import build_dataset_lineage, load_mirage_jsonl
from app.ml.training import train_risk_classifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk_model.joblib"))
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Prepared dataset manifest used to bind lineage into the artifact; "
            "its test split becomes the held-out evaluation set"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_mirage_jsonl(args.input)

    lineage = None
    test_rows = None
    if args.manifest:
        lineage = build_dataset_lineage(args.manifest, args.input)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        test_rows = load_mirage_jsonl(args.manifest.parent / manifest["files"]["test"])

    metrics = train_risk_classifier(
        rows,
        args.output,
        dataset_lineage=lineage,
        test_rows=test_rows,
    )
    print(json.dumps(metrics.__dict__, indent=2))


if __name__ == "__main__":
    main()
