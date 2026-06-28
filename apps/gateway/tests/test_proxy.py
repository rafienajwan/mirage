"""Integration tests for real-app and decoy proxy routing decisions."""

import httpx
import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.routes import proxy as proxy_route
from app.core.config import settings
from app.services.traffic_tracker import TrafficTracker, traffic_tracker
from app.services import honeytoken, proxy_client
from app.services.proxy_client import _request_headers, forward_request


@pytest.fixture(autouse=True)
async def clear_proxy_traffic():
    await traffic_tracker.clear()
    yield
    await traffic_tracker.clear()


@pytest.mark.asyncio
async def test_normal_request_is_forwarded_to_real_app(client, monkeypatch):
    captured = {}

    async def fake_forward(request, **kwargs):
        captured.update(kwargs)
        return JSONResponse({"route": "real"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.get(
        "/api/v1/proxy/api/products",
        headers={"user-agent": "Mozilla/5.0"},
    )

    assert response.status_code == 200
    assert response.json() == {"route": "real"}
    assert captured["upstream_url"] == settings.real_app_url
    assert captured["is_decoy"] is False


@pytest.mark.asyncio
async def test_suspicious_request_is_forwarded_to_decoy(client, monkeypatch):
    captured = {}

    async def fake_forward(request, **kwargs):
        captured.update(kwargs)
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.get(
        "/api/v1/proxy/.env",
        headers={"user-agent": "sqlmap/1.8"},
    )

    assert response.status_code == 200
    assert captured["upstream_url"] == settings.decoy_service_url
    assert captured["is_decoy"] is True
    assert captured["decoy_context"]["x-mirage-actor-hint"]
    assert captured["decoy_context"]["x-mirage-risk-score"]
    assert captured["decoy_context"]["x-mirage-decoy-type"] == "config"


@pytest.mark.asyncio
async def test_payload_signals_can_trigger_decoy_routing(client, monkeypatch):
    captured = {}

    async def fake_forward(request, **kwargs):
        captured.update(kwargs)
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.post(
        "/api/v1/proxy/api/admin/import",
        content="../../records UNION SELECT password FROM users",
        headers={"content-type": "text/plain", "authorization": "Bearer real-secret"},
    )

    assert response.status_code == 200
    assert captured["is_decoy"] is True
    assert captured["body"] == b"../../records UNION SELECT password FROM users"


@pytest.mark.asyncio
async def test_proxy_body_is_available_for_honeytoken_detection(client, monkeypatch):
    captured = {}

    async def fake_forward(request, **kwargs):
        captured.update(kwargs)
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    monkeypatch.setattr(
        honeytoken,
        "settings",
        type(
            "TestSettings",
            (),
            {
                "decoy_login_token": "mirage-login-canary",
                "decoy_oauth_token": "mirage-oauth-canary",
                "decoy_service_token": "mirage-service-canary",
                "decoy_database_url": "postgresql://decoy.invalid/mirage",
            },
        )(),
    )

    response = await client.post(
        "/api/v1/proxy/api/token/verify",
        content="token=mirage-service-canary",
        headers={"content-type": "text/plain"},
    )
    honeytokens = await client.get("/api/v1/dashboard/honeytokens")

    assert response.status_code == 200
    assert captured["body"] == b"token=mirage-service-canary"
    assert honeytokens.json()["total_hits"] == 1
    assert honeytokens.json()["hits"][0]["token_kind"] == "service_token"


@pytest.mark.asyncio
async def test_proxy_rejects_oversized_body_before_forwarding(client, monkeypatch):
    called = False

    async def fake_forward(request, **kwargs):
        nonlocal called
        called = True
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.post(
        "/api/v1/proxy/api/upload",
        content=b"x" * (settings.proxy_max_body_bytes + 1),
    )

    assert response.status_code == 413
    assert called is False


def test_decoy_forwarding_strips_credentials():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"authorization", b"Bearer real-secret"),
                (b"cookie", b"session=real-secret"),
                (b"x-mirage-api-key", b"operator-secret"),
                (b"x-mirage-actor-hint", b"spoofed"),
                (b"user-agent", b"Mozilla/5.0"),
                (b"accept", b"application/json"),
            ],
        }
    )

    decoy_headers = _request_headers(
        request,
        is_decoy=True,
        decoy_context={"x-mirage-actor-hint": "trusted-actor"},
    )
    real_headers = _request_headers(request, is_decoy=False)

    assert "authorization" not in decoy_headers
    assert "cookie" not in decoy_headers
    assert "x-mirage-api-key" not in decoy_headers
    assert decoy_headers["x-mirage-actor-hint"] == "trusted-actor"
    assert decoy_headers["user-agent"] == "Mozilla/5.0"
    assert real_headers["authorization"] == "Bearer real-secret"
    assert "x-mirage-actor-hint" not in real_headers


@pytest.mark.asyncio
async def test_forward_request_preserves_http_semantics(monkeypatch):
    captured = {}

    async def upstream_handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = await request.aread()
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            201,
            json={"upstream": "real"},
            headers={"x-powered-by": "hidden", "x-app": "demo"},
        )

    transport = httpx.MockTransport(upstream_handler)
    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr(proxy_client.httpx, "AsyncClient", client_factory)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/proxy/api/orders",
            "query_string": b"page=2",
            "headers": [
                (b"authorization", b"Bearer real-secret"),
                (b"content-type", b"application/json"),
                (b"host", b"gateway.local"),
            ],
        }
    )

    response = await forward_request(
        request,
        upstream_url="http://real-app:8001",
        target_path="api/orders",
        body=b'{"item_id":7}',
        is_decoy=False,
    )

    assert response.status_code == 201
    assert response.body == b'{"upstream":"real"}'
    assert response.headers["x-app"] == "demo"
    assert "x-powered-by" not in response.headers
    assert captured == {
        "method": "POST",
        "url": "http://real-app:8001/api/orders?page=2",
        "body": b'{"item_id":7}',
        "authorization": "Bearer real-secret",
    }


@pytest.mark.asyncio
async def test_traffic_tracker_bounds_distinct_sources():
    tracker = TrafficTracker(max_sources=2)

    await tracker.record("192.0.2.1")
    await tracker.record("192.0.2.2")
    await tracker.record("192.0.2.3")

    assert len(tracker.requests) == 2
    assert "192.0.2.1" not in tracker.requests
