"""Tests for analyst-label retraining workflow."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import retraining


async def _create_labeled_event(client, index: int, label: str) -> None:
    suspicious = label == "suspicious"
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": f"10.0.0.{index}",
            "method": "POST" if suspicious else "GET",
            "path": f"/.env/{index}" if suspicious else f"/api/v1/products/{index}",
            "user_agent": "sqlmap/1.8" if suspicious else "Mozilla/5.0",
            "request_count": 90 if suspicious else 2,
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
        SimpleNamespace(retraining_artifact_dir=str(tmp_path)),
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
        SimpleNamespace(retraining_artifact_dir=str(tmp_path)),
    )
    for index in range(10):
        await _create_labeled_event(client, index, "normal")
        await _create_labeled_event(client, index + 10, "suspicious")

    response = await client.post("/api/v1/dashboard/training-data/retrain")

    assert response.status_code == 200
    data = response.json()
    artifact = Path(data["artifact_path"])

    assert artifact.exists()
    assert artifact.parent == tmp_path
    assert data["training_summary"]["ready_for_training"] is True
    assert data["metrics"]["training_rows"] == 15
    assert data["metrics"]["test_rows"] == 5
    assert data["review"]["artifact_version"] == 1
    assert "live routing heuristic" in data["next_steps"][2]
