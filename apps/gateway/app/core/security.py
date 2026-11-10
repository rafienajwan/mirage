"""Authentication helpers for operator API operations."""

from __future__ import annotations

from dataclasses import dataclass
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core import config
from app.schemas.operator import OperatorRole
from app.storage import store

_api_key_header = APIKeyHeader(name="X-Mirage-API-Key", auto_error=False)
_operator_header = APIKeyHeader(name="X-Mirage-Operator", auto_error=False)


@dataclass(frozen=True)
class Operator:
    """The authenticated caller of an operator API request."""

    username: str
    role: OperatorRole


API_KEY_OPERATOR = Operator("api-key", "admin")


def _refusal() -> HTTPException:
    """The response for a missing/invalid credential in the current environment."""
    if config.settings.app_env != "development":
        # The operator API shares the attacker-facing port: without the key,
        # look exactly like a path that does not exist.
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid MIRAGE API key",
    )


async def _check_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Require the API key; without one configured, only development is open."""
    expected = config.settings.api_key
    if expected is None:
        if config.settings.app_env == "development":
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured",
        )
    # Bytes: compare_digest rejects non-ASCII str, and headers are attacker input.
    if api_key is None or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise _refusal()


async def require_operator(
    api_key: str | None = Security(_api_key_header),
    operator: str | None = Security(_operator_header),
) -> Operator:
    """Resolve the caller: the API key alone is the shared admin identity."""
    await _check_api_key(api_key)
    if not operator:
        return API_KEY_OPERATOR
    record = await store.get_operator(operator.strip().lower())
    if record is None or record.disabled:
        raise _refusal()
    return Operator(record.username, record.role)


async def require_admin(operator: Operator = Depends(require_operator)) -> Operator:
    if operator.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return operator
