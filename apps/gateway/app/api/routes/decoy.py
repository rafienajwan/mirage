"""Decoy environment endpoints."""

from fastapi import APIRouter

from app.schemas.dashboard import DecoyResponse, DecoyResponseRequest, DecoyStatus
from app.services.decoy_engine import generate_decoy_response, FAKE_ENDPOINTS
from app.storage import store

router = APIRouter(prefix="/decoy", tags=["decoy"])


@router.get("/status", response_model=DecoyStatus)
async def decoy_status():
    """Current state of decoy environments."""
    return DecoyStatus(
        active_decoys=len(FAKE_ENDPOINTS),
        fake_endpoints=FAKE_ENDPOINTS,
        captured_interactions=await store.get_decoy_redirects(),
        last_decoy_trigger=await store.get_last_decoy_trigger(),
    )


@router.post("/respond", response_model=DecoyResponse)
async def decoy_respond(request: DecoyResponseRequest):
    """Generate a safe fake response for a suspicious request."""
    return generate_decoy_response(path=request.path, decoy_type=request.decoy_type)
