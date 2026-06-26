"""Defensive reverse proxy that routes requests to real or decoy services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.core.config import settings
from app.schemas.decision import Decision
from app.schemas.request import InspectRequest
from app.services.inspection import inspect_and_log
from app.services.payload_signals import detect_payload_indicators
from app.services.proxy_client import forward_request
from app.services.traffic_tracker import traffic_tracker

router = APIRouter(prefix="/proxy", tags=["proxy"])

_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.proxy_max_body_bytes:
                raise HTTPException(status_code=413, detail="Request body too large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > settings.proxy_max_body_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
    return bytes(body)


@router.api_route("/{target_path:path}", methods=_PROXY_METHODS)
async def proxy_request(target_path: str, request: Request) -> Response:
    """Inspect an incoming request and transparently choose its upstream."""
    body = await _read_limited_body(request)

    path = "/" + target_path.lstrip("/")
    source_ip = request.client.host if request.client else "unknown"
    request_count = await traffic_tracker.record(source_ip)
    indicators = detect_payload_indicators(path, request.url.query, body)
    payload_excerpt = " ".join(
        [
            request.url.query,
            body[: settings.proxy_max_body_bytes].decode("utf-8", errors="ignore")[:4096],
        ]
    )
    metadata = InspectRequest(
        ip_address=source_ip,
        method=request.method,
        path=path,
        user_agent=request.headers.get("user-agent", ""),
        request_count=request_count,
        payload_indicators=indicators,
        payload_excerpt=payload_excerpt,
    )
    inspection = await inspect_and_log(metadata, event_type="proxy")
    is_decoy = inspection.decision == Decision.REDIRECT_TO_DECOY
    upstream_url = settings.decoy_service_url if is_decoy else settings.real_app_url

    return await forward_request(
        request,
        upstream_url=upstream_url,
        target_path=target_path,
        body=body,
        is_decoy=is_decoy,
    )
