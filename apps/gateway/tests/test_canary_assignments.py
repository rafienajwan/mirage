"""Tests for persistent canary assignment lifecycle."""

import pytest

from app.api.routes import dashboard as dashboard_routes


@pytest.mark.asyncio
async def test_decoy_response_records_and_revokes_canary_assignment(client, monkeypatch):
    refreshes = 0

    def schedule_refresh() -> None:
        nonlocal refreshes
        refreshes += 1

    monkeypatch.setattr(
        dashboard_routes,
        "schedule_dashboard_snapshot_refresh",
        schedule_refresh,
        raising=False,
    )
    response = await client.post(
        "/api/v1/decoy/respond",
        json={
            "path": "/api/config/settings",
            "decoy_type": "auto",
            "actor_hint": "actor-config",
            "risk_score": 80,
        },
    )

    assert response.status_code == 200
    token = response.json()["body"]["secret_key"]
    assert token.startswith("mirage-issued-service-canary-")

    listed = await client.get("/api/v1/dashboard/canary-assignments")
    assert listed.status_code == 200
    data = listed.json()
    assert data["total_assignments"] == 1
    assignment = data["assignments"][0]
    assert assignment["actor_id"].startswith("actor-")
    assert assignment["token_kind"] == "service_token"
    assert assignment["status"] == "active"
    assert assignment["rotation_epoch"] == "v1"
    assert assignment["decoy_type"] == "config"
    assert assignment["source_path"] == "/api/config/settings"
    assert assignment["token_hash"]
    assert token not in assignment["token_hash"]
    assert assignment["revoked_at"] is None

    revoked = await client.post(
        f"/api/v1/dashboard/canary-assignments/{assignment['assignment_id']}/revoke",
        json={"reason": "operator rotation"},
    )

    assert revoked.status_code == 200
    revoked_assignment = revoked.json()
    assert revoked_assignment["assignment_id"] == assignment["assignment_id"]
    assert revoked_assignment["status"] == "revoked"
    assert revoked_assignment["revoke_reason"] == "operator rotation"
    assert revoked_assignment["revoked_at"] is not None
    assert refreshes == 1

    filtered = await client.get(
        "/api/v1/dashboard/canary-assignments?status=revoked"
    )
    assert filtered.status_code == 200
    assert filtered.json()["total_assignments"] == 1


@pytest.mark.asyncio
async def test_missing_canary_assignment_revoke_returns_404(client, monkeypatch):
    refreshes = 0

    def schedule_refresh() -> None:
        nonlocal refreshes
        refreshes += 1

    monkeypatch.setattr(
        dashboard_routes,
        "schedule_dashboard_snapshot_refresh",
        schedule_refresh,
        raising=False,
    )
    response = await client.post(
        "/api/v1/dashboard/canary-assignments/canary-missing/revoke",
        json={"reason": "not found"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Canary assignment not found"
    assert refreshes == 0
