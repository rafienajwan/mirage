"""HTTP forwarding helpers with fixed upstream targets and header isolation."""

from __future__ import annotations

from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response

from app.core.config import settings

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
    "x-mirage-decoy-type",
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


def _response_headers(headers: httpx.Headers, upstream_url: str) -> dict[str, str]:
    safe = {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
        and key.lower() not in {"server", "x-powered-by"}
    }
    location = safe.get("location")
    if location and location.startswith(upstream_url.rstrip("/")):
        safe["location"] = "/api/v1/proxy" + location[len(upstream_url.rstrip("/")) :]
    return safe


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
    encoded_path = quote("/" + target_path.lstrip("/"), safe="/:%@")
    url = upstream_url.rstrip("/") + encoded_path
    if request.url.query:
        url += "?" + request.url.query

    try:
        async with httpx.AsyncClient(
            timeout=settings.proxy_timeout_seconds,
            follow_redirects=False,
        ) as client:
            upstream = await client.request(
                request.method,
                url,
                headers=_request_headers(
                    request,
                    is_decoy=is_decoy,
                    decoy_context=decoy_context,
                ),
                content=body,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Upstream service unavailable") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers, upstream_url),
    )
