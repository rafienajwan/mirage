"""Browsers may call the gateway only from the dashboard origin outside development."""

import dataclasses

from app.core import config
from app.core.cors import allowed_origins

DASHBOARD = "https://mirage-dashboard.example.test"


def _settings(app_env):
    return dataclasses.replace(config.settings, app_env=app_env, frontend_origin=DASHBOARD)


def test_production_allows_only_the_dashboard_origin():
    assert allowed_origins(_settings("production")) == [DASHBOARD]


def test_development_also_allows_local_dev_servers():
    origins = allowed_origins(_settings("development"))
    assert origins[0] == DASHBOARD
    assert "http://localhost:3000" in origins


def test_trailing_slash_is_dropped():
    settings = dataclasses.replace(_settings("production"), frontend_origin=DASHBOARD + "/")
    assert allowed_origins(settings) == [DASHBOARD]
