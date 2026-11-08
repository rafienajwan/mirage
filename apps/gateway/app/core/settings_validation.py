"""Refuse to start a production gateway that is misconfigured.

Messages name the offending variable, never its value, so startup logs do not
leak secrets.
"""

from __future__ import annotations

from app.core.client_ip import parse_trusted_proxies
from app.core.config import Settings
from app.services.payload_exemptions import parse_exemptions

MIN_SECRET_LENGTH = 32

_DECOY_TOKENS = (
    ("decoy_login_token", "DECOY_LOGIN_TOKEN"),
    ("decoy_oauth_token", "DECOY_OAUTH_TOKEN"),
    ("decoy_service_token", "DECOY_SERVICE_TOKEN"),
)


def _is_memory_sqlite(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("sqlite") and (":memory:" in lowered or "mode=memory" in lowered)


def production_config_errors(settings: Settings) -> list[str]:
    errors: list[str] = []
    if not settings.api_key or len(settings.api_key) < MIN_SECRET_LENGTH:
        errors.append(f"MIRAGE_API_KEY must be set to at least {MIN_SECRET_LENGTH} characters")
    secret = settings.dashboard_stream_ticket_secret
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        errors.append(
            f"MIRAGE_DASHBOARD_TICKET_SECRET must be set to at least {MIN_SECRET_LENGTH} characters"
        )
    for field_name, variable in _DECOY_TOKENS:
        if getattr(settings, field_name) == f"{variable}_NOT_CONFIGURED":
            errors.append(f"{variable} must be set; the placeholder default is not allowed")
    if _is_memory_sqlite(settings.database_url):
        errors.append("DATABASE_URL must not be an in-memory SQLite database")
    if settings.ml_model_artifact and not settings.ml_model_artifact_sha256:
        errors.append("MIRAGE_MODEL_ARTIFACT_SHA256 must be set when MIRAGE_MODEL_ARTIFACT is set")
    try:
        parse_trusted_proxies(settings.trusted_proxies)
    except ValueError:
        errors.append("TRUSTED_PROXIES must list IP addresses or CIDR ranges")
    try:
        parse_exemptions(settings.payload_exemptions)
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def validate_startup(settings: Settings) -> None:
    """Raise RuntimeError listing every problem when running in production."""
    if settings.app_env != "production":
        return
    errors = production_config_errors(settings)
    if errors:
        raise RuntimeError(
            "Invalid production configuration:\n" + "\n".join(f"- {e}" for e in errors)
        )
