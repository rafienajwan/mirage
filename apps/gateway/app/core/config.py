"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Attempt to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "Project MIRAGE Gateway")
    )
    api_version: str = field(
        default_factory=lambda: os.getenv("API_VERSION", "0.1.0")
    )
    frontend_origin: str = field(
        default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    )
    risk_threshold: float = field(
        default_factory=lambda: float(os.getenv("RISK_THRESHOLD", "60"))
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./mirage.db"
        )
    )
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))


settings = Settings()
