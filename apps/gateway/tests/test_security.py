"""API key enforcement: fail closed outside development."""

import dataclasses

import pytest

from app.core import config

BODY = {"ip_address": "198.51.100.1", "method": "GET", "path": "/api/items"}


@pytest.fixture
def env(monkeypatch):
    def _env(app_env: str, api_key: str | None) -> None:
        monkeypatch.setattr(
            config,
            "settings",
            dataclasses.replace(config.settings, app_env=app_env, api_key=api_key),
        )

    return _env


async def test_production_without_key_fails_closed(client, env):
    env("production", None)
    response = await client.post("/api/v1/inspect", json=BODY)
    assert response.status_code == 503
    assert response.json()["detail"] == "API key not configured"


async def test_staging_without_key_fails_closed(client, env):
    env("staging", None)
    response = await client.post("/api/v1/inspect", json=BODY)
    assert response.status_code == 503


async def test_development_without_key_is_open(client, env):
    env("development", None)
    response = await client.post("/api/v1/inspect", json=BODY)
    assert response.status_code == 200


async def test_wrong_key_looks_like_unknown_route_outside_development(client, env):
    env("production", "k" * 32)
    response = await client.post(
        "/api/v1/inspect", json=BODY, headers={"X-Mirage-API-Key": "wrong"}
    )
    unknown = await client.post("/api/v1/no-such-route", json=BODY)
    assert response.status_code == 404
    assert response.json() == unknown.json() == {"detail": "Not Found"}


async def test_wrong_key_is_401_in_development(client, env):
    env("development", "k" * 32)
    response = await client.post(
        "/api/v1/inspect", json=BODY, headers={"X-Mirage-API-Key": "wrong"}
    )
    assert response.status_code == 401


async def test_right_key_is_accepted(client, env):
    env("production", "k" * 32)
    response = await client.post(
        "/api/v1/inspect", json=BODY, headers={"X-Mirage-API-Key": "k" * 32}
    )
    assert response.status_code == 200
