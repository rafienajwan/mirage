"""Synthetic API environment for contained suspicious traffic."""

from __future__ import annotations

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


def _fake_payload(path: str) -> dict:
    lowered = path.lower()
    if "login" in lowered or "auth" in lowered:
        return {
            "status": "success",
            "user": {"id": 1042, "email": "admin@example.internal", "role": "admin"},
            "access_token": _LOGIN_TOKEN,
        }
    if "admin" in lowered or "users" in lowered:
        return {
            "users": [
                {"id": 1042, "name": "System Admin", "role": "admin"},
                {"id": 1043, "name": "Service Account", "role": "service"},
            ],
            "page": 1,
        }
    if "token" in lowered or "oauth" in lowered:
        return {
            "access_token": _OAUTH_TOKEN,
            "token_type": "bearer",
            "expires_in": 3600,
        }
    if "db" in lowered or "sql" in lowered:
        return {
            "database": "application_prod",
            "tables": ["users", "orders", "audit_log"],
            "status": "connected",
        }
    return {"status": "ok", "path": path, "result": []}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def decoy_route(path: str, request: Request) -> Response:
    full_path = "/" + path
    lowered = full_path.lower()
    if lowered.endswith("/.env") or lowered == "/.env":
        return PlainTextResponse(
            f"APP_ENV=production\nDATABASE_URL={_DATABASE_URL}\n"
            f"SERVICE_TOKEN={_SERVICE_TOKEN}\n"
        )
    payload = _fake_payload(full_path)
    status_code = 201 if request.method == "POST" else 200
    return JSONResponse(payload, status_code=status_code)
