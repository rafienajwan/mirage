"""Tests for trained model artifact review."""

from pathlib import Path

import joblib

from app.ml.artifacts import review_model_artifact
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.services.feature_extraction import FEATURE_NAMES


def _row(label: int, offset: float) -> LabeledFeatures:
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["request_count_log"] = offset if label else offset / 100
    features["sensitive_path"] = float(label)
    features["high_risk_indicator_count"] = float(label * 2)
    return LabeledFeatures(features=features, label=label)


def test_review_model_artifact_marks_valid_shadow_ready(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(70)]
    train_risk_classifier(rows, artifact)

    review = review_model_artifact(artifact)

    assert review.shadow_ready is True
    assert review.artifact_version == 1
    assert review.feature_contract_version == 3
    assert review.blockers == []
    assert review.metrics["training_rows"] == 105
    assert review.metrics["test_rows"] == 35


def test_review_model_artifact_rejects_feature_contract_mismatch(tmp_path):
    artifact = tmp_path / "bad_model.joblib"
    joblib.dump(
        {
            "artifact_version": 1,
            "feature_names": ("unexpected",),
            "metrics": {
                "precision": 1.0,
                "recall": 1.0,
                "f1_score": 1.0,
                "false_positive_rate": 0.0,
                "training_rows": 30,
                "test_rows": 10,
            },
            "model": object(),
        },
        artifact,
    )

    review = review_model_artifact(artifact)

    assert review.shadow_ready is False
    assert "Artifact feature contract does not match the gateway" in review.blockers


def test_review_model_artifact_rejects_feature_contract_version_mismatch(tmp_path):
    artifact = tmp_path / "bad_contract_version.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(70)]
    train_risk_classifier(rows, artifact)
    payload = joblib.load(artifact)
    payload["feature_contract_version"] = 1
    joblib.dump(payload, artifact)

    review = review_model_artifact(artifact)

    assert review.shadow_ready is False
    assert (
        "Artifact feature contract version does not match the gateway"
        in review.blockers
    )


def test_review_model_artifact_reports_missing_file(tmp_path):
    review = review_model_artifact(Path(tmp_path / "missing.joblib"))

    assert review.shadow_ready is False
    assert review.blockers == ["Artifact file does not exist"]


def test_review_model_artifact_rejects_non_finite_metrics(tmp_path):
    artifact = tmp_path / "non-finite.joblib"
    joblib.dump(
        {
            "artifact_version": 1,
            "feature_names": FEATURE_NAMES,
            "metrics": {
                "precision": float("nan"),
                "recall": float("inf"),
                "f1_score": 1.0,
                "false_positive_rate": 0.0,
                "training_rows": 30,
                "test_rows": 10,
            },
            "model": object(),
        },
        artifact,
    )

    review = review_model_artifact(artifact)

    assert review.shadow_ready is False
    assert "Metric 'precision' is missing or non-numeric" in review.blockers
    assert "Metric 'recall' is missing or non-numeric" in review.blockers


def test_review_model_artifact_exposes_valid_dataset_lineage(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(70)]
    lineage = {
        "dataset_name": "csic-http-2010",
        "dataset_version": "redata-rwuusv-v1",
        "source_kind": "csic-http-dir",
        "manifest_sha256": "a" * 64,
        "train_sha256": "b" * 64,
        "test_sha256": "c" * 64,
    }
    train_risk_classifier(rows, artifact, dataset_lineage=lineage)

    review = review_model_artifact(artifact)

    assert review.shadow_ready is True
    assert review.artifact_version == 2
    assert review.dataset_lineage == lineage


def test_review_model_artifact_rejects_invalid_dataset_lineage(tmp_path):
    artifact = tmp_path / "risk_model.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(70)]
    train_risk_classifier(
        rows,
        artifact,
        dataset_lineage={
            "dataset_name": "csic-http-2010",
            "dataset_version": "redata-rwuusv-v1",
            "source_kind": "csic-http-dir",
            "manifest_sha256": "bad",
            "train_sha256": "b" * 64,
            "test_sha256": "c" * 64,
        },
    )

    review = review_model_artifact(artifact)

    assert review.shadow_ready is False
    assert "Artifact dataset lineage manifest_sha256 is invalid" in review.blockers


GOOD_METRICS = {
    "precision": 0.95,
    "recall": 0.8,
    "f1_score": 0.87,
    "false_positive_rate": 0.01,
    "training_rows": 100,
    "test_rows": 30,
}


def _metrics_artifact(tmp_path, **metric_overrides):
    from app.services.feature_extraction import FEATURE_CONTRACT_VERSION

    metrics = {**GOOD_METRICS, **metric_overrides}
    metrics = {key: value for key, value in metrics.items() if value is not None}
    artifact = tmp_path / "thresholds.joblib"
    joblib.dump(
        {
            "artifact_version": 1,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "feature_names": FEATURE_NAMES,
            "metrics": metrics,
            "model": object(),
        },
        artifact,
    )
    return artifact


def test_review_passes_artifact_meeting_all_thresholds(tmp_path):
    review = review_model_artifact(_metrics_artifact(tmp_path))

    assert review.blockers == []
    assert review.shadow_ready is True


def test_review_blocks_fpr_above_two_percent(tmp_path):
    review = review_model_artifact(
        _metrics_artifact(tmp_path, false_positive_rate=0.05)
    )

    assert review.shadow_ready is False
    assert "False-positive rate 0.050 is above 0.020" in review.blockers


def test_review_blocks_small_training_set(tmp_path):
    review = review_model_artifact(_metrics_artifact(tmp_path, training_rows=99))

    assert review.shadow_ready is False
    assert "Training rows 99 is below 100" in review.blockers


def test_review_blocks_undefined_false_positive_rate(tmp_path):
    review = review_model_artifact(
        _metrics_artifact(tmp_path, false_positive_rate=None)
    )

    assert review.shadow_ready is False
    assert "False-positive rate is unavailable" in review.blockers


def test_holdout_without_negatives_has_no_false_positive_rate():
    from app.ml.artifacts import classification_metrics

    metrics = classification_metrics([1, 1, 1], [1, 0, 1])

    assert metrics["false_positive_rate"] is None
