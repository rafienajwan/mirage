"""Tests for manually reviewed runtime-log batches."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from app.ml.runtime_review_batch import (  # noqa: E402
    FinalizedReviewBatch,
    aggregate_review_batches,
    finalize_review_batch,
    write_text_exact,
)
from collect_runtime_review_batch import (  # noqa: E402
    build_proxy_scenarios,
    collect_review_batch,
    ensure_outputs_available,
)
from aggregate_runtime_review_batches import aggregate_batch_files  # noqa: E402
from finalize_runtime_review_batch import fetch_finalized_review_batch  # noqa: E402


def _reviewed_batch(
    batch_id: str,
    rows: list[dict],
) -> FinalizedReviewBatch:
    export_jsonl = "".join(f"{json.dumps(row, sort_keys=True)}\n" for row in rows)
    label_counts = {
        "0": sum(row["label"] == 0 for row in rows),
        "1": sum(row["label"] == 1 for row in rows),
    }
    return FinalizedReviewBatch(
        export_jsonl=export_jsonl,
        summary={
            "schema_version": 1,
            "batch_id": batch_id,
            "labeling_method": "analyst-reviewed-dashboard",
            "approved_for_training": True,
            "event_count": len(rows),
            "label_counts": label_counts,
            "dataset_sha256": hashlib.sha256(export_jsonl.encode("utf-8")).hexdigest(),
        },
    )


def _reviewed_row(event_id: str, label: int) -> dict:
    return {
        "event_id": event_id,
        "timestamp": "2026-08-18T12:00:00Z",
        "label": label,
        "analyst_label": "normal" if label == 0 else "suspicious",
        "features": {"path_length": float(len(event_id))},
    }


def test_hash_bound_text_is_written_as_exact_utf8_bytes(tmp_path):
    content = '{"label": 0}\n{"label": 1}\n'
    output = tmp_path / "nested" / "reviewed-events.jsonl"

    write_text_exact(output, content)

    assert output.read_bytes() == content.encode("utf-8")
    assert (
        hashlib.sha256(output.read_bytes()).hexdigest()
        == hashlib.sha256(content.encode("utf-8")).hexdigest()
    )


def test_collector_builds_distinct_borderline_requests_without_labels():
    scenarios = build_proxy_scenarios(
        normal_count=1,
        borderline_count=2,
        suspicious_count=1,
    )

    assert len(scenarios) == 4
    assert len({(scenario.method, scenario.path) for scenario in scenarios}) == 4
    assert scenarios[1].method == "GET"
    assert scenarios[1].path.startswith("/api/search?")
    assert scenarios[2].headers["User-Agent"] == "curl/8.0 MIRAGE-Staging-Review"
    assert all(not hasattr(scenario, "expected_label") for scenario in scenarios)


def test_aggregator_combines_hash_bound_batches_in_deterministic_order():
    batch_b = _reviewed_batch(
        "runtime-b",
        [_reviewed_row("evt-b-normal", 0), _reviewed_row("evt-b-risk", 1)],
    )
    batch_a = _reviewed_batch(
        "runtime-a",
        [_reviewed_row("evt-a-normal", 0), _reviewed_row("evt-a-risk", 1)],
    )

    result = aggregate_review_batches([batch_b, batch_a])

    rows = [json.loads(line) for line in result.export_jsonl.splitlines()]
    assert [row["event_id"] for row in rows] == [
        "evt-a-normal",
        "evt-a-risk",
        "evt-b-normal",
        "evt-b-risk",
    ]
    assert result.summary["batch_count"] == 2
    assert result.summary["event_count"] == 4
    assert result.summary["label_counts"] == {"0": 2, "1": 2}
    assert [source["batch_id"] for source in result.summary["source_batches"]] == [
        "runtime-a",
        "runtime-b",
    ]
    assert (
        result.summary["dataset_sha256"]
        == hashlib.sha256(result.export_jsonl.encode("utf-8")).hexdigest()
    )


def test_aggregator_rejects_tampered_or_duplicate_reviewed_batches():
    batch_a = _reviewed_batch(
        "runtime-a",
        [_reviewed_row("evt-shared", 0), _reviewed_row("evt-a-risk", 1)],
    )
    tampered = FinalizedReviewBatch(
        export_jsonl=batch_a.export_jsonl + "{}\n",
        summary=batch_a.summary,
    )

    with pytest.raises(ValueError, match="runtime-a.*SHA-256"):
        aggregate_review_batches([tampered])

    batch_b = _reviewed_batch(
        "runtime-b",
        [_reviewed_row("evt-shared", 0), _reviewed_row("evt-b-risk", 1)],
    )
    with pytest.raises(ValueError, match="duplicate event_id.*evt-shared"):
        aggregate_review_batches([batch_a, batch_b])


def test_aggregator_rejects_non_object_batch_summary():
    batch = FinalizedReviewBatch(export_jsonl="", summary=[])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="summary must be an object"):
        aggregate_review_batches([batch])


def test_aggregator_revalidates_feature_vectors_from_reviewed_rows():
    row = _reviewed_row("evt-empty-features", 0)
    row["features"] = {}
    batch = _reviewed_batch(
        "runtime-invalid",
        [row, _reviewed_row("evt-risk", 1)],
    )

    with pytest.raises(ValueError, match="missing feature vector.*evt-empty-features"):
        aggregate_review_batches([batch])


def test_aggregate_script_writes_hash_bound_outputs(tmp_path):
    batch_a = _reviewed_batch(
        "runtime-a",
        [_reviewed_row("evt-a-normal", 0), _reviewed_row("evt-a-risk", 1)],
    )
    batch_b = _reviewed_batch(
        "runtime-b",
        [_reviewed_row("evt-b-normal", 0), _reviewed_row("evt-b-risk", 1)],
    )
    batch_paths = []
    for batch in (batch_a, batch_b):
        events_path = tmp_path / batch.summary["batch_id"] / "events.jsonl"
        summary_path = tmp_path / batch.summary["batch_id"] / "summary.json"
        write_text_exact(events_path, batch.export_jsonl)
        write_text_exact(
            summary_path,
            json.dumps(batch.summary, indent=2, sort_keys=True) + "\n",
        )
        batch_paths.append((events_path, summary_path))

    output = tmp_path / "aggregate" / "reviewed-events.jsonl"
    summary_output = tmp_path / "aggregate" / "reviewed-summary.json"
    result = aggregate_batch_files(
        batch_paths=batch_paths,
        output=output,
        summary_output=summary_output,
    )

    assert output.read_text(encoding="utf-8") == result.export_jsonl
    assert json.loads(summary_output.read_text(encoding="utf-8")) == result.summary

    with pytest.raises(FileExistsError, match="reviewed-events.jsonl"):
        aggregate_batch_files(
            batch_paths=batch_paths,
            output=output,
            summary_output=summary_output,
        )


@pytest.mark.asyncio
async def test_collector_creates_unlabeled_queue_without_calling_label_endpoint():
    events: list[dict] = []
    request_methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_methods.append(request.method)
        if request.url.path.startswith("/api/v1/proxy/"):
            event = {
                "event_id": f"evt-{len(events) + 1}",
                "timestamp": f"2026-08-05T12:{len(events):02d}:00Z",
                "method": request.method,
                "path": request.url.path.removeprefix("/api/v1/proxy"),
                "risk_score": 0.0,
                "decision": "allow",
                "feature_vector": {"path_length": 10.0},
                "analyst_label": None,
                "analyst_note": "",
                "ip_address": "127.0.***.***",
            }
            events.insert(0, event)
            return httpx.Response(200, json={"status": "ok"})

        if request.method == "GET" and request.url.path == "/api/v1/dashboard/events":
            return httpx.Response(200, json={"events": events})

        return httpx.Response(500, json={"detail": "unexpected request"})

    scenarios = build_proxy_scenarios(
        normal_count=1,
        borderline_count=0,
        suspicious_count=1,
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        queue, manifest = await collect_review_batch(
            client,
            base_url="http://test",
            api_key="private-local-key",
            scenarios=scenarios,
            batch_id="runtime-20260805",
        )

    assert request_methods == ["GET", "GET", "POST", "GET"]
    assert [entry["event_id"] for entry in queue["entries"]] == ["evt-1", "evt-2"]
    assert set(queue["entries"][0]) == {"event_id", "timestamp", "method", "path"}
    serialized = json.dumps(queue)
    assert "private-local-key" not in serialized
    assert "analyst_label" not in serialized
    assert "expected_label" not in serialized
    assert manifest["event_count"] == 2
    assert (
        manifest["queue_sha256"]
        == hashlib.sha256(
            (json.dumps(queue, indent=2, sort_keys=True) + "\n").encode("utf-8")
        ).hexdigest()
    )


def test_finalizer_rejects_batch_with_missing_manual_labels():
    queue = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "entries": [
            {
                "event_id": "evt-1",
                "timestamp": "2026-08-05T12:00:00Z",
                "method": "GET",
                "path": "/api/catalog/items/1",
            },
            {
                "event_id": "evt-2",
                "timestamp": "2026-08-05T12:01:00Z",
                "method": "POST",
                "path": "/api/admin/users/1",
            },
        ],
    }
    queue_text = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "collection_started_at": "2026-08-05T12:00:00Z",
        "collection_ended_at": "2026-08-05T12:02:00Z",
        "event_count": 2,
        "queue_sha256": hashlib.sha256(queue_text.encode("utf-8")).hexdigest(),
    }
    export_jsonl = (
        json.dumps(
            {
                "event_id": "evt-1",
                "timestamp": "2026-08-05T12:00:00Z",
                "label": 0,
                "analyst_label": "normal",
                "features": {"path_length": 20.0},
            }
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="manual labels.*evt-2"):
        finalize_review_batch(
            queue_text=queue_text,
            manifest=manifest,
            export_jsonl=export_jsonl,
            approved_for_training=True,
        )


def test_finalizer_exports_exact_hash_bound_batch_and_both_classes():
    queue = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "entries": [
            {
                "event_id": "evt-1",
                "timestamp": "2026-08-05T12:00:00Z",
                "method": "GET",
                "path": "/api/catalog/items/1",
            },
            {
                "event_id": "evt-2",
                "timestamp": "2026-08-05T12:01:00Z",
                "method": "POST",
                "path": "/api/admin/users/1",
            },
        ],
    }
    queue_text = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "collection_started_at": "2026-08-05T12:00:00Z",
        "collection_ended_at": "2026-08-05T12:02:00Z",
        "event_count": 2,
        "queue_sha256": hashlib.sha256(queue_text.encode("utf-8")).hexdigest(),
    }
    export_rows = [
        {
            "event_id": "unrelated",
            "timestamp": "2026-08-05T11:00:00Z",
            "label": 1,
            "analyst_label": "suspicious",
            "features": {"path_length": 99.0},
        },
        {
            "event_id": "evt-2",
            "timestamp": "2026-08-05T12:01:00Z",
            "label": 1,
            "analyst_label": "suspicious",
            "features": {"path_length": 22.0},
            "ip_address": "must-not-leak",
            "payload": "must-not-leak",
        },
        {
            "event_id": "evt-1",
            "timestamp": "2026-08-05T12:00:00Z",
            "label": 0,
            "analyst_label": "normal",
            "features": {"path_length": 20.0},
        },
    ]
    export_jsonl = "".join(json.dumps(row) + "\n" for row in export_rows)

    result = finalize_review_batch(
        queue_text=queue_text,
        manifest=manifest,
        export_jsonl=export_jsonl,
        approved_for_training=True,
    )

    rows = [json.loads(line) for line in result.export_jsonl.splitlines()]
    assert [row["event_id"] for row in rows] == ["evt-1", "evt-2"]
    assert [row["label"] for row in rows] == [0, 1]
    assert all(
        set(row) == {"event_id", "timestamp", "label", "analyst_label", "features"}
        for row in rows
    )
    assert result.summary == {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "collection_started_at": "2026-08-05T12:00:00Z",
        "collection_ended_at": "2026-08-05T12:02:00Z",
        "labeling_method": "analyst-reviewed-dashboard",
        "approved_for_training": True,
        "event_count": 2,
        "label_counts": {"0": 1, "1": 1},
        "queue_sha256": manifest["queue_sha256"],
        "dataset_sha256": hashlib.sha256(
            result.export_jsonl.encode("utf-8")
        ).hexdigest(),
    }


def test_finalizer_rejects_changed_queue_and_unapproved_training_use():
    queue_text = (
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "runtime-20260805",
                "entries": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    manifest = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "collection_started_at": "2026-08-05T12:00:00Z",
        "collection_ended_at": "2026-08-05T12:02:00Z",
        "event_count": 0,
        "queue_sha256": "0" * 64,
    }

    with pytest.raises(ValueError, match="queue SHA-256"):
        finalize_review_batch(
            queue_text=queue_text,
            manifest=manifest,
            export_jsonl="",
            approved_for_training=True,
        )

    manifest["queue_sha256"] = hashlib.sha256(queue_text.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="explicitly approved"):
        finalize_review_batch(
            queue_text=queue_text,
            manifest=manifest,
            export_jsonl="",
            approved_for_training=False,
        )


def test_collector_refuses_to_overwrite_an_existing_review_queue(tmp_path):
    queue_path = tmp_path / "manual-review-queue.json"
    manifest_path = tmp_path / "manual-review-manifest.json"
    queue_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="manual-review-queue.json"):
        ensure_outputs_available(queue_path, manifest_path)


@pytest.mark.asyncio
async def test_finalizer_script_fetches_dashboard_export_with_operator_key():
    queue = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "entries": [
            {
                "event_id": "evt-1",
                "timestamp": "2026-08-05T12:00:00Z",
                "method": "GET",
                "path": "/api/catalog/items/1",
            },
            {
                "event_id": "evt-2",
                "timestamp": "2026-08-05T12:01:00Z",
                "method": "POST",
                "path": "/api/admin/users/1",
            },
        ],
    }
    queue_text = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": 1,
        "batch_id": "runtime-20260805",
        "collection_started_at": "2026-08-05T12:00:00Z",
        "collection_ended_at": "2026-08-05T12:02:00Z",
        "event_count": 2,
        "queue_sha256": hashlib.sha256(queue_text.encode("utf-8")).hexdigest(),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and request.url.path == "/api/v1/dashboard/training-data/export"
            and request.headers.get("X-Mirage-API-Key") == "private-local-key"
        ):
            rows = [
                {
                    "event_id": "evt-1",
                    "timestamp": "2026-08-05T12:00:00Z",
                    "label": 0,
                    "analyst_label": "normal",
                    "features": {"path_length": 20.0},
                },
                {
                    "event_id": "evt-2",
                    "timestamp": "2026-08-05T12:01:00Z",
                    "label": 1,
                    "analyst_label": "suspicious",
                    "features": {"path_length": 22.0},
                },
            ]
            return httpx.Response(
                200,
                content="".join(json.dumps(row) + "\n" for row in rows),
            )
        return httpx.Response(401, json={"detail": "invalid request"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await fetch_finalized_review_batch(
            client,
            base_url="http://test",
            api_key="private-local-key",
            queue_text=queue_text,
            manifest=manifest,
            approved_for_training=True,
        )

    assert result.summary["event_count"] == 2
    assert result.summary["label_counts"] == {"0": 1, "1": 1}
