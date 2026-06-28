"""Synthetic API environment for contained suspicious traffic."""

from __future__ import annotations

import hashlib
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

app = FastAPI(title="Application API", docs_url=None, redoc_url=None, openapi_url=None)

_LOGIN_TOKEN = os.getenv("DECOY_LOGIN_TOKEN", "DECOY_LOGIN_TOKEN_NOT_CONFIGURED")
_OAUTH_TOKEN = os.getenv("DECOY_OAUTH_TOKEN", "DECOY_OAUTH_TOKEN_NOT_CONFIGURED")
_SERVICE_TOKEN = os.getenv("DECOY_SERVICE_TOKEN", "DECOY_SERVICE_TOKEN_NOT_CONFIGURED")
_DATABASE_URL = os.getenv("DECOY_DATABASE_URL", "postgresql://db:5432/decoy")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


def _assigned_token(actor_hint: str, token_kind: str) -> str:
    seed = f"{actor_hint}:{token_kind}:{_SERVICE_TOKEN}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"mirage-issued-{token_kind}-canary-{digest}"


def _variant_for(path: str, risk_score: float | None) -> str:
    lowered = path.lower()
    if risk_score is not None and risk_score >= 85:
        return "high_interaction"
    if "config" in lowered or ".env" in lowered or "db" in lowered or "sql" in lowered:
        return "credential_bait"
    if "login" in lowered or "auth" in lowered or "token" in lowered or "oauth" in lowered:
        return "token_bait"
    return "standard"


def _risk_score(request: Request) -> float | None:
    value = request.headers.get("x-mirage-risk-score")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _attach_metadata(payload: dict, request: Request, path: str) -> dict:
    actor_hint = request.headers.get("x-mirage-actor-hint", "")
    variant = _variant_for(path, _risk_score(request))
    payload["mirage_decoy"] = {
        "variant": variant,
        "safe": True,
        "note": "Synthetic data for deception telemetry only.",
    }
    if actor_hint:
        payload["mirage_assignment"] = {
            "mode": "per_actor",
            "tracking": "synthetic_canary",
        }
    return payload


def _fake_payload(path: str, request: Request) -> dict:
    lowered = path.lower()
    actor_hint = request.headers.get("x-mirage-actor-hint", "")
    if "login" in lowered or "auth" in lowered:
        return _attach_metadata({
            "status": "success",
            "user": {"id": 1042, "email": "admin@example.internal", "role": "admin"},
            "access_token": (
                _assigned_token(actor_hint, "login") if actor_hint else _LOGIN_TOKEN
            ),
        }, request, path)
    if "admin" in lowered or "users" in lowered:
        return _attach_metadata({
            "users": [
                {"id": 1042, "name": "System Admin", "role": "admin"},
                {"id": 1043, "name": "Service Account", "role": "service"},
            ],
            "page": 1,
        }, request, path)
    if "token" in lowered or "oauth" in lowered:
        return _attach_metadata({
            "access_token": (
                _assigned_token(actor_hint, "oauth") if actor_hint else _OAUTH_TOKEN
            ),
            "token_type": "bearer",
            "expires_in": 3600,
        }, request, path)
    if "db" in lowered or "sql" in lowered:
        payload = {
            "database": "application_prod",
            "tables": ["users", "orders", "audit_log"],
            "status": "connected",
        }
        if actor_hint:
            payload["connection_token"] = _assigned_token(actor_hint, "database")
        return _attach_metadata(payload, request, path)
    return _attach_metadata({"status": "ok", "path": path, "result": []}, request, path)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def decoy_route(path: str, request: Request) -> Response:
    full_path = "/" + path
    lowered = full_path.lower()
    actor_hint = request.headers.get("x-mirage-actor-hint", "")
    service_token = (
        _assigned_token(actor_hint, "service") if actor_hint else _SERVICE_TOKEN
    )
    if lowered.endswith("/.env") or lowered == "/.env":
        return PlainTextResponse(
            f"APP_ENV=production\nDATABASE_URL={_DATABASE_URL}\n"
            f"SERVICE_TOKEN={service_token}\n"
            f"MIRAGE_DECOY_VARIANT={_variant_for(full_path, _risk_score(request))}\n"
        )
    payload = _fake_payload(full_path, request)
    status_code = 201 if request.method == "POST" else 200
    return JSONResponse(payload, status_code=status_code)
