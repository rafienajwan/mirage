"""Tests for deterministic API-domain fixture dataset generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_api_domain_fixture_dataset import build_fixture_rows, write_fixture_jsonl  # noqa: E402

from app.ml.datasets import prepare_dataset  # noqa: E402


def test_build_fixture_rows_creates_balanced_api_log_records():
    rows = build_fixture_rows(normal_count=3, suspicious_count=3)

    assert [row["label"] for row in rows].count("normal") == 3
    assert [row["label"] for row in rows].count("suspicious") == 3
    assert len({row["event_id"] for row in rows}) == 6
    assert all(row["request"]["path"].startswith("/") for row in rows)


def test_fixture_jsonl_can_be_prepared_with_api_log_adapter(tmp_path: Path):
    raw_path = tmp_path / "api-domain-fixture.jsonl"
    output_dir = tmp_path / "prepared"

    write_fixture_jsonl(
        raw_path,
        build_fixture_rows(normal_count=20, suspicious_count=20),
    )
    manifest = prepare_dataset(
        raw_path,
        output_dir,
        source_kind="api-log-jsonl",
        dataset_name="api-domain-fixture",
        dataset_version="test",
    )

    assert manifest.total_rows == 40
    assert manifest.train_rows == 30
    assert manifest.test_rows == 10
    assert manifest.label_counts == {"0": 20, "1": 20}
    first_train_row = json.loads((output_dir / "train.jsonl").read_text().splitlines()[0])
    assert set(first_train_row) >= {"features", "label", "source", "record_id"}
