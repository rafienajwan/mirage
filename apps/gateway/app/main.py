"""Project MIRAGE — FastAPI Gateway Application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router, root_router
from app.core.config import settings
from app.core.cors import configure_cors
from app.core.rate_limit import configure_rate_limit
from app.storage.db.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: dispose connections."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description=(
        "AI-powered cyber deception defense gateway. "
        "Inspects API requests, calculates risk scores, and redirects "
        "suspicious traffic to safe decoy environments."
    ),
    lifespan=lifespan,
)

# CORS
configure_cors(app)
configure_rate_limit(app)

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
