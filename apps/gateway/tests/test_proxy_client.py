"""Shared upstream client and upstream response size cap."""

import dataclasses

from fastapi import HTTPException
import httpx
import pytest
from starlette.requests import Request

from app.core import config
from app.services import proxy_client


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/proxy/api/items",
            "query_string": b"",
            "headers": [(b"host", b"gateway.local")],
        }
    )


async def _forward() -> object:
    return await proxy_client.forward_request(
        _request(),
        upstream_url="http://real-app:8001",
        target_path="api/items",
        body=b"",
        is_decoy=False,
    )


@pytest.fixture
def cap(monkeypatch):
    def _cap(limit: int) -> None:
        monkeypatch.setattr(
            config,
            "settings",
            dataclasses.replace(config.settings, proxy_max_response_bytes=limit),
        )

    return _cap


@pytest.fixture
def upstream(monkeypatch):
    """Install a shared client backed by a mock transport."""

    def _install(handler) -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(proxy_client, "_client", client)
        return client

    yield _install


async def _chunks(*parts: bytes, error: Exception | None = None):
    for part in parts:
        yield part
    if error is not None:
        raise error


async def test_shared_client_is_reused(upstream):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, content=b"ok")

    client = upstream(handler)
    await _forward()
    await _forward()
    assert calls == ["/api/items", "/api/items"]
    assert proxy_client._client is client
    assert not client.is_closed


async def test_content_length_over_cap_returns_502(upstream, cap):
    cap(10)
    upstream(lambda request: httpx.Response(200, content=b"x" * 11))
    with pytest.raises(HTTPException) as exc:
        await _forward()
    assert exc.value.status_code == 502
    assert exc.value.detail == "Upstream response too large"


async def test_streamed_body_over_cap_returns_502(upstream, cap):
    cap(10)
    upstream(lambda request: httpx.Response(200, content=_chunks(b"x" * 6, b"x" * 5)))
    with pytest.raises(HTTPException) as exc:
        await _forward()
    assert exc.value.status_code == 502
    assert exc.value.detail == "Upstream response too large"


async def test_body_under_cap_is_identical(upstream, cap):
    cap(10)
    upstream(
        lambda request: httpx.Response(
            201, content=b"0123456789", headers={"x-app": "demo", "server": "hidden"}
        )
    )
    response = await _forward()
    assert response.status_code == 201
    assert response.body == b"0123456789"
    assert response.headers["x-app"] == "demo"
    assert "server" not in response.headers


async def test_midstream_error_returns_502(upstream):
    upstream(
        lambda request: httpx.Response(
            200, content=_chunks(b"partial", error=httpx.ReadError("reset"))
        )
    )
    with pytest.raises(HTTPException) as exc:
        await _forward()
    assert exc.value.status_code == 502
    assert exc.value.detail == "Upstream service unavailable"


async def test_lifespan_opens_and_closes_shared_client(monkeypatch):
    monkeypatch.setattr(proxy_client, "_client", None)
    await proxy_client.open_upstream_client()
    client = proxy_client._client
    assert isinstance(client, httpx.AsyncClient)
    await proxy_client.close_upstream_client()
    assert client.is_closed
    assert proxy_client._client is None


async def test_without_lifespan_uses_temporary_client(monkeypatch):
    monkeypatch.setattr(proxy_client, "_client", None)
    original = httpx.AsyncClient

    def factory(**kwargs):
        return original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"ok")),
            **kwargs,
        )

    monkeypatch.setattr(proxy_client.httpx, "AsyncClient", factory)
    response = await _forward()
    assert response.body == b"ok"
