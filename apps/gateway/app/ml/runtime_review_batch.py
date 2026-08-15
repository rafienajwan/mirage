"""Validate and finalize hash-bound batches of manually reviewed runtime events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_EXPORTED_FIELDS = ("event_id", "timestamp", "label", "analyst_label", "features")


@dataclass(frozen=True)
class FinalizedReviewBatch:
    """Sanitized dataset and provenance summary for one reviewed batch."""

    export_jsonl: str
    summary: dict[str, Any]


def serialize_review_queue(queue: dict[str, Any]) -> str:
    """Return the canonical on-disk representation used for hash validation."""
    return json.dumps(queue, indent=2, sort_keys=True) + "\n"


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def write_text_exact(path: Path, content: str) -> None:
    """Write canonical UTF-8 bytes without platform newline translation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _parse_export_rows(export_jsonl: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line_number, raw_line in enumerate(export_jsonl.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid export JSON on line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"export line {line_number} must be an object")
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError(f"export line {line_number} has no event_id")
        if event_id in rows:
            raise ValueError(f"duplicate exported event_id: {event_id}")
        rows[event_id] = row
    return rows


def _validate_queue(
    queue_text: str,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256_text(queue_text) != manifest.get("queue_sha256"):
        raise ValueError("review queue SHA-256 does not match its manifest")
    try:
        queue = json.loads(queue_text)
    except json.JSONDecodeError as exc:
        raise ValueError("review queue is not valid JSON") from exc
    if not isinstance(queue, dict) or queue.get("schema_version") != 1:
        raise ValueError("unsupported review queue schema")
    if queue.get("batch_id") != manifest.get("batch_id"):
        raise ValueError("review queue batch_id does not match its manifest")
    entries = queue.get("entries")
    if not isinstance(entries, list):
        raise ValueError("review queue entries must be a list")
    if len(entries) != manifest.get("event_count"):
        raise ValueError("review queue event count does not match its manifest")

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("review queue entries must be objects")
        event_id = entry.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("review queue entry has no event_id")
        if event_id in seen:
            raise ValueError(f"duplicate review queue event_id: {event_id}")
        seen.add(event_id)
    return queue, entries


def finalize_review_batch(
    *,
    queue_text: str,
    manifest: dict[str, Any],
    export_jsonl: str,
    approved_for_training: bool,
) -> FinalizedReviewBatch:
    """Filter the dashboard export to one complete, explicitly approved batch."""
    _, entries = _validate_queue(queue_text, manifest)
    if not approved_for_training:
        raise ValueError("review batch must be explicitly approved for training")
    if not entries:
        raise ValueError("review batch must contain at least one event")

    exported_by_id = _parse_export_rows(export_jsonl)
    missing = [entry["event_id"] for entry in entries if entry["event_id"] not in exported_by_id]
    if missing:
        raise ValueError(
            "manual labels or feature vectors are missing for: " + ", ".join(missing)
        )

    sanitized_rows: list[dict[str, Any]] = []
    label_counts = {"0": 0, "1": 0}
    for entry in entries:
        source = exported_by_id[entry["event_id"]]
        label = source.get("label")
        if label not in (0, 1):
            raise ValueError(f"invalid binary label for {entry['event_id']}")
        analyst_label = source.get("analyst_label")
        if not isinstance(analyst_label, str) or not analyst_label:
            raise ValueError(f"missing analyst label for {entry['event_id']}")
        features = source.get("features")
        if not isinstance(features, dict) or not features:
            raise ValueError(f"missing feature vector for {entry['event_id']}")
        sanitized_rows.append({field: source[field] for field in _EXPORTED_FIELDS})
        label_counts[str(label)] += 1

    if 0 in label_counts.values():
        raise ValueError("review batch must contain both normal and suspicious classes")

    finalized_jsonl = "".join(
        f"{json.dumps(row, sort_keys=True)}\n" for row in sanitized_rows
    )
    summary = {
        "schema_version": 1,
        "batch_id": manifest["batch_id"],
        "collection_started_at": manifest["collection_started_at"],
        "collection_ended_at": manifest["collection_ended_at"],
        "labeling_method": "analyst-reviewed-dashboard",
        "approved_for_training": True,
        "event_count": len(sanitized_rows),
        "label_counts": label_counts,
        "queue_sha256": manifest["queue_sha256"],
        "dataset_sha256": sha256_text(finalized_jsonl),
    }
    return FinalizedReviewBatch(export_jsonl=finalized_jsonl, summary=summary)
