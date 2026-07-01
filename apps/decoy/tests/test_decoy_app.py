"""Tests for the external decoy service."""

from fastapi.testclient import TestClient

from apps.decoy.app.main import app


def test_decoy_service_issues_actor_token_from_gateway_context():
    client = TestClient(app)

    first = client.get(
        "/api/auth/login",
        headers={
            "x-mirage-actor-hint": "actor-alpha",
            "x-mirage-risk-score": "91.0",
        },
    )
    repeat = client.get(
        "/api/auth/login",
        headers={
            "x-mirage-actor-hint": "actor-alpha",
            "x-mirage-risk-score": "91.0",
        },
    )
    other = client.get(
        "/api/auth/login",
        headers={
            "x-mirage-actor-hint": "actor-beta",
            "x-mirage-risk-score": "91.0",
        },
    )

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["access_token"].startswith("mirage-issued-login-canary-")
    assert first_body["access_token"] == repeat.json()["access_token"]
    assert first_body["access_token"] != other.json()["access_token"]
    assert first_body["mirage_decoy"]["variant"] == "high_interaction"
    assert first_body["mirage_assignment"]["mode"] == "per_actor"
    assert first_body["mirage_assignment"]["rotation_epoch"] == "v1"


def test_decoy_env_response_uses_actor_service_canary():
    client = TestClient(app)

    response = client.get(
        "/.env",
        headers={
            "x-mirage-actor-hint": "actor-config",
            "x-mirage-risk-score": "72.0",
        },
    )

    assert response.status_code == 200
    assert "SERVICE_TOKEN=mirage-issued-service-canary-" in response.text
    assert "MIRAGE_DECOY_VARIANT=credential_bait" in response.text
