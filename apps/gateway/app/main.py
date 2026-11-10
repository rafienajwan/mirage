"""Project MIRAGE — FastAPI Gateway Application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router, root_router
from app.core import config
from app.core.config import Settings
from app.core.cors import configure_cors
from app.core.rate_limit import configure_rate_limit
from app.core.settings_validation import validate_startup
from app.services.proxy_client import close_upstream_client, open_upstream_client
from app.storage.db.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config and create tables. Shutdown: dispose connections."""
    validate_startup(config.settings)
    await init_db()
    await open_upstream_client()
    yield
    await close_upstream_client()
    await close_db()


def create_app(settings: Settings) -> FastAPI:
    """Build the gateway.

    The attacker-facing proxy shares this port, so outside development nothing
    unauthenticated may describe the service: no docs, no OpenAPI schema and
    no root banner.
    """
    development = settings.app_env == "development"
    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        description=(
            "AI-powered cyber deception defense gateway. "
            "Inspects API requests, calculates risk scores, and redirects "
            "suspicious traffic to safe decoy environments."
        ),
        lifespan=lifespan,
        docs_url="/docs" if development else None,
        redoc_url="/redoc" if development else None,
        openapi_url="/openapi.json" if development else None,
    )

    configure_cors(app, settings)
    configure_rate_limit(app)

    app.include_router(root_router)
    app.include_router(api_router)

    if development:

        @app.get("/")
        async def root():
            """Root endpoint (development only)."""
            return {
                "service": settings.app_name,
                "version": settings.api_version,
                "docs": "/docs",
            }

    return app


app = create_app(config.settings)
