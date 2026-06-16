"""CORS middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

ALLOWED_ORIGINS = [
    settings.frontend_origin,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
