"""Health check endpoint."""

from fastapi import APIRouter

from app.core import config

router = APIRouter()


@router.get("/health")
async def health_check():
    """Service health check. Outside development it says nothing identifying."""
    settings = config.settings
    if settings.app_env != "development":
        return {"status": "ok"}
    return {
        "service": settings.app_name,
        "status": "healthy",
        "version": settings.api_version,
        "environment": settings.app_env,
    }
