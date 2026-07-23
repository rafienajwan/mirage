"""Tests for privacy-safe custom API-log source review."""

from __future__ import annotations

import json

import pytest

from app.ml.api_log_review import (
    APILogReviewMetadata,
    review_api_log_source,
    validate_api_log_source_review,
    write_api_log_source_review,
)
from app.ml.errors import DatasetValidationError


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _metadata(**overrides) -> APILogReviewMetadata:
    values = {
        "data_origin": "staging-api-gateway",
        "collection_started_at": "2026-07-01T00:00:00Z",
        "collection_ended_at": "2026-07-02T00:00:00Z",
        "labeling_method": "analyst-reviewed",
        "sanitized": True,
        "approved_for_training": True,
    }
    values.update(overrides)
    return APILogReviewMetadata(**values)


def test_review_deduplicates_requests_without_exposing_raw_values(tmp_path):
    source = tmp_path / "production-api.jsonl"
    normal = {
        "request_id": "customer-request-123",
        "label": "normal",
        "method": "GET",
        "path": "/api/orders",
        "source_ip": "203.0.113.44",
        "user_agent": "private-client/1.0",
    }
    suspicious = {
        "request_id": "attack-request-456",
        "label": "suspicious",
        "method": "POST",
        "path": "/api/search",
        "source_ip": "198.51.100.24",
        "payload_excerpt": "password=do-not-persist&query=' or 1=1",
        "payload_indicators": ["sql-like"],
    }
    _write_jsonl(source, [normal, normal, suspicious])

    review = review_api_log_source(
        source,
        _metadata(),
        minimum_rows=2,
        minimum_rows_per_class=1,
    )
    serialized = json.dumps(review.to_dict(), sort_keys=True)

    assert review.ready_for_preparation is True
    assert review.total_rows == 3
    assert review.accepted_rows == 2
    assert review.duplicate_rows_removed == 1
    assert review.rejected_rows == 0
    assert review.conflicting_identities == 0
    assert review.label_counts == {"0": 1, "1": 1}
    assert review.input_file == source.name
    assert len(review.input_sha256) == 64
    assert "do-not-persist" not in serialized
    assert "203.0.113.44" not in serialized
    assert "customer-request-123" not in serialized


def test_review_blocks_identical_requests_with_conflicting_labels(tmp_path):
    source = tmp_path / "conflicting.jsonl"
    request = {
        "method": "GET",
        "path": "/api/orders",
        "source_ip": "203.0.113.44",
    }
    _write_jsonl(
        source,
        [
            {**request, "label": "normal"},
            {**request, "label": "suspicious"},
        ],
    )

    review = review_api_log_source(source, _metadata(), minimum_rows=1)

    assert review.ready_for_preparation is False
    assert review.conflicting_identities == 1
    assert any("conflicting labels" in blocker for blocker in review.blockers)


def test_review_counts_invalid_rows_without_echoing_their_content(tmp_path):
    source = tmp_path / "invalid.jsonl"
    source.write_text(
        '{"label":"normal","method":"GET","path":"/api/orders",'
        '"source_ip":"203.0.113.44"}\n'
        '{"label":"suspicious","payload":"private-secret"\n',
        encoding="utf-8",
    )

    review = review_api_log_source(source, _metadata(), minimum_rows=1)
    serialized = json.dumps(review.to_dict(), sort_keys=True)

    assert review.ready_for_preparation is False
    assert review.rejected_rows == 1
    assert "private-secret" not in serialized
    assert any("rejected" in blocker for blocker in review.blockers)


def test_review_requires_sanitization_and_training_approval(tmp_path):
    source = tmp_path / "unapproved.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "normal",
                "method": "GET",
                "path": "/api/orders",
                "source_ip": "203.0.113.44",
            }
        ],
    )

    review = review_api_log_source(
        source,
        _metadata(sanitized=False, approved_for_training=False),
        minimum_rows=1,
    )

    assert review.ready_for_preparation is False
    assert any("sanitized" in blocker for blocker in review.blockers)
    assert any("approved" in blocker for blocker in review.blockers)


def test_written_review_is_bound_to_the_exact_input_file(tmp_path):
    source = tmp_path / "reviewed.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "normal",
                "method": "GET",
                "path": "/api/orders",
                "source_ip": "203.0.113.44",
            },
            {
                "label": "suspicious",
                "method": "POST",
                "path": "/api/search",
                "source_ip": "198.51.100.24",
                "payload_indicators": ["sql-like"],
            },
        ],
    )
    review = review_api_log_source(
        source,
        _metadata(),
        minimum_rows=2,
        minimum_rows_per_class=1,
    )
    review_path = tmp_path / "source-review.json"
    write_api_log_source_review(review_path, review)

    validated = validate_api_log_source_review(review_path, source)

    assert validated["ready_for_preparation"] is True
    assert validated["input_sha256"] == review.input_sha256

    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="SHA-256"):
        validate_api_log_source_review(review_path, source)


def test_unready_review_cannot_be_validated_for_preparation(tmp_path):
    source = tmp_path / "unready.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "normal",
                "method": "GET",
                "path": "/api/orders",
                "source_ip": "203.0.113.44",
            }
        ],
    )
    review = review_api_log_source(
        source,
        _metadata(approved_for_training=False),
        minimum_rows=1,
        minimum_rows_per_class=1,
    )
    review_path = tmp_path / "source-review.json"
    write_api_log_source_review(review_path, review)

    with pytest.raises(DatasetValidationError, match="not approved"):
        validate_api_log_source_review(review_path, source)


def test_review_blocks_invalid_collection_window(tmp_path):
    source = tmp_path / "invalid-window.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "normal",
                "method": "GET",
                "path": "/api/orders",
                "source_ip": "203.0.113.44",
            },
            {
                "label": "suspicious",
                "method": "POST",
                "path": "/api/search",
                "source_ip": "198.51.100.24",
            },
        ],
    )

    review = review_api_log_source(
        source,
        _metadata(
            collection_started_at="2026-07-03T00:00:00Z",
            collection_ended_at="2026-07-02T00:00:00Z",
        ),
        minimum_rows=2,
        minimum_rows_per_class=1,
    )

    assert review.ready_for_preparation is False
    assert any("collection window" in blocker for blocker in review.blockers)


def test_review_rejects_oversized_jsonl_rows_without_echoing_content(tmp_path):
    source = tmp_path / "oversized.jsonl"
    secret = "private-oversized-value"
    source.write_text(
        json.dumps(
            {
                "label": "normal",
                "method": "POST",
                "path": "/api/upload",
                "source_ip": "203.0.113.44",
                "payload": secret + ("x" * 1_048_576),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    review = review_api_log_source(source, _metadata(), minimum_rows=1)
    serialized = json.dumps(review.to_dict(), sort_keys=True)

    assert review.rejected_rows == 1
    assert review.rejection_reasons == {"line_too_large": 1}
    assert secret not in serialized


def test_validation_rejects_internally_inconsistent_review_counts(tmp_path):
    source = tmp_path / "inconsistent.jsonl"
    _write_jsonl(
        source,
        [
            {
                "label": "normal",
                "method": "GET",
                "path": "/api/orders",
                "source_ip": "203.0.113.44",
            },
            {
                "label": "suspicious",
                "method": "POST",
                "path": "/api/search",
                "source_ip": "198.51.100.24",
            },
        ],
    )
    review = review_api_log_source(
        source,
        _metadata(),
        minimum_rows=2,
        minimum_rows_per_class=1,
    ).to_dict()
    review["duplicate_rows_removed"] = 1
    review_path = tmp_path / "source-review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="row counts"):
        validate_api_log_source_review(review_path, source)
