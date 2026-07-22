"""Tests for reviewed API-log command-line workflows."""

from __future__ import annotations

import json
import sys

from scripts import prepare_dataset as prepare_script
from scripts import review_api_log_source as review_script


def _write_source(path) -> None:
    rows = [
        {
            "label": label,
            "source_ip": f"203.0.113.{index + 10}",
            "method": "GET",
            "path": f"/api/{label}/{index}",
        }
        for label in ("normal", "suspicious")
        for index in range(10)
    ]
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def test_review_then_prepare_cli_creates_review_bound_dataset(tmp_path, monkeypatch):
    source = tmp_path / "production-api.jsonl"
    review_path = tmp_path / "production-api-review.json"
    output_dir = tmp_path / "prepared"
    _write_source(source)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review_api_log_source.py",
            "--input",
            str(source),
            "--output",
            str(review_path),
            "--data-origin",
            "staging-api-gateway",
            "--collection-started-at",
            "2026-07-01T00:00:00Z",
            "--collection-ended-at",
            "2026-07-02T00:00:00Z",
            "--labeling-method",
            "analyst-reviewed",
            "--sanitized",
            "--approved-for-training",
        ],
    )

    review_script.main()

    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["ready_for_preparation"] is True
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_dataset.py",
            "--source",
            "reviewed-api-log-jsonl",
            "--input",
            str(source),
            "--source-review",
            str(review_path),
            "--output-dir",
            str(output_dir),
            "--dataset-name",
            "production-api",
            "--dataset-version",
            "v1",
        ],
    )

    prepare_script.main()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_kind"] == "reviewed-api-log-jsonl"
    assert manifest["files"]["source_review"] == "source-review.json"
