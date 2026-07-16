"""Tests for guarded ML promotion-readiness evaluation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import security
from app.schemas.dashboard import MLPromotionReadiness
from app.services.ml_promotion import evaluate_ml_promotion


def _settings(**overrides):
    values = {
        "ml_model_artifact": "C:/private/artifacts/risk-model.joblib",
        "ml_dataset_manifest": "C:/private/data/manifest.json",
        "ml_promotion_min_total_rows": 1000,
        "ml_promotion_min_rows_per_class": 100,
        "ml_promotion_min_shadow_events": 500,
        "ml_promotion_min_agreement_rate": 0.8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _artifact_review(*, ready: bool = True, dataset_lineage=None):
    return SimpleNamespace(
        shadow_ready=ready,
        metrics={"precision": 0.91, "recall": 0.89, "f1_score": 0.9},
        blockers=[] if ready else ["Artifact feature contract is invalid"],
        warnings=[],
        dataset_lineage=dataset_lineage,
    )


def _dataset_review(*, ready: bool = True):
    return SimpleNamespace(
        ready_for_training=ready,
        dataset_name="api-domain",
        dataset_version="v2",
        source_kind="mirage-jsonl",
        total_rows=2000,
        label_counts={"0": 1000, "1": 1000},
        blockers=[] if ready else ["Dataset split is invalid"],
        warnings=[],
    )


def _summary(*, events: int = 600, agreement: float = 0.9):
    return SimpleNamespace(shadow_events=events, agreement_rate=agreement)


def test_promotion_is_unavailable_without_required_paths():
    report = evaluate_ml_promotion(
        settings=_settings(ml_model_artifact=None, ml_dataset_manifest=None),
        shadow_summary=_summary(),
    )

    assert report.status == "unavailable"
    assert {gate.code for gate in report.gates if not gate.passed} == {
        "artifact_not_configured",
        "dataset_not_configured",
    }


def test_promotion_is_blocked_by_invalid_reviews_without_leaking_paths():
    report = evaluate_ml_promotion(
        settings=_settings(),
        shadow_summary=_summary(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(ready=False),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(ready=False),
    )

    assert report.status == "blocked"
    assert report.artifact == "risk-model.joblib"
    assert report.dataset_manifest == "manifest.json"
    assert "C:/private" not in report.model_dump_json()


def test_promotion_needs_more_shadow_observation():
    report = evaluate_ml_promotion(
        settings=_settings(),
        shadow_summary=_summary(events=120, agreement=0.92),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
        lineage_reviewer=lambda *_args: True,
    )

    assert report.status == "needs_observation"
    gate = next(gate for gate in report.gates if gate.code == "shadow_event_count")
    assert gate.actual == 120
    assert gate.required == 500


def test_promotion_is_eligible_only_when_every_gate_passes():
    report = evaluate_ml_promotion(
        settings=_settings(),
        shadow_summary=_summary(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
        lineage_reviewer=lambda *_args: True,
    )

    assert report.status == "eligible"
    assert all(gate.passed for gate in report.gates)
    assert report.routing_unchanged is True


def test_promotion_blocks_artifact_dataset_lineage_mismatch(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"dataset_name":"api-domain"}', encoding="utf-8")
    report = evaluate_ml_promotion(
        settings=_settings(ml_dataset_manifest=str(manifest)),
        shadow_summary=_summary(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(
            dataset_lineage={
                "dataset_name": "different-dataset",
                "dataset_version": "v2",
                "source_kind": "mirage-jsonl",
                "manifest_sha256": "a" * 64,
                "train_sha256": "b" * 64,
                "test_sha256": "c" * 64,
            }
        ),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
    )

    gate = next(gate for gate in report.gates if gate.code == "dataset_lineage")
    assert report.status == "blocked"
    assert gate.passed is False


def test_promotion_blocks_invalid_threshold_configuration():
    report = evaluate_ml_promotion(
        settings=_settings(
            ml_promotion_min_total_rows=0,
            ml_promotion_min_agreement_rate=1.5,
        ),
        shadow_summary=_summary(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
    )

    assert report.status == "blocked"
    assert {gate.code for gate in report.gates if not gate.passed} == {
        "invalid_min_total_rows",
        "invalid_min_agreement_rate",
    }


def test_promotion_caches_unchanged_artifact_and_dataset_reviews(tmp_path):
    artifact = tmp_path / "risk-model.joblib"
    manifest = tmp_path / "manifest.json"
    artifact.write_text("artifact", encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    calls = {"artifact": 0, "dataset": 0}

    def artifact_reviewer(*_args, **_kwargs):
        calls["artifact"] += 1
        return _artifact_review()

    def dataset_reviewer(*_args, **_kwargs):
        calls["dataset"] += 1
        return _dataset_review()

    configured = _settings(
        ml_model_artifact=str(artifact),
        ml_dataset_manifest=str(manifest),
    )
    for _ in range(2):
        evaluate_ml_promotion(
            settings=configured,
            shadow_summary=_summary(),
            artifact_reviewer=artifact_reviewer,
            dataset_reviewer=dataset_reviewer,
        )

    assert calls == {"artifact": 1, "dataset": 1}


@pytest.mark.asyncio
async def test_promotion_endpoint_requires_operator_api_key(client, monkeypatch):
    monkeypatch.setattr(security, "settings", SimpleNamespace(api_key="operator-key"))

    denied = await client.get("/api/v1/dashboard/ml-promotion/readiness")
    allowed = await client.get(
        "/api/v1/dashboard/ml-promotion/readiness",
        headers={"X-Mirage-API-Key": "operator-key"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "unavailable"


@pytest.mark.asyncio
async def test_dashboard_snapshot_includes_promotion_readiness(monkeypatch):
    from app.services import dashboard_stream

    expected = MLPromotionReadiness(
        status="needs_observation",
        artifact="risk-model.joblib",
        dataset_manifest="manifest.json",
        gates=[],
        warnings=[],
    )
    monkeypatch.setattr(
        dashboard_stream,
        "evaluate_ml_promotion",
        lambda **_kwargs: expected,
        raising=False,
    )

    snapshot = await dashboard_stream.build_dashboard_snapshot()

    assert snapshot["ml_promotion_readiness"] == expected.model_dump(mode="json")
