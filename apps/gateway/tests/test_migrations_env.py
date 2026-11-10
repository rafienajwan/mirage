"""Alembic must run against a URL containing percent-encoded characters."""

import dataclasses
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core import config

GATEWAY = Path(__file__).resolve().parents[1]


def test_upgrade_head_with_percent_in_url(tmp_path, monkeypatch):
    # Supabase passwords are URL-encoded (p%40ss); a SQLite path stands in.
    db_dir = tmp_path / "pct%40dir"
    db_dir.mkdir()
    url = f"sqlite+aiosqlite:///{(db_dir / 'm.db').as_posix()}"
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, database_url=url))
    alembic_config = Config(str(GATEWAY / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(GATEWAY / "migrations"))

    command.upgrade(alembic_config, "head")

    head = ScriptDirectory.from_config(alembic_config).get_current_head()
    engine = create_engine(f"sqlite:///{(db_dir / 'm.db').as_posix()}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
    engine.dispose()
