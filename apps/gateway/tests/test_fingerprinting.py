"""Outside development, unauthenticated paths reveal nothing about MIRAGE."""

import dataclasses

from httpx import ASGITransport, AsyncClient
import pytest

from app.core import config
from app.main import create_app

KEY = "k" * 32


@pytest.fixture
def production(monkeypatch):
    prod_settings = dataclasses.replace(config.settings, app_env="production", api_key=KEY)
    monkeypatch.setattr(config, "settings", prod_settings)
    return create_app(prod_settings)


async def _get(app, path: str, headers: dict | None = None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/"])
async def test_production_hides_docs_and_root(production, path):
    assert (await _get(production, path)).status_code == 404


async def test_production_decoy_status_requires_key(production):
    denied = await _get(production, "/api/v1/decoy/status")
    assert denied.status_code == 404
    assert denied.json() == {"detail": "Not Found"}
    assert "mirage" not in denied.text.lower()
    response = await _get(production, "/api/v1/decoy/status", {"X-Mirage-API-Key": KEY})
    assert response.status_code == 200


async def test_production_health_is_anonymous(production):
    response = await _get(production, "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    lowered = response.text.lower()
    for word in ("mirage", "deception", "decoy"):
        assert word not in lowered


def test_production_websocket_route_still_registered(production):
    # FastAPI nests included routers, so resolve by name instead of listing.
    assert production.url_path_for("dashboard_websocket") == "/api/v1/dashboard/ws"


async def test_development_keeps_docs():
    dev_app = create_app(dataclasses.replace(config.settings, app_env="development"))
    assert (await _get(dev_app, "/docs")).status_code == 200
