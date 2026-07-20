"""Tests for the external HTTP CSIC 2010 dataset adapter."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.ml.csic_http import load_csic_http_directory, parse_csic_http_requests
from app.ml.datasets import (
    DatasetValidationError,
    load_csic_http_rows,
    prepare_dataset,
    review_prepared_dataset,
)


def _request(method: str, target: str, body: str = "", *, user_agent: str = "Mozilla/5.0") -> bytes:
    body_bytes = body.encode("latin-1")
    headers = [
        f"{method} {target} HTTP/1.1",
        "Host: localhost:8080",
        f"User-Agent: {user_agent}",
        "Connection: close",
    ]
    if body:
        headers.append(f"Content-Length: {len(body_bytes)}")
        headers.append("Content-Type: application/x-www-form-urlencoded")
    return ("\r\n".join(headers) + "\r\n\r\n").encode("latin-1") + body_bytes + b"\r\n\r\n"


def _write_csic_directory(path) -> None:
    path.mkdir()
    normal_training = b"".join(
        _request("GET", f"http://localhost:8080/tienda1/publico/anadir.jsp?id={index}")
        for index in range(6)
    )
    normal_test = b"".join(
        _request("POST", "/tienda1/publico/autenticar.jsp", f"modo=entrar&login=user{index}")
        for index in range(4)
    )
    anomalous = b"".join(
        _request(
            "POST",
            "/tienda1/publico/autenticar.jsp?next=%2e%2e/admin",
            f"modo=entrar&login=' or 1=1&sample={index}",
            user_agent="w3af",
        )
        for index in range(10)
    )
    (path / "normalTrafficTraining.txt").write_bytes(normal_training)
    (path / "normalTrafficTest.txt").write_bytes(normal_test)
    (path / "anomalousTrafficTest.txt").write_bytes(anomalous)


def test_parser_reads_absolute_target_headers_and_post_body():
    payload = _request(
        "POST",
        "http://localhost:8080/tienda1/publico/autenticar.jsp?next=%2e%2e/admin",
        "modo=entrar&login=' or 1=1",
        user_agent="w3af",
    )

    records = parse_csic_http_requests(payload, source_file="anomalousTrafficTest.txt", label=1)

    assert len(records) == 1
    assert records[0].method == "POST"
    assert records[0].path == "/tienda1/publico/autenticar.jsp"
    assert records[0].query == "next=%2e%2e/admin"
    assert records[0].body == b"modo=entrar&login=' or 1=1"
    assert records[0].user_agent == "w3af"
    assert records[0].label == 1


def test_csic_rows_combine_query_and_body_features(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)

    suspicious = next(
        row for row in load_csic_http_rows(source) if row.label == 1
    )

    assert suspicious.features["payload_percent_encoded_count_log"] > 0.0
    assert suspicious.features["payload_parameter_count_log"] == pytest.approx(
        1.609438,
    )


def test_parser_rejects_truncated_content_length():
    payload = (
        b"POST /login HTTP/1.1\r\nHost: localhost\r\n"
        b"Content-Length: 20\r\n\r\nshort"
    )

    with pytest.raises(DatasetValidationError, match="truncated body"):
        parse_csic_http_requests(payload, source_file="anomalousTrafficTest.txt", label=1)


def test_parser_falls_back_to_host_header_for_malformed_target_port():
    payload = _request("GET", "http://localhost:8080.old")

    records = parse_csic_http_requests(
        payload,
        source_file="anomalousTrafficTest.txt",
        label=1,
    )

    assert records[0].path == "/"
    assert records[0].destination_port == 8080


def test_directory_loader_records_hashes_and_removes_same_label_duplicates(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)
    duplicate = _request("GET", "http://localhost:8080/tienda1/publico/anadir.jsp?id=0")
    normal_test = source / "normalTrafficTest.txt"
    normal_test.write_bytes(normal_test.read_bytes() + duplicate)

    loaded = load_csic_http_directory(source)

    assert len(loaded.records) == 20
    assert loaded.duplicate_rows_removed == 1
    assert loaded.rejected_rows == 0
    assert set(loaded.input_sha256) == {
        "normalTrafficTraining.txt",
        "normalTrafficTest.txt",
        "anomalousTrafficTest.txt",
    }
    assert all(len(value) == 64 for value in loaded.input_sha256.values())


def test_directory_loader_rejects_duplicate_with_conflicting_label(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)
    conflicting = _request("GET", "http://localhost:8080/tienda1/publico/anadir.jsp?id=0")
    anomalous = source / "anomalousTrafficTest.txt"
    anomalous.write_bytes(anomalous.read_bytes() + conflicting)

    with pytest.raises(DatasetValidationError, match="conflicting labels"):
        load_csic_http_directory(source)


def test_prepare_csic_dataset_writes_provenance_and_prevents_leakage(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)
    expected = {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in source.iterdir()
    }

    manifest = prepare_dataset(
        source,
        tmp_path / "prepared",
        source_kind="csic-http-dir",
        dataset_name="http-csic-2010",
        dataset_version="impact-ds-0940",
        expected_checksums=expected,
    )

    manifest_data = json.loads((tmp_path / "prepared" / "manifest.json").read_text())
    train_ids = {
        json.loads(line)["record_id"]
        for line in (tmp_path / "prepared" / "train.jsonl").read_text().splitlines()
    }
    test_ids = {
        json.loads(line)["record_id"]
        for line in (tmp_path / "prepared" / "test.jsonl").read_text().splitlines()
    }

    assert manifest.source_kind == "csic-http-dir"
    assert manifest.source_url.startswith("https://www.impactcybertrust.org/")
    assert manifest.distribution_url == "https://doi.org/10.60895/redata/RWUUSV"
    assert manifest_data["input_sha256"] == expected
    assert manifest_data["duplicate_rows_removed"] == 0
    assert train_ids.isdisjoint(test_ids)


def test_prepare_csic_dataset_rejects_checksum_mismatch(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)
    expected = {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in source.iterdir()
    }
    expected["normalTrafficTraining.txt"] = "0" * 64

    with pytest.raises(DatasetValidationError, match="checksum mismatch"):
        prepare_dataset(
            source,
            tmp_path / "prepared",
            source_kind="csic-http-dir",
            dataset_name="http-csic-2010",
            dataset_version="impact-ds-0940",
            expected_checksums=expected,
        )


def test_directory_loader_rejects_incomplete_checksum_manifest(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)

    with pytest.raises(DatasetValidationError, match="must cover the three required files"):
        load_csic_http_directory(
            source,
            expected_checksums={"normalTrafficTraining.txt": "0" * 64},
        )


def test_review_csic_manifest_blocks_invalid_provenance(tmp_path):
    source = tmp_path / "csic"
    _write_csic_directory(source)
    output = tmp_path / "prepared"
    prepare_dataset(
        source,
        output,
        source_kind="csic-http-dir",
        dataset_name="http-csic-2010",
        dataset_version="impact-ds-0940",
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_url"] = "https://example.invalid/dataset"
    manifest["distribution_url"] = "https://example.invalid/download"
    manifest["input_sha256"] = {"normalTrafficTraining.txt": "bad"}
    manifest["duplicate_rows_removed"] = -1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    review = review_prepared_dataset(manifest_path)

    assert review.ready_for_training is False
    assert "CSIC source_url does not match the official catalog" in review.blockers
    assert "CSIC distribution_url does not match the approved DOI" in review.blockers
    assert "CSIC input_sha256 must cover the three required files" in review.blockers
    assert "CSIC checksum for normalTrafficTraining.txt is invalid" in review.blockers
    assert "manifest duplicate_rows_removed must be non-negative" in review.blockers
