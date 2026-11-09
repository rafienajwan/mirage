"""Decoy environment endpoints."""

from fastapi import APIRouter, Depends

from app.core.security import require_operator
from app.schemas.dashboard import DecoyResponse, DecoyResponseRequest, DecoyStatus
from app.services.canary_assignments import record_canary_assignments
from app.services.decoy_engine import FAKE_ENDPOINTS, generate_decoy_response
from app.storage import store

router = APIRouter(prefix="/decoy", tags=["decoy"])


@router.get(
    "/status",
    response_model=DecoyStatus,
    dependencies=[Depends(require_operator)],
)
async def decoy_status():
    """Current state of decoy environments."""
    return DecoyStatus(
        active_decoys=len(FAKE_ENDPOINTS),
        fake_endpoints=FAKE_ENDPOINTS,
        captured_interactions=await store.get_decoy_redirects(),
        last_decoy_trigger=await store.get_last_decoy_trigger(),
    )


@router.post(
    "/respond",
    response_model=DecoyResponse,
    dependencies=[Depends(require_operator)],
)
async def decoy_respond(request: DecoyResponseRequest):
    """Generate a safe fake response for a suspicious request."""
    response = generate_decoy_response(
        path=request.path,
        decoy_type=request.decoy_type,
        actor_hint=request.actor_hint,
        risk_score=request.risk_score,
    )
    await record_canary_assignments(
        actor_hint=request.actor_hint,
        decoy_type=response.decoy_type,
        source_path=request.path,
        response_text=response.model_dump_json(),
    )
    return response
