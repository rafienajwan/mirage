"""Decoy response engine — generates safe fake responses.

All values returned are clearly fake demo placeholders. No real credentials,
tokens, or secrets are ever generated.
"""

from __future__ import annotations

from app.schemas.dashboard import DecoyResponse


# ── Safe fake data templates ─────────────────────────────────

_FAKE_LOGIN = {
    "status": "success",
    "user": {"id": 9999, "email": "fake_user_demo_only@mirage-decoy.io", "role": "admin"},
    "token": "mirage_demo_token_not_real_abc123",
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
    "database_url": "postgresql://decoy_demo:decoy_demo@localhost:5432/mirage_decoy",
    "secret_key": "decoy_config_demo_only_not_real",
    "debug": True,
    "note": "This is a MIRAGE decoy configuration — no real secrets are present.",
}

_FAKE_TOKEN = {
    "access_token": "mirage_demo_token_not_real_xyz789",
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


def generate_decoy_response(path: str, decoy_type: str = "auto") -> DecoyResponse:
    """Generate a safe fake response for a suspicious request."""
    if decoy_type == "auto":
        decoy_type = _infer_decoy_type(path)

    body = _DECOY_MAP.get(decoy_type, _FAKE_LOGIN)

    return DecoyResponse(
        decoy_type=decoy_type,
        status_code=200,
        body=body,
        note="This is a MIRAGE demo decoy response. No real data is included.",
    )
