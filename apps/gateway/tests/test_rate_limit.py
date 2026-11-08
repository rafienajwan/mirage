"""Rate limiter behavior and memory bounds."""

import dataclasses

from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core import config
from app.core.rate_limit import RateLimitMiddleware


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _build(limit: int, max_clients: int = 10000):
    clock = FakeClock()

    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/api/v1/x", ok)])
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=limit,
        max_clients=max_clients,
        clock=clock,
    )
    return app, clock


async def _hit(app, ip: str, headers: dict | None = None) -> int:
    transport = ASGITransport(app=app, client=(ip, 1))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/x", headers=headers or {})
        return response.status_code


def _limiter(app) -> RateLimitMiddleware:
    # Build the middleware stack once and return the limiter instance.
    if app.middleware_stack is None:
        app.middleware_stack = app.build_middleware_stack()
    layer = app.middleware_stack
    while not isinstance(layer, RateLimitMiddleware):
        layer = layer.app
    return layer


async def test_blocks_after_limit():
    app, _ = _build(limit=2)
    assert await _hit(app, "1.1.1.1") == 200
    assert await _hit(app, "1.1.1.1") == 200
    transport = ASGITransport(app=app, client=("1.1.1.1", 1))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/x")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


async def test_clients_are_independent():
    app, _ = _build(limit=1)
    assert await _hit(app, "1.1.1.1") == 200
    assert await _hit(app, "1.1.1.1") == 429
    assert await _hit(app, "2.2.2.2") == 200


async def test_expired_bucket_is_deleted():
    app, clock = _build(limit=5)
    await _hit(app, "1.1.1.1")
    clock.now += 61
    await _hit(app, "2.2.2.2")
    assert "1.1.1.1" not in _limiter(app).requests


async def test_cap_evicts_least_recently_used():
    app, _ = _build(limit=10, max_clients=2)
    for ip in ("1.1.1.1", "2.2.2.2", "1.1.1.1", "3.3.3.3"):
        await _hit(app, ip)
    assert set(_limiter(app).requests) == {"1.1.1.1", "3.3.3.3"}


async def test_cap_prefers_expired_buckets():
    app, clock = _build(limit=10, max_clients=2)
    await _hit(app, "1.1.1.1")
    clock.now += 61
    await _hit(app, "2.2.2.2")
    await _hit(app, "3.3.3.3")
    assert set(_limiter(app).requests) == {"2.2.2.2", "3.3.3.3"}


async def test_no_eviction_below_cap():
    app, _ = _build(limit=1, max_clients=3)
    assert await _hit(app, "1.1.1.1") == 200
    await _hit(app, "2.2.2.2")
    await _hit(app, "3.3.3.3")
    assert await _hit(app, "1.1.1.1") == 429


async def test_keys_on_client_ip(monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, trusted_proxies="10.0.0.0/8"),
    )
    app, _ = _build(limit=1)
    assert await _hit(app, "10.0.0.2", {"x-forwarded-for": "203.0.113.1"}) == 200
    assert await _hit(app, "10.0.0.2", {"x-forwarded-for": "203.0.113.2"}) == 200
    assert await _hit(app, "10.0.0.2", {"x-forwarded-for": "203.0.113.1"}) == 429


async def test_valid_operator_api_key_is_not_limited(monkeypatch):
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, api_key="operator-key")
    )
    app, _ = _build(limit=1)
    operator = {"x-mirage-api-key": "operator-key"}
    # The dashboard server calls the gateway for every operator from one IP.
    assert [await _hit(app, "10.0.0.9", operator) for _ in range(3)] == [200, 200, 200]
    assert await _hit(app, "10.0.0.9", {"x-mirage-api-key": "wrong"}) == 200
    assert await _hit(app, "10.0.0.9", {"x-mirage-api-key": "wrong"}) == 429


async def test_api_key_header_is_limited_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, api_key=None))
    app, _ = _build(limit=1)
    assert await _hit(app, "10.0.0.9", {"x-mirage-api-key": ""}) == 200
    assert await _hit(app, "10.0.0.9", {"x-mirage-api-key": ""}) == 429
