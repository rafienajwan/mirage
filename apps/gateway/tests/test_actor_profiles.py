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


@pytest.mark.asyncio
async def test_actor_clusters_group_profiles_by_status_and_path(client, monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())
    first = {
        "ip_address": "10.10.20.10",
        "method": "GET",
        "path": "/.env",
        "user_agent": "curl/8",
        "request_count": 120,
        "payload_indicators": ["path-traversal"],
    }
    second = {
        **first,
        "ip_address": "10.10.20.11",
        "user_agent": "python-requests/2",
        "payload_excerpt": "SERVICE_TOKEN=mirage-issued-service-canary-abcdef123456",
    }

    first_response = await client.post("/api/v1/inspect", json=first)
    second_response = await client.post("/api/v1/inspect", json=second)
    response = await client.get("/api/v1/dashboard/actor-clusters")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert response.status_code == 200

    data = response.json()
    assert data["total_clusters"] >= 1

    cluster = data["clusters"][0]
    assert cluster["cluster_id"].startswith("cluster-")
    assert cluster["actor_count"] == 1
    assert cluster["status"] == "confirmed_interaction"
    assert cluster["shared_paths"] == ["/.env"]
    assert cluster["honeytoken_hits"] == 1


@pytest.mark.asyncio
async def test_actor_cases_recommend_investigations_from_clusters(client, monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())
    request = {
        "ip_address": "10.10.30.10",
        "method": "GET",
        "path": "/api/token/verify",
        "user_agent": "curl/8",
        "request_count": 80,
        "payload_indicators": ["encoded"],
        "payload_excerpt": "token=mirage-service-canary",
    }

    event_response = await client.post("/api/v1/inspect", json=request)
    response = await client.get("/api/v1/dashboard/actor-cases")

    assert event_response.status_code == 200
    assert response.status_code == 200

    data = response.json()
    assert data["total_cases"] == 1

    case = data["cases"][0]
    assert case["case_id"].startswith("case-")
    assert case["cluster_id"].startswith("cluster-")
    assert case["severity"] == "critical"
    assert case["status"] == "recommended"
    assert case["actor_count"] == 1
    assert case["recommended_action"].startswith("Investigate issued canary reuse")


@pytest.mark.asyncio
async def test_actor_case_workflows_open_and_update_recommended_case(client, monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())
    request = {
        "ip_address": "10.10.40.10",
        "method": "GET",
        "path": "/.env",
        "user_agent": "curl/8",
        "request_count": 90,
        "payload_indicators": ["path-traversal"],
        "payload_excerpt": "SERVICE_TOKEN=mirage-service-canary",
    }

    event_response = await client.post("/api/v1/inspect", json=request)
    recommendations = await client.get("/api/v1/dashboard/actor-cases")
    case_id = recommendations.json()["cases"][0]["case_id"]

    open_response = await client.post(
        f"/api/v1/dashboard/actor-cases/{case_id}/open",
        json={"note": "Opened from triage", "assigned_to": "rafie"},
    )
    workflows = await client.get(
        "/api/v1/dashboard/actor-case-workflows?assigned_to=rafie"
    )
    update_response = await client.patch(
        f"/api/v1/dashboard/actor-case-workflows/{case_id}",
        json={
            "status": "investigating",
            "note": "Analyst assigned",
            "assigned_to": "rafie",
        },
    )

    assert event_response.status_code == 200
    assert open_response.status_code == 200
    assert workflows.status_code == 200
    assert update_response.status_code == 200

    opened = open_response.json()
    assert opened["case_id"] == case_id
    assert opened["status"] == "open"
    assert opened["assigned_to"] == "rafie"
    assert opened["analyst_note"] == "Opened from triage"

    workflow_data = workflows.json()
    assert workflow_data["total_cases"] == 1
    assert workflow_data["cases"][0]["case_id"] == case_id

    updated = update_response.json()
    assert updated["status"] == "investigating"
    assert updated["assigned_to"] == "rafie"
    assert updated["analyst_note"] == "Analyst assigned"
