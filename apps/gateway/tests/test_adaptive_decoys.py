"""Tests for adaptive decoy responses and issued honeytokens."""

from types import SimpleNamespace

import pytest

from app.schemas.request import InspectRequest
from app.services import decoy_engine, honeytoken


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        decoy_login_token="mirage-login-canary",
        decoy_oauth_token="mirage-oauth-canary",
        decoy_service_token="mirage-service-canary",
        decoy_canary_epoch="v1",
        decoy_database_url="postgresql://decoy.invalid/mirage",
    )


def test_decoy_response_assigns_stable_actor_token(monkeypatch):
    monkeypatch.setattr(decoy_engine, "settings", _settings())

    first = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-alpha",
        risk_score=90,
    )
    repeat = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-alpha",
        risk_score=90,
    )
    other = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-beta",
        risk_score=90,
    )

    assert first.variant == "high_interaction"
    assert first.body["token"].startswith("mirage-issued-login-canary-")
    assert first.body["token"] == repeat.body["token"]
    assert first.body["token"] != other.body["token"]
    assert first.body["mirage_assignment"]["mode"] == "per_actor"
    assert first.body["mirage_assignment"]["rotation_epoch"] == "v1"


def test_decoy_response_rotates_actor_token_by_epoch(monkeypatch):
    settings_v1 = _settings()
    settings_v2 = _settings()
    settings_v2.decoy_canary_epoch = "v2"

    monkeypatch.setattr(decoy_engine, "settings", settings_v1)
    first = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-alpha",
    )

    monkeypatch.setattr(decoy_engine, "settings", settings_v2)
    rotated = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-alpha",
    )

    assert first.body["token"] != rotated.body["token"]
    assert rotated.body["mirage_assignment"]["rotation_epoch"] == "v2"


def test_issued_actor_token_is_detected_as_honeytoken(monkeypatch):
    monkeypatch.setattr(decoy_engine, "settings", _settings())
    monkeypatch.setattr(honeytoken, "settings", _settings())

    decoy = decoy_engine.generate_decoy_response(
        "/api/auth/login",
        actor_hint="actor-alpha",
    )
    request = InspectRequest(
        ip_address="10.0.0.9",
        method="POST",
        path="/api/token/verify",
        user_agent="curl/8",
        payload_excerpt=f"token={decoy.body['token']}",
    )

    matches = honeytoken.detect_honeytokens(request)

    assert len(matches) == 1
    assert matches[0].token_kind == "login_token"
    assert matches[0].token_label == "Issued decoy login token"


@pytest.mark.asyncio
async def test_decoy_endpoint_returns_adaptive_metadata(client):
    response = await client.post(
        "/api/v1/decoy/respond",
        json={
            "path": "/api/config/settings",
            "decoy_type": "auto",
            "actor_hint": "actor-config",
            "risk_score": 70,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decoy_type"] == "config"
    assert data["variant"] == "credential_bait"
    assert data["body"]["secret_key"].startswith("mirage-issued-service-canary-")
    assert data["body"]["mirage_decoy"]["safe"] is True
