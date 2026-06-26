"""Tests for honeytoken detection and dashboard reporting."""

from types import SimpleNamespace

import pytest

from app.schemas.request import InspectRequest
from app.services import honeytoken


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        decoy_login_token="mirage-login-canary",
        decoy_oauth_token="mirage-oauth-canary",
        decoy_service_token="mirage-service-canary",
        decoy_database_url="postgresql://decoy.invalid/mirage",
    )


def test_detect_honeytokens_from_bounded_payload(monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())
    request = InspectRequest(
        ip_address="10.0.0.5",
        method="POST",
        path="/api/token/verify",
        user_agent="curl/8",
        payload_excerpt="Authorization: Bearer mirage-oauth-canary",
    )

    matches = honeytoken.detect_honeytokens(request)

    assert len(matches) == 1
    assert matches[0].token_kind == "oauth_token"
    assert matches[0].token_label == "Decoy OAuth token"


@pytest.mark.asyncio
async def test_honeytoken_hit_creates_dashboard_activity(client, monkeypatch):
    monkeypatch.setattr(honeytoken, "settings", _settings())

    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "10.0.0.99",
            "method": "POST",
            "path": "/api/internal/token-check",
            "user_agent": "curl/8",
            "request_count": 10,
            "payload_indicators": ["token-probe"],
            "payload_excerpt": "token=mirage-service-canary",
        },
    )
    assert response.status_code == 200

    honeytokens = await client.get("/api/v1/dashboard/honeytokens")
    alerts = await client.get("/api/v1/dashboard/alerts")

    assert honeytokens.status_code == 200
    data = honeytokens.json()
    assert data["total_hits"] == 1
    assert data["hits"][0]["token_kind"] == "service_token"
    assert data["hits"][0]["token_label"] == "Decoy service token"

    alert_titles = [item["title"] for item in alerts.json()["alerts"]]
    assert "Honeytoken touched: Decoy service token" in alert_titles
