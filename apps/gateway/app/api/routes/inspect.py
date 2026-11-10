"""Request metadata inspection endpoint."""

from fastapi import APIRouter, Depends

from app.core.security import require_operator
from app.schemas.decision import InspectResponse
from app.schemas.request import InspectRequest
from app.services.inspection import inspect_and_log

router = APIRouter()


@router.post(
    "/inspect",
    response_model=InspectResponse,
    dependencies=[Depends(require_operator)],
)
async def inspect_request(request: InspectRequest) -> InspectResponse:
    """Inspect submitted request metadata and return a security decision."""
    return await inspect_and_log(request)
