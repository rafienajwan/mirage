"""Tests for dataset validation and preparation workflows."""

from __future__ import annotations

import json

import pytest

from app.ml.datasets import (
    DatasetValidationError,
    PreparedTrainingRow,
    load_api_log_jsonl,
    load_cicids_csv,
    load_mirage_jsonl,
    prepare_dataset,
    review_prepared_dataset,
    stratified_split,
)
from app.services.feature_extraction import FEATURE_NAMES


def _features(offset: float = 0.0) -> dict[str, float]:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset
    features["sensitive_path"] = offset % 2
    return features


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def test_load_mirage_jsonl_normalizes_feature_order(tmp_path):
    source = tmp_path / "training_events.jsonl"
    _write_jsonl(
        source,
        [
            {
                "event_id": "evt-1",
                "label": 1,
                "features": {
                    "request_count_log": "3.5",
                    "unknown_feature": 999,
                },
            }
        ],
    )

    rows = load_mirage_jsonl(source)

    assert len(rows) == 1
    assert rows[0].label == 1
    assert set(rows[0].features) == set(FEATURE_NAMES)
    assert rows[0].features["request_count_log"] == 3.5
    assert "unknown_feature" not in rows[0].features


def test_load_mirage_jsonl_rejects_bad_label(tmp_path):
    source = tmp_path / "training_events.jsonl"
    _write_jsonl(source, [{"label": 3, "features": _features()}])

    with pytest.raises(DatasetValidationError, match="label must be 0 or 1"):
        load_mirage_jsonl(source)


def test_load_api_log_jsonl_extracts_request_features(tmp_path):
    source = tmp_path / "api_logs.jsonl"
    _write_jsonl(
        source,
        [
            {
                "event_id": "evt-normal",
                "label": "normal",
                "source_ip": "10.0.0.10",
                "method": "GET",
                "path": "/api/products",
                "user_agent": "Mozilla/5.0",
                "request_count": 3,
            },
            {
                "event_id": "evt-suspicious",
                "label": "suspicious",
                "request": {
                    "client_ip": "10.0.0.66",
                    "http_method": "POST",
                    "endpoint": "/.env",
                    "ua": "curl/8.0",
                    "request_count": "30",
                    "payload_indicators": "path-traversal,sql-like",
                    "payload_excerpt": "SERVICE_TOKEN=mirage-service-canary",
                    "destination_port": "443",
                },
            },
        ],
    )

    rows = load_api_log_jsonl(source)

    assert [row.label for row in rows] == [0, 1]
    assert rows[0].record_id == "evt-normal"
    assert rows[1].record_id == "evt-suspicious"
    assert rows[1].features["method_post"] == 1.0
    assert rows[1].features["sensitive_path"] == 1.0
    assert rows[1].features["high_risk_indicator_count"] == 2.0
    assert rows[1].features["destination_port"] == 443.0


def test_load_api_log_jsonl_rejects_unknown_label(tmp_path):
    source = tmp_path / "api_logs.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "maybe",
                "source_ip": "10.0.0.10",
                "method": "GET",
                "path": "/api/products",
            }
        ],
    )

    with pytest.raises(DatasetValidationError, match="API log label"):
        load_api_log_jsonl(source)


def test_stratified_split_requires_two_rows_per_class():
    rows = [
        *load_rows(label=0, count=19),
        *load_rows(label=1, count=1),
    ]

    with pytest.raises(DatasetValidationError, match="at least two rows"):
        stratified_split(rows)


def test_prepare_dataset_writes_split_and_manifest(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(10)
    ]
    _write_jsonl(source, rows)

    manifest = prepare_dataset(
        source,
        tmp_path / "prepared" / "runtime-v1",
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
        train_ratio=0.8,
        random_seed=7,
    )

    output_dir = tmp_path / "prepared" / "runtime-v1"
    manifest_data = json.loads((output_dir / "manifest.json").read_text())
    train_rows = (output_dir / "train.jsonl").read_text().splitlines()
    test_rows = (output_dir / "test.jsonl").read_text().splitlines()

    assert manifest.total_rows == 20
    assert manifest.train_rows == 16
    assert manifest.test_rows == 4
    assert manifest_data["label_counts"] == {"0": 10, "1": 10}
    assert len(train_rows) == 16
    assert len(test_rows) == 4


def test_review_prepared_dataset_marks_valid_split_ready(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(12)
    ]
    _write_jsonl(source, rows)
    prepare_dataset(
        source,
        tmp_path / "prepared" / "runtime-v1",
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
        train_ratio=0.75,
        random_seed=7,
    )

    review = review_prepared_dataset(
        tmp_path / "prepared" / "runtime-v1" / "manifest.json",
    )

    assert review.ready_for_training is True
    assert review.blockers == []
    assert review.total_rows == 24
    assert review.train_label_counts["0"] >= 1
    assert review.test_label_counts["1"] >= 1


def test_review_prepared_dataset_blocks_manifest_row_mismatch(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(10)
    ]
    _write_jsonl(source, rows)
    prepare_dataset(
        source,
        tmp_path / "prepared" / "runtime-v1",
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    train_path = tmp_path / "prepared" / "runtime-v1" / "train.jsonl"
    train_path.write_text("", encoding="utf-8")

    review = review_prepared_dataset(
        tmp_path / "prepared" / "runtime-v1" / "manifest.json",
    )

    assert review.ready_for_training is False
    assert any("Train file row count" in blocker for blocker in review.blockers)


def test_review_prepared_dataset_blocks_malformed_counts(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(10)
    ]
    _write_jsonl(source, rows)
    prepare_dataset(
        source,
        tmp_path / "prepared" / "runtime-v1",
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    manifest_path = tmp_path / "prepared" / "runtime-v1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["label_counts"] = {"0": "bad", "1": 10}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    review = review_prepared_dataset(manifest_path)

    assert review.ready_for_training is False
    assert "manifest label_counts.0 must be an integer" in review.blockers


def test_load_cicids_csv_maps_known_columns(tmp_path):
    source = tmp_path / "cicids.csv"
    source.write_text(
        "\n".join(
            [
                "Destination Port,Flow Duration,Flow Packets/s,Packet Length Mean,SYN Flag Count,Average Packet Size,Label",
                "443,1200,15.5,42.0,2,64.0,BENIGN",
                "8080,5000,95.0,128.0,4,256.0,DDoS",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_cicids_csv(source)

    assert [row.label for row in rows] == [0, 1]
    assert rows[0].features["destination_port"] == 443.0
    assert rows[1].features["flow_packets_per_second"] == 95.0


def load_rows(label: int, count: int):
    return [
        PreparedTrainingRow(features=_features(float(i)), label=label)
        for i in range(count)
    ]
