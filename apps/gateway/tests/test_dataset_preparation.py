"""Tests for dataset validation and preparation workflows."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.ml.api_log_review import (
    APILogReviewMetadata,
    review_api_log_source,
    write_api_log_source_review,
)
from app.ml.datasets import (
    DatasetValidationError,
    PreparedTrainingRow,
    build_dataset_lineage,
    load_api_log_jsonl,
    load_cicids_csv,
    load_dataset,
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


def test_load_api_log_jsonl_combines_query_and_body_features(tmp_path):
    source = tmp_path / "api_logs.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "suspicious",
                "source_ip": "10.0.0.66",
                "method": "POST",
                "path": "/api/search",
                "query_string": "next=%2e%2e/admin",
                "request_body": "role=admin",
            }
        ],
    )

    row = load_api_log_jsonl(source)[0]

    assert row.features["payload_percent_encoded_count_log"] > 0.0
    assert row.features["payload_parameter_count_log"] == pytest.approx(
        1.098612,
    )


def test_load_api_log_jsonl_accepts_access_log_aliases(tmp_path):
    source = tmp_path / "api_logs.jsonl"
    _write_jsonl(
        source,
        [
            {
                "request_id": "access-1",
                "decision": "redirected",
                "httpRequest": {
                    "remote_addr": "203.0.113.10",
                    "request_method": "GET",
                    "url": "https://target.example/.env?debug=true",
                    "headers": {"User-Agent": "sqlmap/1.8"},
                    "hits": "42",
                    "tags": ["sql-like", "encoded"],
                    "query_string": "debug=true",
                    "durationMs": "250",
                    "flowPacketsPerSecond": "120.5",
                    "packetLengthMean": "512",
                    "synFlagCount": "8",
                    "destinationPort": "443",
                    "averagePacketSize": "640",
                },
            },
            {
                "id": "access-2",
                "outcome": "clean",
                "http": {
                    "clientIp": "203.0.113.11",
                    "httpMethod": "GET",
                    "uri": "/api/products?page=1",
                    "headers": {"user-agent": "Mozilla/5.0"},
                },
            },
        ],
    )

    rows = load_api_log_jsonl(source)

    assert [row.label for row in rows] == [1, 0]
    assert rows[0].record_id == "access-1"
    assert rows[0].features["sensitive_path"] == 1.0
    assert rows[0].features["suspicious_user_agent"] == 1.0
    assert rows[0].features["high_risk_indicator_count"] == 1.0
    assert rows[0].features["medium_risk_indicator_count"] == 1.0
    assert rows[0].features["destination_port"] == 443.0
    assert rows[1].features["path_depth"] == 2.0


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


def test_prepare_reviewed_api_logs_binds_safe_provenance_and_hashes_ids(tmp_path):
    source = tmp_path / "production-api.jsonl"
    rows = [
        {
            "request_id": f"private-normal-{index}",
            "label": "normal",
            "source_ip": f"203.0.113.{index + 10}",
            "method": "GET",
            "path": f"/api/orders/{index}",
            "user_agent": "private-client/1.0",
        }
        for index in range(12)
    ] + [
        {
            "request_id": f"private-attack-{index}",
            "label": "suspicious",
            "source_ip": f"198.51.100.{index + 10}",
            "method": "POST",
            "path": f"/api/search/{index}",
            "payload_excerpt": f"password=private-{index}&query=' or 1=1",
            "payload_indicators": ["sql-like"],
        }
        for index in range(12)
    ]
    _write_jsonl(source, [*rows, rows[0]])
    source_review = review_api_log_source(
        source,
        APILogReviewMetadata(
            data_origin="staging-api-gateway",
            collection_started_at="2026-07-01T00:00:00Z",
            collection_ended_at="2026-07-02T00:00:00Z",
            labeling_method="analyst-reviewed",
            sanitized=True,
            approved_for_training=True,
        ),
    )
    source_review_path = tmp_path / "production-api-review.json"
    write_api_log_source_review(source_review_path, source_review)
    output_dir = tmp_path / "prepared" / "production-api-v1"

    manifest = prepare_dataset(
        source,
        output_dir,
        source_kind="reviewed-api-log-jsonl",
        dataset_name="production-api",
        dataset_version="v1",
        source_review_path=source_review_path,
    )
    dataset_review = review_prepared_dataset(output_dir / "manifest.json")
    prepared_text = "".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )
    prepared_rows = [
        json.loads(line)
        for name in ("train.jsonl", "test.jsonl")
        for line in (output_dir / name).read_text(encoding="utf-8").splitlines()
    ]

    assert manifest.source_kind == "reviewed-api-log-jsonl"
    assert manifest.total_rows == 24
    assert manifest.duplicate_rows_removed == 1
    assert manifest.rejected_rows == 0
    assert manifest.input_sha256 == {source.name: source_review.input_sha256}
    assert manifest.files["source_review"] == "source-review.json"
    assert set(manifest.file_sha256) == {"train", "test", "source_review"}
    assert dataset_review.ready_for_training is True
    assert all(
        row["record_id"].startswith("sha256:")
        and len(row["record_id"]) == len("sha256:") + 64
        for row in prepared_rows
    )
    assert "private-normal" not in prepared_text
    assert "private-attack" not in prepared_text
    assert "203.0.113" not in prepared_text
    assert "private-client" not in prepared_text


def test_prepare_reviewed_api_logs_requires_source_review(tmp_path):
    source = tmp_path / "production-api.jsonl"
    _write_jsonl(source, [])

    with pytest.raises(DatasetValidationError, match="source review is required"):
        prepare_dataset(
            source,
            tmp_path / "prepared",
            source_kind="reviewed-api-log-jsonl",
            dataset_name="production-api",
            dataset_version="v1",
        )


def test_dataset_review_blocks_tampered_api_log_source_review(tmp_path):
    source = tmp_path / "production-api.jsonl"
    rows = [
        {
            "label": label,
            "source_ip": f"203.0.113.{index + 10}",
            "method": "GET",
            "path": f"/api/{label}/{index}",
        }
        for label in ("normal", "suspicious")
        for index in range(12)
    ]
    _write_jsonl(source, rows)
    source_review = review_api_log_source(
        source,
        APILogReviewMetadata(
            data_origin="staging-api-gateway",
            collection_started_at="2026-07-01T00:00:00Z",
            collection_ended_at="2026-07-02T00:00:00Z",
            labeling_method="analyst-reviewed",
            sanitized=True,
            approved_for_training=True,
        ),
    )
    source_review_path = tmp_path / "source-review.json"
    write_api_log_source_review(source_review_path, source_review)
    output_dir = tmp_path / "prepared"
    prepare_dataset(
        source,
        output_dir,
        source_kind="reviewed-api-log-jsonl",
        dataset_name="production-api",
        dataset_version="v1",
        source_review_path=source_review_path,
    )
    copied_review_path = output_dir / "source-review.json"
    copied_review = json.loads(copied_review_path.read_text(encoding="utf-8"))
    copied_review_path.write_text("{}\n", encoding="utf-8")

    review = review_prepared_dataset(output_dir / "manifest.json")

    assert review.ready_for_training is False
    assert "Source Review file SHA-256 does not match manifest" in review.blockers

    copied_review["metadata"]["collection_ended_at"] = "2026-06-30T00:00:00Z"
    copied_review_path.write_text(json.dumps(copied_review), encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["file_sha256"]["source_review"] = hashlib.sha256(
        copied_review_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    review = review_prepared_dataset(manifest_path)

    assert review.ready_for_training is False
    assert any("collection window" in blocker for blocker in review.blockers)


def test_dataset_review_blocks_manifest_paths_outside_prepared_directory(tmp_path):
    source = tmp_path / "source.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(12)
    ]
    _write_jsonl(source, rows)
    output_dir = tmp_path / "prepared"
    prepare_dataset(
        source,
        output_dir,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"label":0}\n', encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["train"] = "../outside.jsonl"
    manifest["file_sha256"]["train"] = hashlib.sha256(
        outside.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    review = review_prepared_dataset(manifest_path)

    assert review.ready_for_training is False
    assert "manifest train file must stay in the prepared directory" in review.blockers


def test_load_cicids_csv_directory_combines_sorted_csv_files(tmp_path):
    cicids_dir = tmp_path / "cicids"
    cicids_dir.mkdir()
    (cicids_dir / "b.csv").write_text(
        "Flow Duration,Flow Packets/s,Destination Port,Label\n"
        "20,4,80,DDoS\n",
        encoding="utf-8",
    )
    (cicids_dir / "a.csv").write_text(
        "Flow Duration,Flow Packets/s,Destination Port,Label\n"
        "10,2,443,BENIGN\n",
        encoding="utf-8",
    )

    rows = load_dataset(cicids_dir, source_kind="cicids-csv-dir")

    assert [row.label for row in rows] == [0, 1]
    assert [row.source for row in rows] == ["cicids-csv-dir", "cicids-csv-dir"]
    assert rows[0].record_id == "a.csv:2"
    assert rows[1].record_id == "b.csv:2"
    assert rows[0].features["flow_duration_ms"] == 10.0
    assert rows[1].features["destination_port"] == 80.0


def test_load_cicids_csv_directory_rejects_empty_directories(tmp_path):
    cicids_dir = tmp_path / "empty-cicids"
    cicids_dir.mkdir()

    with pytest.raises(DatasetValidationError, match="no CSV files"):
        load_dataset(cicids_dir, source_kind="cicids-csv-dir")


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
    assert manifest_data["feature_contract_version"] == 2
    assert manifest_data["label_counts"] == {"0": 10, "1": 10}
    assert manifest_data["file_sha256"] == {
        "train": hashlib.sha256((output_dir / "train.jsonl").read_bytes()).hexdigest(),
        "test": hashlib.sha256((output_dir / "test.jsonl").read_bytes()).hexdigest(),
    }
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


def test_review_prepared_dataset_blocks_split_hash_mismatch(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(10)
    ]
    _write_jsonl(source, rows)
    output_dir = tmp_path / "prepared" / "runtime-v1"
    prepare_dataset(
        source,
        output_dir,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    train_path = output_dir / "train.jsonl"
    content = train_path.read_text(encoding="utf-8")
    train_path.write_text(
        content.replace('"label": 0', '"label": 1', 1),
        encoding="utf-8",
    )

    review = review_prepared_dataset(output_dir / "manifest.json")

    assert review.ready_for_training is False
    assert "Train file SHA-256 does not match manifest" in review.blockers


def test_review_prepared_dataset_blocks_feature_contract_version_mismatch(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(12)
    ]
    _write_jsonl(source, rows)
    output_dir = tmp_path / "prepared" / "runtime-v1"
    prepare_dataset(
        source,
        output_dir,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["feature_contract_version"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    review = review_prepared_dataset(manifest_path)

    assert review.ready_for_training is False
    assert "Feature contract version does not match the gateway" in review.blockers


def test_build_dataset_lineage_rejects_unrelated_training_file(tmp_path):
    source = tmp_path / "training_events.jsonl"
    rows = [
        {"label": label, "features": _features(float(index))}
        for label in (0, 1)
        for index in range(12)
    ]
    _write_jsonl(source, rows)
    output_dir = tmp_path / "prepared" / "runtime-v1"
    prepare_dataset(
        source,
        output_dir,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    unrelated = tmp_path / "unrelated.jsonl"
    unrelated.write_text((output_dir / "train.jsonl").read_text(), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="manifest train file"):
        build_dataset_lineage(output_dir / "manifest.json", unrelated)


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


def test_load_cicids_csv_accepts_headers_with_extra_spaces(tmp_path):
    source = tmp_path / "cicids.csv"
    source.write_text(
        "\n".join(
            [
                " Destination Port, Flow Duration, Flow Packets/s, Packet Length Mean, SYN Flag Count, Average Packet Size, Label",
                "443,1200,15.5,42.0,2,64.0,BENIGN",
                "8080,5000,95.0,128.0,4,256.0,DDoS",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_cicids_csv(source)

    assert rows[0].features["destination_port"] == 443.0
    assert rows[0].features["flow_duration_ms"] == 1200.0
    assert rows[1].features["syn_flag_count"] == 4.0


def test_load_cicids_csv_zeroes_non_finite_values(tmp_path):
    source = tmp_path / "cicids.csv"
    source.write_text(
        "\n".join(
            [
                "Destination Port,Flow Duration,Flow Packets/s,Packet Length Mean,SYN Flag Count,Average Packet Size,Label",
                "443,Infinity,Infinity,42.0,2,64.0,BENIGN",
                "8080,5000,95.0,128.0,4,256.0,DDoS",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_cicids_csv(source)

    assert rows[0].features["flow_duration_ms"] == 0.0
    assert rows[0].features["flow_packets_per_second"] == 0.0


def load_rows(label: int, count: int):
    return [
        PreparedTrainingRow(features=_features(float(i)), label=label)
        for i in range(count)
    ]
