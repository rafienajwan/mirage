"""Prepare validated train/test JSONL datasets for MIRAGE model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.datasets import prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source",
        choices=[
            "mirage-jsonl",
            "api-log-jsonl",
            "cicids-csv",
            "cicids-csv-dir",
            "csic-http-dir",
        ],
        required=True,
        dest="source_kind",
    )
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--train-ratio", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--checksums",
        type=Path,
        help="Optional JSON object mapping CSIC filenames to expected SHA-256 values",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_checksums = None
    if args.checksums:
        expected_checksums = json.loads(args.checksums.read_text(encoding="utf-8"))
        if not isinstance(expected_checksums, dict) or not all(
            isinstance(name, str) and isinstance(value, str)
            for name, value in expected_checksums.items()
        ):
            raise SystemExit("--checksums must contain a JSON object of string values")
    manifest = prepare_dataset(
        args.input,
        args.output_dir,
        source_kind=args.source_kind,
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
        train_ratio=args.train_ratio,
        random_seed=args.seed,
        expected_checksums=expected_checksums,
    )
    print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
