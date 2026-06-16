"""Project MIRAGE — FastAPI Gateway Application."""

from fastapi import FastAPI

from app.api.router import api_router, root_router
from app.core.config import settings
from app.core.cors import configure_cors

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description=(
        "AI-powered cyber deception defense gateway. "
        "Inspects API requests, calculates risk scores, and redirects "
        "suspicious traffic to safe decoy environments."
    ),
)

# CORS
configure_cors(app)

# Routers
app.include_router(root_router)
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.api_version,
        "docs": "/docs",
    }
