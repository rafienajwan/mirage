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
        choices=["mirage-jsonl", "cicids-csv"],
        required=True,
        dest="source_kind",
    )
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--train-ratio", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = prepare_dataset(
        args.input,
        args.output_dir,
        source_kind=args.source_kind,
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
        train_ratio=args.train_ratio,
        random_seed=args.seed,
    )
    print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
