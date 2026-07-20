"""Smoke tests for the real ML training and inference path."""

import sys
from pathlib import Path

import joblib
import pytest

from app.ml.datasets import build_dataset_lineage, prepare_dataset
from app.ml.inference import RiskClassifier
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services.feature_extraction import FEATURE_NAMES
from scripts import train_model


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_train_and_load_classifier():
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    artifact = Path(".test-risk-model.joblib")
    try:
        metrics = train_risk_classifier(rows, artifact)
        classifier = RiskClassifier(artifact)

        assert artifact.exists()
        assert metrics.training_rows == 30
        assert metrics.test_rows == 10
        assert classifier.suspicious_probability(_row(1, 20).features) > 0.5
    finally:
        artifact.unlink(missing_ok=True)


def test_training_artifact_embeds_dataset_lineage(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(
        "".join(
            f'{{"label": {label}, "features": {{"request_count_log": {index}}}}}\n'
            for label in (0, 1)
            for index in range(12)
        ),
        encoding="utf-8",
    )
    prepared = tmp_path / "prepared"
    prepare_dataset(
        source,
        prepared,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    lineage = build_dataset_lineage(
        prepared / "manifest.json",
        prepared / "train.jsonl",
    )
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    artifact = tmp_path / "risk-model.joblib"

    train_risk_classifier(rows, artifact, dataset_lineage=lineage)

    payload = joblib.load(artifact)
    assert payload["feature_contract_version"] == 2
    assert payload["artifact_version"] == 2
    assert payload["dataset_lineage"] == lineage
    assert set(lineage) == {
        "dataset_name",
        "dataset_version",
        "source_kind",
        "manifest_sha256",
        "train_sha256",
        "test_sha256",
    }


def test_classifier_rejects_feature_contract_version_mismatch(tmp_path):
    artifact = tmp_path / "risk-model.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(20)]
    train_risk_classifier(rows, artifact)
    payload = joblib.load(artifact)
    payload["feature_contract_version"] = 1
    joblib.dump(payload, artifact)

    with pytest.raises(ValueError, match="feature contract version"):
        RiskClassifier(artifact)


def test_train_script_binds_reviewed_manifest(tmp_path, monkeypatch):
    source = tmp_path / "source.jsonl"
    source.write_text(
        "".join(
            f'{{"label": {label}, "features": {{"request_count_log": {index}}}}}\n'
            for label in (0, 1)
            for index in range(20)
        ),
        encoding="utf-8",
    )
    prepared = tmp_path / "prepared"
    prepare_dataset(
        source,
        prepared,
        source_kind="mirage-jsonl",
        dataset_name="runtime-export",
        dataset_version="v1",
    )
    artifact = tmp_path / "risk-model.joblib"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_model.py",
            "--input",
            str(prepared / "train.jsonl"),
            "--output",
            str(artifact),
            "--manifest",
            str(prepared / "manifest.json"),
        ],
    )

    train_model.main()

    payload = joblib.load(artifact)
    assert payload["feature_contract_version"] == 2
    assert payload["artifact_version"] == 2
    assert payload["dataset_lineage"]["dataset_name"] == "runtime-export"
