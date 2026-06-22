"""Train a MIRAGE risk model from labeled JSON Lines records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.training import LabeledFeatures, train_risk_classifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk_model.joblib"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = []
    with args.input.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            try:
                rows.append(
                    LabeledFeatures(
                        features=record["features"], label=int(record["label"])
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid training row {line_number}") from exc

    metrics = train_risk_classifier(rows, args.output)
    print(json.dumps(metrics.__dict__, indent=2))


if __name__ == "__main__":
    main()
