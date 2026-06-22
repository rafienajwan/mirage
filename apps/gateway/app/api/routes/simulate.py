"""Simulation endpoints — generate safe demo events for testing."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas.request import InspectRequest
from app.schemas.decision import InspectResponse
from app.services.inspection import inspect_and_log
from app.core.security import require_api_key

router = APIRouter(prefix="/simulate", tags=["simulate"])


async def _process_simulation(request: InspectRequest) -> InspectResponse:
    """Shared logic for processing a simulated request."""
    return await inspect_and_log(request, event_type="simulation")


@router.post(
    "/normal",
    response_model=InspectResponse,
    dependencies=[Depends(require_api_key)],
)
async def simulate_normal():
    """Generate a safe normal traffic event for demo purposes."""
    request = InspectRequest(
        ip_address="192.168.1.42",
        method="GET",
        path="/api/v1/products",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
        request_count=3,
        payload_indicators=[],
    )
    return await _process_simulation(request)


@router.post(
    "/suspicious",
    response_model=InspectResponse,
    dependencies=[Depends(require_api_key)],
)
async def simulate_suspicious():
    """Generate a safe suspicious traffic event for demo purposes."""
    request = InspectRequest(
        ip_address="10.0.0.99",
        method="POST",
        path="/.env",
        user_agent="sqlmap/1.7",
        request_count=85,
        payload_indicators=["sql-like", "path-traversal"],
    )
    return await _process_simulation(request)
