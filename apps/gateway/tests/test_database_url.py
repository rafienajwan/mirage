"""Connection strings pasted from Supabase must work with the asyncpg engine."""

import pytest

from app.core.config import Settings
from app.core.database_url import normalize_database_url

ENCODED = "postgres.abc:p%40ss%2Fw0rd@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_plain_schemes_use_asyncpg(scheme):
    assert (
        normalize_database_url(f"{scheme}://{ENCODED}")
        == f"postgresql+asyncpg://{ENCODED}"
    )


def test_encoded_password_is_untouched():
    assert "p%40ss%2Fw0rd" in normalize_database_url(f"postgresql://{ENCODED}")


def test_sslmode_becomes_ssl():
    assert normalize_database_url(f"postgresql://{ENCODED}?sslmode=require") == (
        f"postgresql+asyncpg://{ENCODED}?ssl=require"
    )


def test_other_parameters_keep_their_order():
    url = f"postgresql+asyncpg://{ENCODED}?application_name=mirage&sslmode=verify-full&x=1"
    assert normalize_database_url(url) == (
        f"postgresql+asyncpg://{ENCODED}?application_name=mirage&ssl=verify-full&x=1"
    )


def test_explicit_ssl_wins_over_sslmode():
    url = f"postgresql://{ENCODED}?sslmode=disable&ssl=require"
    assert normalize_database_url(url) == f"postgresql+asyncpg://{ENCODED}?ssl=require"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "memory",
        "sqlite+aiosqlite:///./mirage.db",
        "sqlite+aiosqlite:///:memory:",
        f"postgresql+asyncpg://{ENCODED}",
        f"postgresql+asyncpg://{ENCODED}?ssl=require",
    ],
)
def test_supported_urls_pass_through(url):
    assert normalize_database_url(url) == url


def test_settings_normalize_the_environment_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"postgres://{ENCODED}?sslmode=require")
    assert Settings().database_url == f"postgresql+asyncpg://{ENCODED}?ssl=require"
