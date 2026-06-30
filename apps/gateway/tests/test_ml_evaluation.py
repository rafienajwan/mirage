"""Tests for holdout evaluation of trained model artifacts."""

from __future__ import annotations

import json

from app.ml.evaluation import evaluate_model_artifact
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services.feature_extraction import FEATURE_NAMES


def _features(label: int, offset: float) -> dict[str, float]:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return features


def _row(label: int, offset: float) -> LabeledFeatures:
    return LabeledFeatures(features=_features(label, offset), label=label)


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def test_evaluate_model_artifact_marks_holdout_ready(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    holdout = tmp_path / "test.jsonl"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(30)]
    train_risk_classifier(rows, artifact)
    _write_jsonl(
        holdout,
        [
            {"label": label, "features": _features(label, float(index + 100))}
            for label in (0, 1)
            for index in range(8)
        ],
    )

    evaluation = evaluate_model_artifact(artifact, holdout)

    assert evaluation.holdout_ready is True
    assert evaluation.blockers == []
    assert evaluation.metrics["evaluated_rows"] == 16
    assert evaluation.metrics["normal_rows"] == 8
    assert evaluation.metrics["suspicious_rows"] == 8
    assert evaluation.metrics["f1_score"] >= 0.5


def test_evaluate_model_artifact_blocks_strict_threshold(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    holdout = tmp_path / "test.jsonl"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(30)]
    train_risk_classifier(rows, artifact)
    _write_jsonl(
        holdout,
        [
            {"label": label, "features": _features(label, float(index + 100))}
            for label in (0, 1)
            for index in range(8)
        ],
    )

    evaluation = evaluate_model_artifact(
        artifact,
        holdout,
        min_precision=1.1,
    )

    assert evaluation.holdout_ready is False
    assert any("Precision" in blocker for blocker in evaluation.blockers)
