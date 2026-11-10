"""Production startup validation."""

import dataclasses

import pytest

from app.core import config
from app.core.settings_validation import production_config_errors, validate_startup
from app.main import app

KEY = "k" * 32
SECRET = "s" * 32


def _production(**overrides):
    values = {
        "app_env": "production",
        "api_key": KEY,
        "dashboard_stream_ticket_secret": SECRET,
        "decoy_login_token": "real-login-token",
        "decoy_oauth_token": "real-oauth-token",
        "decoy_service_token": "real-service-token",
        "database_url": "postgresql+asyncpg://db:5432/mirage",
        "ml_model_artifact": None,
        "ml_model_artifact_sha256": None,
        "trusted_proxies": "",
        "payload_exemptions": "",
    }
    values.update(overrides)
    return dataclasses.replace(config.settings, **values)


def _single_error(**overrides) -> str:
    errors = production_config_errors(_production(**overrides))
    assert len(errors) == 1, errors
    return errors[0]


def test_valid_production_config_has_no_errors():
    assert production_config_errors(_production()) == []
    assert production_config_errors(_production(database_url="sqlite+aiosqlite:///./m.db")) == []


@pytest.mark.parametrize(
    ("overrides", "variable", "secret"),
    [
        ({"api_key": None}, "MIRAGE_API_KEY", None),
        ({"api_key": "x" * 31}, "MIRAGE_API_KEY", "x" * 31),
        ({"dashboard_stream_ticket_secret": None}, "MIRAGE_DASHBOARD_TICKET_SECRET", None),
        (
            {"dashboard_stream_ticket_secret": "t" * 31},
            "MIRAGE_DASHBOARD_TICKET_SECRET",
            "t" * 31,
        ),
        (
            {"decoy_login_token": "DECOY_LOGIN_TOKEN_NOT_CONFIGURED"},
            "DECOY_LOGIN_TOKEN",
            None,
        ),
        (
            {"decoy_oauth_token": "DECOY_OAUTH_TOKEN_NOT_CONFIGURED"},
            "DECOY_OAUTH_TOKEN",
            None,
        ),
        (
            {"decoy_service_token": "DECOY_SERVICE_TOKEN_NOT_CONFIGURED"},
            "DECOY_SERVICE_TOKEN",
            None,
        ),
        ({"database_url": "sqlite+aiosqlite:///:memory:"}, "DATABASE_URL", None),
        (
            {"database_url": "sqlite+aiosqlite:///file:x?mode=memory&cache=shared&uri=true"},
            "DATABASE_URL",
            None,
        ),
        ({"ml_model_artifact": "/app/artifacts/m.joblib"}, "MIRAGE_MODEL_ARTIFACT_SHA256", None),
        ({"trusted_proxies": "nope-proxy"}, "TRUSTED_PROXIES", "nope-proxy"),
        ({"payload_exemptions": "POST /secret-route:bogus"}, "PAYLOAD_EXEMPTIONS", "secret-route"),
    ],
)
def test_each_problem_is_reported_without_its_value(overrides, variable, secret):
    message = _single_error(**overrides)
    assert variable in message
    if secret:
        assert secret not in message


def test_validate_startup_ignores_development():
    validate_startup(_production(app_env="development", api_key=None))


def test_validate_startup_raises_with_every_problem():
    with pytest.raises(RuntimeError) as exc:
        validate_startup(_production(api_key=None, dashboard_stream_ticket_secret=None))
    assert "MIRAGE_API_KEY" in str(exc.value)
    assert "MIRAGE_DASHBOARD_TICKET_SECRET" in str(exc.value)


async def test_lifespan_refuses_bad_production_config(monkeypatch):
    monkeypatch.setattr(config, "settings", _production(api_key=None))
    with pytest.raises(RuntimeError):
        async with app.router.lifespan_context(app):
            pass


POOLER = "aws-0-eu-west-1.pooler.supabase.com"


def test_supabase_transaction_pooler_is_refused():
    error = _single_error(
        database_url=f"postgresql+asyncpg://postgres.abc:hunter2-secret@{POOLER}:6543/postgres"
    )
    assert "DATABASE_URL" in error
    assert "5432" in error
    assert "hunter2-secret" not in error


def test_supabase_session_pooler_is_accepted():
    url = f"postgresql+asyncpg://postgres.abc:pw@{POOLER}:5432/postgres?ssl=require"
    assert production_config_errors(_production(database_url=url)) == []
