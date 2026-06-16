"""Health check endpoint."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Service health check."""
    return {
        "service": settings.app_name,
        "status": "healthy",
        "version": settings.api_version,
        "environment": settings.app_env,
    }
