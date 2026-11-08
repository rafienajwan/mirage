"""Defensive reverse proxy that routes requests to real or decoy services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.client_ip import client_ip
from app.core.config import settings
from app.schemas.decision import Decision
from app.schemas.request import InspectRequest
from app.services.canary_assignments import record_canary_assignments
from app.services.inspection import inspect_and_log
from app.services.payload_exemptions import apply_exemptions
from app.services.payload_signals import (
    build_payload_excerpt,
    detect_payload_indicators,
)
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
    source_ip = client_ip(request)
    request_count = await traffic_tracker.record(source_ip)
    # Inspecting a large body is CPU-bound (~0.4 s per MiB); keep it off the
    # event loop so other requests are not stalled behind it.
    indicators = await run_in_threadpool(
        detect_payload_indicators,
        path,
        request.url.query,
        body,
        content_type=request.headers.get("content-type"),
        headers=(request.headers.get("user-agent", ""), request.headers.get("referer", "")),
    )
    indicators, exempted = apply_exemptions(request.method, path, indicators)
    payload_excerpt = build_payload_excerpt(
        request.url.query,
        body[: settings.proxy_max_body_bytes].decode("utf-8", errors="ignore"),
    )
    # Logged values are truncated to the stored column sizes; detection above
    # and the forwarded request use the complete path.
    metadata = InspectRequest(
        ip_address=source_ip,
        method=request.method,
        path=path[:512],
        user_agent=request.headers.get("user-agent", "")[:512],
        request_count=request_count,
        payload_indicators=indicators,
        exempted_indicators=exempted,
        payload_excerpt=payload_excerpt,
        header_text=" ".join(
            request.headers.get(name, "") for name in ("authorization", "cookie", "referer")
        )[:8192],
    )
    inspection = await inspect_and_log(metadata, event_type="proxy")
    is_decoy = inspection.decision == Decision.REDIRECT_TO_DECOY
    upstream_url = settings.decoy_service_url if is_decoy else settings.real_app_url
    decoy_context = (
        {
            "x-mirage-actor-hint": inspection.fingerprint_hash,
            "x-mirage-risk-score": f"{inspection.risk_score:.1f}",
        }
        if is_decoy
        else None
    )

    response = await forward_request(
        request,
        upstream_url=upstream_url,
        target_path=target_path,
        body=body,
        is_decoy=is_decoy,
        decoy_context=decoy_context,
    )
    if is_decoy:
        # Record what the decoy really issued, not what the gateway would issue.
        await record_canary_assignments(
            actor_hint=inspection.fingerprint_hash,
            decoy_type=inspection.decoy_type or "auto",
            source_path=metadata.path,
            response_text=response.body.decode("utf-8", errors="ignore"),
        )
    return response
