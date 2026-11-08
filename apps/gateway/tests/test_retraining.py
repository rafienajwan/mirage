"""Tests for analyst-label retraining workflow."""

from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from app.ml.artifact_integrity import sha256_file
from app.services import retraining


async def _create_labeled_event(
    client, index: int, label: str, *, distinct: bool = True
) -> None:
    suspicious = label == "suspicious"
    # Vary the request count so each event has its own feature vector.
    extra = index if distinct else 0
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": f"10.0.0.{index}",
            "method": "POST" if suspicious else "GET",
            "path": f"/.env/{index}" if suspicious else f"/api/v1/products/{index}",
            "user_agent": "sqlmap/1.8" if suspicious else "Mozilla/5.0",
            "request_count": (90 if suspicious else 2) + extra,
            "payload_indicators": (
                ["sql-like", "path-traversal"] if suspicious else []
            ),
        },
    )
    assert response.status_code == 200

    event = (await client.get("/api/v1/dashboard/events?limit=1")).json()["events"][0]
    label_response = await client.patch(
        f"/api/v1/dashboard/events/{event['event_id']}/label",
        json={"label": label},
    )
    assert label_response.status_code == 200


@pytest.mark.asyncio
async def test_retraining_rejects_unready_training_data(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        retraining,
        "settings",
        SimpleNamespace(retraining_artifact_dir=str(tmp_path), ml_model_artifact=None),
    )

    response = await client.post("/api/v1/dashboard/training-data/retrain")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "Training data is not ready"
    assert detail["training_summary"]["ready_for_training"] is False


@pytest.mark.asyncio
async def test_retraining_trains_and_reviews_local_artifact(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        retraining,
        "settings",
        SimpleNamespace(retraining_artifact_dir=str(tmp_path), ml_model_artifact=None),
    )
    _seven_artifacts(tmp_path)
    for index in range(10):
        await _create_labeled_event(client, index, "normal")
        await _create_labeled_event(client, index + 10, "suspicious")

    response = await client.post("/api/v1/dashboard/training-data/retrain")

    assert response.status_code == 200
    data = response.json()
    artifact = Path(data["artifact_path"])

    assert artifact.exists()
    assert len(list(tmp_path.glob("risk_model_*.joblib"))) == 5
    assert artifact.parent == tmp_path
    assert data["training_summary"]["ready_for_training"] is True
    assert data["metrics"]["training_rows"] == 14
    assert data["metrics"]["test_rows"] == 6
    assert data["review"]["artifact_version"] == 1
    assert data["artifact_sha256"] == sha256_file(artifact)
    assert "live routing heuristic" in data["next_steps"][2]


@pytest.mark.asyncio
async def test_retraining_rejects_identical_rows_clearly(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        retraining,
        "settings",
        SimpleNamespace(retraining_artifact_dir=str(tmp_path), ml_model_artifact=None),
    )
    for index in range(10):
        await _create_labeled_event(client, index, "normal", distinct=False)
        await _create_labeled_event(client, index + 10, "suspicious")

    response = await client.post("/api/v1/dashboard/training-data/retrain")

    assert response.status_code == 409
    assert "distinct feature groups" in response.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_retraining_trains_off_the_event_loop(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        retraining,
        "settings",
        SimpleNamespace(retraining_artifact_dir=str(tmp_path), ml_model_artifact=None),
    )
    loop_thread = threading.get_ident()
    train_threads: list[int] = []
    real_train = retraining.train_risk_classifier

    def recording_train(*args, **kwargs):
        train_threads.append(threading.get_ident())
        return real_train(*args, **kwargs)

    monkeypatch.setattr(retraining, "train_risk_classifier", recording_train)
    for index in range(10):
        await _create_labeled_event(client, index, "normal")
        await _create_labeled_event(client, index + 10, "suspicious")

    response = await client.post("/api/v1/dashboard/training-data/retrain")

    assert response.status_code == 200
    assert train_threads and train_threads[0] != loop_thread


def test_retraining_artifact_paths_do_not_collide_within_a_second(tmp_path, monkeypatch):
    monkeypatch.setattr(
        retraining,
        "settings",
        SimpleNamespace(retraining_artifact_dir=str(tmp_path), ml_model_artifact=None),
    )

    assert retraining._artifact_path() != retraining._artifact_path()


def _seven_artifacts(directory: Path) -> list[Path]:
    import os

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(7):
        path = directory / f"risk_model_2026110{index}T000000Z_{index:08x}.joblib"
        path.write_bytes(b"artifact")
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
        paths.append(path)
    return paths  # oldest first


def test_prune_keeps_the_five_newest_artifacts(tmp_path):
    paths = _seven_artifacts(tmp_path)
    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("keep", encoding="utf-8")
    other_model = tmp_path / "custom.joblib"
    other_model.write_bytes(b"keep")

    deleted = retraining.prune_retraining_artifacts(tmp_path, protected=None)

    assert sorted(deleted) == sorted(paths[:2])
    assert all(path.exists() for path in paths[2:])
    assert unrelated.exists()
    assert other_model.exists()


def test_prune_never_deletes_the_configured_artifact(tmp_path, monkeypatch):
    directory = tmp_path / "artifacts"
    paths = _seven_artifacts(directory)
    monkeypatch.chdir(tmp_path)

    deleted = retraining.prune_retraining_artifacts(
        directory, protected=Path("artifacts") / paths[0].name
    )

    assert deleted == [paths[1]]
    assert paths[0].exists()
    assert len(list(directory.glob("risk_model_*.joblib"))) == 6


def test_prune_logs_deletion_errors(tmp_path, monkeypatch, caplog):
    paths = _seven_artifacts(tmp_path)
    real_unlink = Path.unlink

    def failing_unlink(self, *args, **kwargs):
        if self == paths[0]:
            raise PermissionError("locked")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    deleted = retraining.prune_retraining_artifacts(tmp_path, protected=None)

    assert deleted == [paths[1]]
    assert paths[0].exists()
    assert "locked" in caplog.text
