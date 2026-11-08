"""Authentication helpers for operator API operations."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core import config

_api_key_header = APIKeyHeader(name="X-Mirage-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Require the API key; without one configured, only development is open."""
    expected = config.settings.api_key
    if expected is None:
        if config.settings.app_env == "development":
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured",
        )
    if api_key is None or not secrets.compare_digest(api_key, expected):
        if config.settings.app_env != "development":
            # The operator API shares the attacker-facing port: without the key,
            # look exactly like a path that does not exist.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid MIRAGE API key",
        )
