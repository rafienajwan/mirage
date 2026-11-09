"""Operator login, roster and audit endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from pydantic import BaseModel, Field

from app.core.security import (
    Operator,
    _api_key_header,
    _check_api_key,
    require_admin,
    require_operator,
)
from app.services import operators as operator_service
from app.storage import store

router = APIRouter(prefix="/operators", tags=["operators"])


class OperatorLoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


async def _require_api_key_only(api_key: str | None = Security(_api_key_header)) -> None:
    await _check_api_key(api_key)


@router.post("/login", dependencies=[Depends(_require_api_key_only)])
async def login(payload: OperatorLoginRequest):
    """Verify analyst credentials; the dashboard server then keeps the session."""
    operator = await operator_service.authenticate(payload.username, payload.password)
    if operator is None:
        await operator_service.audit(
            Operator("anonymous", "analyst"), "login_failed", payload.username.strip()[:32]
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    await operator_service.audit(operator, "login", operator.username)
    return {"username": operator.username, "role": operator.role}


@router.get("")
async def list_operators(_: Operator = Depends(require_operator)):
    """Enabled operators, for the assignee picker. Never includes credentials."""
    return {
        "operators": [
            {"username": record.username, "role": record.role}
            for record in await store.list_operators()
            if not record.disabled
        ]
    }


@router.get("/audit")
async def operator_audit(
    limit: int = Query(default=100, ge=1, le=500),
    _: Operator = Depends(require_admin),
):
    """Newest audit rows first."""
    entries = await store.get_audit(limit=limit)
    return {"entries": [entry.model_dump(mode="json") for entry in entries]}
