"""Model artifacts are verified against a pinned SHA-256 before unpickling."""

import hashlib
from types import SimpleNamespace

import pytest

from app.ml import artifact_integrity, inference
from app.ml import artifacts as artifacts_module
from app.ml.artifact_integrity import (
    ArtifactIntegrityError,
    load_verified_artifact,
    sha256_file,
)
from app.ml.training import train_risk_classifier
from app.services import ml_shadow
from tests.test_ml_shadow import _row

WRONG = "0" * 64


@pytest.fixture
def blob(tmp_path):
    path = tmp_path / "model.joblib"
    path.write_bytes(b"not really a model")
    return path


@pytest.fixture
def trained(tmp_path):
    path = tmp_path / "risk.joblib"
    rows = [_row(label, float(index + 1)) for label in (0, 1) for index in range(70)]
    train_risk_classifier(rows, path)
    return path


def _forbid_load(*_args, **_kwargs):
    raise AssertionError("joblib.load must not run when the digest does not match")


def test_verify_matches(trained):
    digest = hashlib.sha256(trained.read_bytes()).hexdigest()
    assert load_verified_artifact(trained, digest)["model"] is not None


def test_sha256_file(blob):
    assert sha256_file(blob) == hashlib.sha256(blob.read_bytes()).hexdigest()


def test_verify_mismatch_raises(blob):
    with pytest.raises(ArtifactIntegrityError):
        load_verified_artifact(blob, WRONG)


def test_uppercase_digest_accepted(trained):
    assert load_verified_artifact(trained, sha256_file(trained).upper()) is not None


@pytest.mark.parametrize("digest", ["abc", "z" * 64, ""])
def test_bad_digest_format_raises(blob, digest):
    with pytest.raises(ArtifactIntegrityError):
        load_verified_artifact(blob, digest)


def test_classifier_does_not_load_on_mismatch(blob, monkeypatch):
    monkeypatch.setattr(artifact_integrity.joblib, "load", _forbid_load)
    with pytest.raises(ArtifactIntegrityError):
        inference.RiskClassifier(blob, expected_sha256=WRONG)


def test_classifier_loads_when_digest_matches(trained):
    classifier = inference.RiskClassifier(trained, expected_sha256=sha256_file(trained))
    assert classifier.model is not None


def test_review_blocks_on_mismatch_without_loading(blob, monkeypatch):
    monkeypatch.setattr(artifact_integrity.joblib, "load", _forbid_load)
    review = artifacts_module.review_model_artifact(blob, expected_sha256=WRONG)
    assert review.shadow_ready is False
    assert review.blockers == [
        "Artifact SHA-256 does not match MIRAGE_MODEL_ARTIFACT_SHA256"
    ]


def _shadow_settings(artifact, digest):
    return SimpleNamespace(
        ml_model_artifact=str(artifact),
        ml_model_artifact_sha256=digest,
        ml_shadow_monitor_threshold=0.35,
        ml_shadow_redirect_threshold=0.65,
    )


def test_shadow_loader_returns_none_on_mismatch(trained, monkeypatch):
    monkeypatch.setattr(ml_shadow, "settings", _shadow_settings(trained, WRONG))
    ml_shadow._load_classifier.cache_clear()
    try:
        assert ml_shadow._load_classifier() is None
    finally:
        ml_shadow._load_classifier.cache_clear()


def test_shadow_loader_accepts_pinned_artifact(trained, monkeypatch):
    monkeypatch.setattr(
        ml_shadow, "settings", _shadow_settings(trained, sha256_file(trained))
    )
    ml_shadow._load_classifier.cache_clear()
    try:
        assert ml_shadow._load_classifier() is not None
    finally:
        ml_shadow._load_classifier.cache_clear()


UNPICKLED: list[str] = []


def _mark(value: str) -> str:
    UNPICKLED.append(value)
    return value


class _Booby:
    def __reduce__(self):
        return (_mark, ("unpickled",))


@pytest.fixture
def booby_trapped(tmp_path):
    import joblib

    path = tmp_path / "trap.joblib"
    joblib.dump(_Booby(), path)
    UNPICKLED.clear()
    yield path
    UNPICKLED.clear()


def _status_settings(artifact, digest, app_env="production"):
    return SimpleNamespace(
        app_env=app_env,
        ml_model_artifact=str(artifact),
        ml_model_artifact_sha256=digest,
        ml_shadow_monitor_threshold=0.35,
        ml_shadow_redirect_threshold=0.65,
    )


def test_ml_status_does_not_unpickle_on_digest_mismatch(booby_trapped, monkeypatch):
    from app.services import ml_status

    monkeypatch.setattr(ml_status, "settings", _status_settings(booby_trapped, WRONG))
    status = ml_status.get_ml_shadow_status()
    assert UNPICKLED == []
    assert status["shadow_ready"] is False


def test_unpinned_artifact_is_not_loaded_outside_development(booby_trapped, monkeypatch):
    from app.services import ml_status

    monkeypatch.setattr(ml_status, "settings", _status_settings(booby_trapped, None))
    status = ml_status.get_ml_shadow_status()
    assert UNPICKLED == []
    assert "MIRAGE_MODEL_ARTIFACT_SHA256 is not set" in status["blockers"]

    monkeypatch.setattr(ml_shadow, "settings", _status_settings(booby_trapped, None))
    ml_shadow._load_classifier.cache_clear()
    try:
        assert ml_shadow._load_classifier() is None
    finally:
        ml_shadow._load_classifier.cache_clear()
    assert UNPICKLED == []


def test_promotion_does_not_load_unpinned_artifact_outside_development(booby_trapped):
    from app.services.ml_promotion import evaluate_ml_promotion

    settings = SimpleNamespace(
        app_env="staging",
        ml_model_artifact=str(booby_trapped),
        ml_model_artifact_sha256=None,
        ml_dataset_manifest=str(booby_trapped.with_name("manifest.json")),
        ml_routing_mode="heuristic",
        ml_live_routing_approved=False,
        ml_promotion_min_total_rows=1,
        ml_promotion_min_rows_per_class=1,
        ml_promotion_min_shadow_events=1,
        ml_promotion_min_labeled_events=1,
    )
    readiness = evaluate_ml_promotion(
        shadow_summary=SimpleNamespace(shadow_events=0, agreement_rate=0.0),
        settings=settings,
    )
    assert UNPICKLED == []
    gate = next(g for g in readiness.gates if g.code == "artifact_review")
    assert gate.passed is False


def test_loads_the_bytes_that_were_hashed(tmp_path, monkeypatch):
    import joblib

    from app.ml import artifact_integrity

    path = tmp_path / "artifact.joblib"
    joblib.dump({"version": "verified"}, path)
    digest = sha256_file(path)
    original_load = joblib.load

    def swap_then_load(source, *args, **kwargs):
        joblib.dump({"version": "swapped"}, path)
        return original_load(source, *args, **kwargs)

    monkeypatch.setattr(joblib, "load", swap_then_load)

    loaded = artifact_integrity.load_verified_artifact(path, digest)

    assert loaded == {"version": "verified"}


def test_shadow_loader_loads_artifact_once(trained, monkeypatch):
    import joblib

    original_load = joblib.load
    calls = []

    def counting_load(*args, **kwargs):
        calls.append(args)
        return original_load(*args, **kwargs)

    monkeypatch.setattr(joblib, "load", counting_load)
    monkeypatch.setattr(
        ml_shadow, "settings", _shadow_settings(trained, sha256_file(trained))
    )
    ml_shadow._load_classifier.cache_clear()
    try:
        assert ml_shadow._load_classifier() is not None
    finally:
        ml_shadow._load_classifier.cache_clear()

    assert len(calls) == 1
