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
    finalize_review_batch,
    write_text_exact,
)
from collect_runtime_review_batch import (  # noqa: E402
    build_proxy_scenarios,
    collect_review_batch,
    ensure_outputs_available,
)
from finalize_runtime_review_batch import fetch_finalized_review_batch  # noqa: E402


def test_hash_bound_text_is_written_as_exact_utf8_bytes(tmp_path):
    content = '{"label": 0}\n{"label": 1}\n'
    output = tmp_path / "nested" / "reviewed-events.jsonl"

    write_text_exact(output, content)

    assert output.read_bytes() == content.encode("utf-8")
    assert hashlib.sha256(output.read_bytes()).hexdigest() == hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


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

    scenarios = build_proxy_scenarios(normal_count=1, suspicious_count=1)
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
    assert manifest["queue_sha256"] == hashlib.sha256(
        (json.dumps(queue, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()


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
    export_jsonl = json.dumps(
        {
            "event_id": "evt-1",
            "timestamp": "2026-08-05T12:00:00Z",
            "label": 0,
            "analyst_label": "normal",
            "features": {"path_length": 20.0},
        }
    ) + "\n"

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
        "dataset_sha256": hashlib.sha256(result.export_jsonl.encode("utf-8")).hexdigest(),
    }


def test_finalizer_rejects_changed_queue_and_unapproved_training_use():
    queue_text = json.dumps(
        {
            "schema_version": 1,
            "batch_id": "runtime-20260805",
            "entries": [],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
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
