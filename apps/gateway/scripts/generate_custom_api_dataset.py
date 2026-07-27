"""Generate, review, train, and evaluate a production-like custom API log dataset and artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure app package is importable when executed directly
gateway_dir = Path(__file__).resolve().parent.parent
if str(gateway_dir) not in sys.path:
    sys.path.insert(0, str(gateway_dir))

from build_api_domain_fixture_dataset import build_fixture_rows, write_fixture_jsonl
from app.ml.api_log_review import (
    APILogReviewMetadata,
    review_api_log_source,
    write_api_log_source_review,
)
from app.ml.artifacts import review_model_artifact
from app.ml.datasets import (
    build_dataset_lineage,
    prepare_dataset,
    review_prepared_dataset,
)
from app.ml.training import LabeledFeatures, train_risk_classifier


def generate_and_train_custom_api_dataset(
    *,
    normal_count: int = 600,
    suspicious_count: int = 600,
    raw_dir: Path = Path("data/raw/custom_api_logs"),
    prepared_dir: Path = Path("data/prepared/custom_api_logs"),
    artifact_dir: Path = Path("artifacts/custom_api_logs"),
) -> dict:
    """Generate, review, prepare, and train a custom API log candidate artifact."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    input_jsonl = raw_dir / "custom-api-logs.jsonl"

    # Step 1: Generate synthetic production-like custom API log rows
    rows = build_fixture_rows(normal_count=normal_count, suspicious_count=suspicious_count)
    write_fixture_jsonl(input_jsonl, rows)

    # Step 2: Metadata attestation required for API log source review
    meta = APILogReviewMetadata(
        data_origin="production-like-synthetic-api-logs",
        collection_started_at="2026-07-01T00:00:00Z",
        collection_ended_at="2026-07-27T12:00:00Z",
        labeling_method="expert-analyst-rules",
        sanitized=True,
        approved_for_training=True,
    )

    # Step 3: Review source quality and provenance
    source_review = review_api_log_source(
        input_jsonl,
        meta,
        minimum_rows=100,
        minimum_rows_per_class=20,
    )
    if not source_review.ready_for_preparation:
        raise ValueError(f"Source review failed: {source_review.blockers}")

    source_review_path = raw_dir / "custom-api-logs.review.json"
    write_api_log_source_review(source_review_path, source_review)

    # Step 4: Prepare train/test dataset splits using reviewed-api-log-jsonl source
    prepare_dataset(
        input_jsonl,
        prepared_dir,
        source_kind="reviewed-api-log-jsonl",
        dataset_name="custom-api-logs-candidate",
        dataset_version="1.0.0",
        random_seed=42,
        source_review_path=source_review_path,
    )

    dataset_manifest_path = prepared_dir / "manifest.json"
    dataset_review = review_prepared_dataset(
        dataset_manifest_path,
        min_total_rows=100,
        min_rows_per_class=20,
    )

    # Step 5: Load prepared training rows from train.jsonl
    train_jsonl_path = prepared_dir / "train.jsonl"
    training_rows: list[LabeledFeatures] = []
    with train_jsonl_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            rec = json.loads(line)
            training_rows.append(
                LabeledFeatures(features=rec["features"], label=int(rec["label"]))
            )

    # Step 6: Train Random Forest model artifact bound to dataset lineage
    lineage = build_dataset_lineage(dataset_manifest_path, train_jsonl_path)
    artifact_path = artifact_dir / "custom_api_risk_model.joblib"
    train_metrics = train_risk_classifier(
        training_rows,
        artifact_path,
        dataset_lineage=lineage,
    )
    artifact_review = review_model_artifact(artifact_path)

    return {
        "raw_jsonl": str(input_jsonl),
        "source_review": str(source_review_path),
        "prepared_manifest": str(dataset_manifest_path),
        "model_artifact": str(artifact_path),
        "total_rows": dataset_review.total_rows,
        "metrics": train_metrics.__dict__,
        "shadow_ready": artifact_review.shadow_ready,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-count", type=int, default=600)
    parser.add_argument("--suspicious-count", type=int, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = generate_and_train_custom_api_dataset(
        normal_count=args.normal_count,
        suspicious_count=args.suspicious_count,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
