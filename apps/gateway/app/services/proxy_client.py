"""HTTP forwarding helpers with fixed upstream targets and header isolation."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import Response
import httpx

from app.core import config

_TOO_LARGE = "Upstream response too large"

# One pooled client for the process, opened and closed by the app lifespan.
_client: httpx.AsyncClient | None = None


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=config.settings.proxy_timeout_seconds,
        follow_redirects=False,
    )


async def open_upstream_client() -> None:
    global _client
    if _client is None:
        _client = _build_client()


async def close_upstream_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
_DECOY_SAFE_HEADERS = {"accept", "accept-language", "content-type", "user-agent"}
_MIRAGE_INTERNAL_HEADERS = {
    "x-mirage-api-key",
    "x-mirage-actor-hint",
    "x-mirage-risk-score",
}


def _request_headers(
    request: Request,
    *,
    is_decoy: bool,
    decoy_context: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }
    for name in _MIRAGE_INTERNAL_HEADERS:
        headers.pop(name, None)
    if is_decoy:
        headers = {
            key: value
            for key, value in headers.items()
            if key.lower() in _DECOY_SAFE_HEADERS
        }
        for key, value in (decoy_context or {}).items():
            if value:
                headers[key] = value
    return headers


def _response_headers(headers: httpx.Headers, upstream_url: str) -> list[tuple[str, str]]:
    """Filter upstream headers, keeping repeated ones (Set-Cookie) separate."""
    upstream = upstream_url.rstrip("/")
    safe = []
    for key, value in headers.multi_items():
        name = key.lower()
        # The body is read decoded (aiter_bytes), so its encoding no longer applies.
        if name in _HOP_BY_HOP_HEADERS or name in {"server", "x-powered-by", "content-encoding"}:
            continue
        if name == "location" and value.startswith(upstream):
            value = "/api/v1/proxy" + value[len(upstream) :]
        safe.append((key, value))
    return safe


_PROXY_PREFIX = b"/api/v1/proxy/"


def _upstream_path(request: Request, target_path: str) -> str:
    """Return the path as the client encoded it (%2F and %25 kept intact).

    The decoded ``target_path`` is only a fallback for scopes without a usable
    ``raw_path``; re-quoting it would turn %2541 into %41 and %2F into "/".
    """
    raw_path = request.scope.get("raw_path") or b""
    if raw_path.startswith(_PROXY_PREFIX) and raw_path.isascii():
        return raw_path[len(_PROXY_PREFIX) - 1 :].decode("ascii")
    return quote("/" + target_path.lstrip("/"), safe="/:%@")


async def forward_request(
    request: Request,
    *,
    upstream_url: str,
    target_path: str,
    body: bytes,
    is_decoy: bool,
    decoy_context: dict[str, str] | None = None,
) -> Response:
    """Forward a request to one configured upstream and return its response."""
    url = upstream_url.rstrip("/") + _upstream_path(request, target_path)
    if request.url.query:
        url += "?" + request.url.query

    headers = _request_headers(request, is_decoy=is_decoy, decoy_context=decoy_context)
    try:
        if _client is not None:
            return await _send(_client, request.method, url, headers, body, upstream_url)
        async with _build_client() as client:
            return await _send(client, request.method, url, headers, body, upstream_url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Upstream service unavailable") from exc


async def _send(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    upstream_url: str,
) -> Response:
    """Stream the upstream response, refusing bodies above the configured cap."""
    limit = config.settings.proxy_max_response_bytes
    upstream = await client.send(
        client.build_request(method, url, headers=headers, content=body),
        stream=True,
    )
    try:
        declared = upstream.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise HTTPException(status_code=502, detail=_TOO_LARGE)
        content = bytearray()
        async for chunk in upstream.aiter_bytes():
            content += chunk
            if len(content) > limit:
                raise HTTPException(status_code=502, detail=_TOO_LARGE)
    finally:
        await upstream.aclose()

    response = Response(content=bytes(content), status_code=upstream.status_code)
    for key, value in _response_headers(upstream.headers, upstream_url):
        response.headers.append(key, value)
    return response
