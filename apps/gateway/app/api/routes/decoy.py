"""Decoy environment endpoints."""

from fastapi import APIRouter

from app.schemas.dashboard import DecoyResponse, DecoyResponseRequest, DecoyStatus
from app.services.decoy_engine import generate_decoy_response
from app.storage.memory_store import store
from app.utils.time import utcnow

router = APIRouter(prefix="/decoy", tags=["decoy"])

# Track decoy interactions
_decoy_counter = 0
_last_decoy_trigger = None


@router.get("/status", response_model=DecoyStatus)
async def decoy_status():
    """Current state of decoy environments."""
    fake_endpoints = [
        "/api/admin/users",
        "/api/config/settings",
        "/api/auth/login",
        "/api/internal/debug",
        "/api/token/refresh",
    ]
    return DecoyStatus(
        active_decoys=5,
        fake_endpoints=fake_endpoints,
        captured_interactions=store.decoy_redirects,
        last_decoy_trigger=_last_decoy_trigger,
    )


@router.post("/respond", response_model=DecoyResponse)
async def decoy_respond(request: DecoyResponseRequest):
    """Generate a safe fake response for a suspicious request."""
    global _decoy_counter, _last_decoy_trigger
    _decoy_counter += 1
    _last_decoy_trigger = utcnow()

    return generate_decoy_response(path=request.path, decoy_type=request.decoy_type)
