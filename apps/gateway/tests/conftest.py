"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.memory_store import store


@pytest.fixture(autouse=True)
def clear_store():
    """Reset in-memory store between tests."""
    store.events.clear()
    store.alerts.clear()
    store._alert_counter = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)
