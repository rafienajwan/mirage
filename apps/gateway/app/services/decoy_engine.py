"""Decoy response engine — generates safe fake responses.

All values returned are clearly fake demo placeholders. No real credentials,
tokens, or secrets are ever generated.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib

from app.core.config import settings
from app.schemas.dashboard import DecoyResponse


# ── Safe fake data templates ─────────────────────────────────

_FAKE_LOGIN = {
    "status": "success",
    "user": {"id": 9999, "email": "fake_user_demo_only@mirage-decoy.io", "role": "admin"},
    "token": settings.decoy_login_token,
    "expires_in": 3600,
}

_FAKE_ADMIN = {
    "panel": "admin_dashboard",
    "users": [
        {"id": 1, "name": "Demo User A", "email": "demo_a@mirage-decoy.io"},
        {"id": 2, "name": "Demo User B", "email": "demo_b@mirage-decoy.io"},
    ],
    "settings": {"maintenance_mode": False, "decoy_active": True},
}

_FAKE_CONFIG = {
    "app_name": "mirage_decoy_app",
    "database_url": settings.decoy_database_url,
    "secret_key": settings.decoy_service_token,
    "debug": True,
    "note": "This is a MIRAGE decoy configuration — no real secrets are present.",
}

_FAKE_TOKEN = {
    "access_token": settings.decoy_oauth_token,
    "token_type": "bearer",
    "scope": "read write admin",
    "note": "This token is a MIRAGE demo value and cannot be used anywhere.",
}

_FAKE_DATABASE = {
    "tables": ["users", "orders", "products"],
    "users_count": 42,
    "sample_row": {
        "id": 1,
        "username": "decoy_admin",
        "password_hash": "demo_hash_not_real_do_not_use",
        "email": "decoy@mirage-demo.io",
    },
    "note": "This is a MIRAGE decoy database response — all data is fabricated.",
}

# Map path hints to decoy types
_DECOY_MAP: dict[str, dict] = {
    "login": _FAKE_LOGIN,
    "admin": _FAKE_ADMIN,
    "config": _FAKE_CONFIG,
    "token": _FAKE_TOKEN,
    "database": _FAKE_DATABASE,
}

_TOKEN_FIELDS = {
    "login": ("token", "login"),
    "config": ("secret_key", "service"),
    "token": ("access_token", "oauth"),
}

# Protected fake endpoints served by the decoy system
FAKE_ENDPOINTS: list[str] = [
    "/api/admin/users",
    "/api/config/settings",
    "/api/auth/login",
    "/api/internal/debug",
    "/api/token/refresh",
]


def _infer_decoy_type(path: str) -> str:
    """Guess the best decoy type from the request path."""
    path_lower = path.lower()
    if "login" in path_lower or "auth" in path_lower:
        return "login"
    if "admin" in path_lower:
        return "admin"
    if "config" in path_lower or ".env" in path_lower:
        return "config"
    if "token" in path_lower or "oauth" in path_lower:
        return "token"
    if "db" in path_lower or "database" in path_lower or "sql" in path_lower:
        return "database"
    # Default fallback
    return "login"


def _variant_for(decoy_type: str, risk_score: float | None) -> str:
    if risk_score is not None and risk_score >= 85:
        return "high_interaction"
    if decoy_type in {"config", "database"}:
        return "credential_bait"
    if decoy_type in {"login", "token"}:
        return "token_bait"
    return "standard"


def _assigned_token(actor_hint: str, token_kind: str) -> str:
    seed = f"{actor_hint}:{token_kind}:{settings.decoy_service_token}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"mirage-issued-{token_kind}-canary-{digest}"


def _apply_actor_assignment(body: dict, decoy_type: str, actor_hint: str) -> dict:
    if not actor_hint:
        return body

    assignment = _TOKEN_FIELDS.get(decoy_type)
    if assignment is not None:
        field, token_kind = assignment
        body[field] = _assigned_token(actor_hint, token_kind)

    if decoy_type == "database":
        body["connection_token"] = _assigned_token(actor_hint, "database")

    body["mirage_assignment"] = {
        "mode": "per_actor",
        "tracking": "synthetic_canary",
    }
    return body


def _apply_variant(body: dict, variant: str) -> dict:
    body["mirage_decoy"] = {
        "variant": variant,
        "safe": True,
        "note": "Synthetic data for deception telemetry only.",
    }
    if variant == "high_interaction":
        body["mirage_decoy"]["interaction_depth"] = "extended"
    return body


def generate_decoy_response(
    path: str,
    decoy_type: str = "auto",
    *,
    actor_hint: str = "",
    risk_score: float | None = None,
) -> DecoyResponse:
    """Generate a safe fake response for a suspicious request."""
    if decoy_type == "auto":
        decoy_type = _infer_decoy_type(path)

    variant = _variant_for(decoy_type, risk_score)
    body = deepcopy(_DECOY_MAP.get(decoy_type, _FAKE_LOGIN))
    body = _apply_actor_assignment(body, decoy_type, actor_hint)
    body = _apply_variant(body, variant)

    return DecoyResponse(
        decoy_type=decoy_type,
        variant=variant,
        status_code=200,
        body=body,
        note="This is a MIRAGE demo decoy response. No real data is included.",
    )
