"""CORS middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings

_LOCAL_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]


def allowed_origins(settings: Settings) -> list[str]:
    """The dashboard origin, plus local dev servers in development only."""
    origins = [settings.frontend_origin.rstrip("/")]
    if settings.app_env == "development":
        origins += [origin for origin in _LOCAL_DEV_ORIGINS if origin not in origins]
    return origins


def configure_cors(app: FastAPI, settings: Settings) -> None:
    """Attach CORS middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
