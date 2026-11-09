"""Per-operator identity, roles and login on the operator API."""

import dataclasses

import pytest

from app.core import config
from app.services import operators as operator_service
from app.storage import store

KEY = "k" * 32
HEADERS = {"X-Mirage-API-Key": KEY}


def _as(name: str) -> dict[str, str]:
    return {**HEADERS, "X-Mirage-Operator": name}


@pytest.fixture
def production(monkeypatch):
    def _set(**overrides) -> None:
        settings = dataclasses.replace(
            config.settings, app_env="production", api_key=KEY, **overrides
        )
        monkeypatch.setattr(config, "settings", settings)

    _set()
    return _set


@pytest.fixture
async def alice(production):
    return await operator_service.create_operator("alice", "long enough pw", "analyst")


async def test_key_without_header_is_api_key_admin(client, production):
    response = await client.get("/api/v1/operators/audit", headers=HEADERS)
    assert response.status_code == 200


async def test_enabled_operator_resolves(client, alice):
    response = await client.get("/api/v1/operators", headers=_as("alice"))
    assert response.status_code == 200
    assert response.json() == {"operators": [{"username": "alice", "role": "analyst"}]}
    assert "hash" not in response.text


async def test_unknown_operator_is_404(client, production):
    response = await client.get("/api/v1/operators", headers=_as("nobody"))
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


async def test_disabled_operator_is_refused(client, alice):
    await store.update_operator("alice", disabled=True)
    response = await client.get("/api/v1/operators", headers=_as("alice"))
    assert response.status_code == 404


async def test_header_without_key_is_refused(client, alice):
    response = await client.get(
        "/api/v1/operators", headers={"X-Mirage-Operator": "alice"}
    )
    assert response.status_code == 404


async def test_development_unknown_operator_is_401(client, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, app_env="development", api_key=None),
    )
    response = await client.get("/api/v1/operators", headers=_as("nobody"))
    assert response.status_code == 401


async def test_development_without_key_resolves_known_operator(client, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, app_env="development", api_key=None),
    )
    await operator_service.create_operator("alice", "long enough pw", "analyst")
    forbidden = await client.get(
        "/api/v1/operators/audit", headers={"X-Mirage-Operator": "alice"}
    )
    assert forbidden.status_code == 403
    assert (await client.get("/api/v1/operators/audit")).status_code == 200


async def test_analyst_forbidden_on_admin_routes(client, alice):
    responses = [
        await client.post(
            "/api/v1/dashboard/training-data/retrain", headers=_as("alice")
        ),
        await client.post(
            "/api/v1/dashboard/canary-assignments/x/revoke",
            json={"reason": "r"},
            headers=_as("alice"),
        ),
        await client.get("/api/v1/operators/audit", headers=_as("alice")),
    ]
    for response in responses:
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin role required"


async def test_login_success_returns_role(client, alice):
    response = await client.post(
        "/api/v1/operators/login",
        json={"username": "alice", "password": "long enough pw"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"username": "alice", "role": "analyst"}
    entries = await store.get_audit()
    assert [(e.action, e.operator, e.target) for e in entries] == [
        ("login", "alice", "alice")
    ]


async def test_login_failures_are_identical(client, alice):
    await operator_service.create_operator("dora", "long enough pw", "analyst")
    await store.update_operator("dora", disabled=True)
    attempts = [
        {"username": "ghost", "password": "long enough pw"},
        {"username": "alice", "password": "wrong password!"},
        {"username": "dora", "password": "long enough pw"},
    ]
    responses = [
        await client.post("/api/v1/operators/login", json=a, headers=HEADERS)
        for a in attempts
    ]
    assert {r.status_code for r in responses} == {401}
    assert all(r.json() == {"detail": "Invalid credentials"} for r in responses)
    entries = await store.get_audit()
    assert [e.action for e in entries] == ["login_failed"] * 3
    assert {e.target for e in entries} == {"ghost", "alice", "dora"}


async def test_login_is_case_insensitive(client, alice):
    response = await client.post(
        "/api/v1/operators/login",
        json={"username": "Alice", "password": "long enough pw"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


async def test_login_requires_api_key(client, alice):
    response = await client.post(
        "/api/v1/operators/login",
        json={"username": "alice", "password": "long enough pw"},
    )
    assert response.status_code == 404


async def test_authenticate_runs_one_verify_per_attempt(alice, monkeypatch):
    await operator_service.create_operator("off", "long enough pw", "analyst")
    await store.update_operator("off", disabled=True)
    calls = []
    real = operator_service.verify_password

    def spy(password, encoded):
        calls.append(encoded)
        return real(password, encoded)

    monkeypatch.setattr(operator_service, "verify_password", spy)
    for name in ("alice", "ghost", "off", "Bad Name!"):
        await operator_service.authenticate(name, "long enough pw")
    assert len(calls) == 4
    assert calls.count(operator_service.DUMMY_HASH) == 3


async def test_operator_header_keeps_rate_limit_exemption(client, alice, production):
    production(rate_limit_per_minute=1)
    for _ in range(3):
        response = await client.get("/api/v1/operators", headers=_as("alice"))
        assert response.status_code == 200
