"""Tests for actor profile aggregation."""

from types import SimpleNamespace

import pytest

from app.services import honeytoken


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        decoy_login_token="mirage-login-canary",
        decoy_oauth_token="mirage-oauth-canary",
        decoy_service_token="mirage-service-canary",
        decoy_database_url="postgresql://decoy.invalid/mirage",
    )


@pytest.mark.asyncio
async def test_actor_profiles_group_fingerprints_and_honeytoken_hits(client, monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())
    base_request = {
        "ip_address": "10.10.10.50",
        "method": "POST",
        "path": "/api/token/verify",
        "user_agent": "curl/8",
        "request_count": 6,
        "payload_indicators": ["token-probe"],
    }

    first = await client.post(
        "/api/v1/inspect",
        json={**base_request, "payload_excerpt": "token=mirage-service-canary"},
    )
    second = await client.post(
        "/api/v1/inspect",
        json={**base_request, "payload_excerpt": ""},
    )
    response = await client.get("/api/v1/dashboard/actors")

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200

    data = response.json()
    assert data["total_actors"] == 1

    profile = data["profiles"][0]
    assert profile["actor_id"].startswith("actor-")
    assert profile["fingerprint_hash"] == first.json()["fingerprint_hash"]
    assert profile["fingerprint_hash"] == second.json()["fingerprint_hash"]
    assert profile["source_ip"] == "10.10.***.***"
    assert profile["request_count"] == 2
    assert profile["honeytoken_hits"] == 1
    assert profile["status"] == "confirmed_interaction"
    assert profile["top_paths"] == ["/api/token/verify"]
