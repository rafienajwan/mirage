"""Tests for guarded ML promotion-readiness evaluation."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from app.core import config
from app.schemas.dashboard import MLPromotionReadiness
from app.schemas.event import EventRecord
from app.schemas.ml import MLShadowScore
from app.services.ml_promotion import (
    ClassifierRates,
    evaluate_ml_promotion,
    labeled_shadow_comparison,
)


def _settings(**overrides):
    values = {
        "ml_model_artifact": "C:/private/artifacts/risk-model.joblib",
        "ml_dataset_manifest": "C:/private/data/manifest.json",
        "ml_promotion_min_total_rows": 1000,
        "ml_promotion_min_rows_per_class": 100,
        "ml_promotion_min_shadow_events": 500,
        "ml_promotion_min_labeled_events": 4,
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
        labeled_events=_four_events(),
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
            ml_promotion_min_labeled_events=0,
        ),
        shadow_summary=_summary(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
    )

    assert report.status == "blocked"
    assert {gate.code for gate in report.gates if not gate.passed} == {
        "invalid_min_total_rows",
        "invalid_min_labeled_events",
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


def test_promotion_re_reviews_dataset_when_a_split_file_changes(tmp_path):
    artifact = tmp_path / "risk-model.joblib"
    manifest = tmp_path / "manifest.json"
    test_split = tmp_path / "test.jsonl"
    artifact.write_text("artifact", encoding="utf-8")
    manifest.write_text(
        '{"files": {"train": "train.jsonl", "test": "test.jsonl"}}', encoding="utf-8"
    )
    (tmp_path / "train.jsonl").write_text("{}\n", encoding="utf-8")
    test_split.write_text("{}\n", encoding="utf-8")
    calls = {"dataset": 0}

    def dataset_reviewer(*_args, **_kwargs):
        calls["dataset"] += 1
        return _dataset_review()

    configured = _settings(
        ml_model_artifact=str(artifact),
        ml_dataset_manifest=str(manifest),
    )
    for content in ("{}\n", '{"replaced": true}\n'):
        test_split.write_text(content, encoding="utf-8")
        evaluate_ml_promotion(
            settings=configured,
            shadow_summary=_summary(),
            artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
            dataset_reviewer=dataset_reviewer,
        )

    assert calls == {"dataset": 2}


@pytest.mark.asyncio
async def test_promotion_endpoint_requires_operator_api_key(client, monkeypatch):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, api_key="operator-key")
    )

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


def _event(label: str, model: str, heuristic: str | None, final: str = "allow"):
    shadow = {
        "artifact": "risk-model.joblib",
        "probability": 0.9 if model == "redirect_to_decoy" else 0.1,
        "score": 90.0 if model == "redirect_to_decoy" else 10.0,
        "prediction": "suspicious" if model == "redirect_to_decoy" else "normal",
        "shadow_decision": model,
        "agrees_with_decision": model == (heuristic or final),
    }
    if heuristic is not None:
        shadow["heuristic_decision"] = heuristic
    return EventRecord.model_validate(
        {
            "event_id": f"evt-{label}-{model}-{heuristic}-{final}",
            "timestamp": "2026-11-09T00:00:00Z",
            "ip_address": "10.0.0.x",
            "path": "/api",
            "method": "GET",
            "risk_score": 10.0,
            "decision": final,
            "ml_shadow": shadow,
            "analyst_label": label,
        }
    )


def _compare(events):
    return labeled_shadow_comparison(events, artifact="risk-model.joblib")


def _four_events():
    # Model: TP, FN, TN, TN -> precision 1.0, recall 0.5, FPR 0.0.
    # Heuristic: TP, FN, FP, TN -> precision 0.5, recall 0.5, FPR 0.5.
    return [
        _event("suspicious", "redirect_to_decoy", "redirect_to_decoy"),
        _event("false_negative", "allow", "allow"),
        _event("normal", "allow", "redirect_to_decoy"),
        _event("false_positive", "allow", "monitor"),
    ]


def test_labeled_comparison_rates():
    comparison = _compare(_four_events())

    assert comparison.events == 4
    assert comparison.model == ClassifierRates(
        precision=1.0, recall=0.5, false_positive_rate=0.0
    )
    assert comparison.heuristic == ClassifierRates(
        precision=0.5, recall=0.5, false_positive_rate=0.5
    )


def test_labeled_comparison_skips_events_without_label_or_shadow():
    unlabeled = _event("normal", "allow", "allow").model_copy(
        update={"analyst_label": None}
    )
    unscored = _event("normal", "allow", "allow").model_copy(update={"ml_shadow": None})

    assert _compare([unlabeled, unscored]).events == 0


def test_labeled_comparison_falls_back_to_final_decision():
    events = [
        _event("suspicious", "redirect_to_decoy", None, final="redirect_to_decoy"),
        _event("normal", "allow", None, final="redirect_to_decoy"),
    ]

    comparison = _compare(events)

    assert comparison.heuristic == ClassifierRates(
        precision=0.5, recall=1.0, false_positive_rate=1.0
    )


def test_old_shadow_rows_read_back():
    stored = {
        "artifact": "risk-model.joblib",
        "probability": 0.2,
        "score": 20.0,
        "prediction": "normal",
        "shadow_decision": "allow",
        "agrees_with_decision": True,
    }

    assert MLShadowScore.model_validate(stored).heuristic_decision is None


def _labeled_gate(events, **settings_overrides):
    report = evaluate_ml_promotion(
        settings=_settings(**settings_overrides),
        shadow_summary=_summary(),
        labeled_events=events,
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
        lineage_reviewer=lambda *_args: True,
    )
    gate = next(g for g in report.gates if g.code == "labeled_model_vs_heuristic")
    return report, gate


def test_labeled_gate_passes_when_model_matches_or_beats_heuristic():
    report, gate = _labeled_gate(_four_events())

    assert gate.passed is True
    assert report.status == "eligible"
    for number in ("1.0", "0.5"):
        assert number in gate.message


def test_labeled_gate_fails_when_model_precision_is_lower():
    events = [
        _event("suspicious", "redirect_to_decoy", "redirect_to_decoy"),
        _event("false_negative", "allow", "allow"),
        _event("normal", "redirect_to_decoy", "allow"),
        _event("false_positive", "allow", "allow"),
    ]

    report, gate = _labeled_gate(events)

    assert gate.passed is False
    assert report.status != "eligible"


def test_labeled_gate_fails_below_minimum_labeled_events():
    report, gate = _labeled_gate(_four_events(), ml_promotion_min_labeled_events=5)

    assert gate.passed is False
    assert gate.actual == 4
    assert gate.required == 5
    assert report.status != "eligible"


def test_low_agreement_no_longer_blocks_promotion():
    report = evaluate_ml_promotion(
        settings=_settings(),
        shadow_summary=_summary(agreement=0.5),
        labeled_events=_four_events(),
        artifact_reviewer=lambda *_args, **_kwargs: _artifact_review(),
        dataset_reviewer=lambda *_args, **_kwargs: _dataset_review(),
        lineage_reviewer=lambda *_args: True,
    )

    gate = next(g for g in report.gates if g.code == "shadow_agreement_rate")
    assert gate.actual == 0.5
    assert report.status == "eligible"


def test_labeled_gate_fails_without_any_suspicious_label():
    events = [_event("normal", "allow", "allow")] * 60 + [
        _event("false_positive", "allow", "redirect_to_decoy")
    ] * 60

    report, gate = _labeled_gate(events, ml_promotion_min_labeled_events=100)

    assert gate.passed is False
    assert "suspicious and one normal" in gate.message
    assert report.status != "eligible"


def test_labeled_gate_fails_when_model_never_redirects():
    events = [_event("suspicious", "allow", "allow")] * 60 + [
        _event("normal", "allow", "allow")
    ] * 60

    report, gate = _labeled_gate(events, ml_promotion_min_labeled_events=100)

    assert gate.passed is False
    assert "redirected none" in gate.message
    assert report.status != "eligible"


def test_rates_with_empty_denominator_are_none():
    comparison = _compare([_event("normal", "allow", "allow")])

    assert comparison.model == ClassifierRates(
        precision=None, recall=None, false_positive_rate=0.0
    )


def test_labeled_comparison_ignores_events_scored_by_another_artifact():
    other = _event("suspicious", "allow", "redirect_to_decoy")
    other = other.model_copy(
        update={"ml_shadow": other.ml_shadow.model_copy(update={"artifact": "a.joblib"})}
    )

    comparison = labeled_shadow_comparison(
        [*_four_events(), other], artifact="risk-model.joblib"
    )

    assert comparison.events == 4
    assert comparison.model.recall == 0.5
