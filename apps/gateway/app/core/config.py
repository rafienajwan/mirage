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
    anomaly_redirect_confidence: float = field(
        default_factory=lambda: float(os.getenv("ANOMALY_REDIRECT_CONFIDENCE", "0.5"))
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./mirage.db"
        )
    )
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    api_key: str | None = field(
        default_factory=lambda: os.getenv("MIRAGE_API_KEY") or None
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    )
    real_app_url: str = field(
        default_factory=lambda: os.getenv("REAL_APP_URL", "http://localhost:8001")
    )
    decoy_service_url: str = field(
        default_factory=lambda: os.getenv("DECOY_SERVICE_URL", "http://localhost:8002")
    )
    proxy_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("PROXY_TIMEOUT_SECONDS", "10"))
    )
    proxy_max_body_bytes: int = field(
        default_factory=lambda: int(os.getenv("PROXY_MAX_BODY_BYTES", "1048576"))
    )
    ml_model_artifact: str | None = field(
        default_factory=lambda: os.getenv("MIRAGE_MODEL_ARTIFACT") or None
    )
    ml_shadow_monitor_threshold: float = field(
        default_factory=lambda: float(os.getenv("ML_SHADOW_MONITOR_THRESHOLD", "0.35"))
    )
    ml_shadow_redirect_threshold: float = field(
        default_factory=lambda: float(os.getenv("ML_SHADOW_REDIRECT_THRESHOLD", "0.65"))
    )
    decoy_login_token: str = field(
        default_factory=lambda: os.getenv(
            "DECOY_LOGIN_TOKEN", "DECOY_LOGIN_TOKEN_NOT_CONFIGURED"
        )
    )
    decoy_oauth_token: str = field(
        default_factory=lambda: os.getenv(
            "DECOY_OAUTH_TOKEN", "DECOY_OAUTH_TOKEN_NOT_CONFIGURED"
        )
    )
    decoy_service_token: str = field(
        default_factory=lambda: os.getenv(
            "DECOY_SERVICE_TOKEN", "DECOY_SERVICE_TOKEN_NOT_CONFIGURED"
        )
    )
    decoy_database_url: str = field(
        default_factory=lambda: os.getenv(
            "DECOY_DATABASE_URL", "postgresql://db:5432/decoy"
        )
    )


settings = Settings()
