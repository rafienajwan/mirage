"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes import dashboard, decoy, health, inspect, simulate

api_router = APIRouter(prefix="/api/v1")

# Register sub-routers
api_router.include_router(inspect.router)
api_router.include_router(dashboard.router)
api_router.include_router(decoy.router)
api_router.include_router(simulate.router)

# Health check lives at root level (no /api/v1 prefix)
root_router = APIRouter()
root_router.include_router(health.router)
