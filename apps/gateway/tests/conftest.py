"""Shared test fixtures."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

# Force in-memory SQLite for tests BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.main import app  # noqa: E402
from app.storage.db.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
async def setup_db():
    """Create fresh tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
"""Shared test fixtures."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

# Force in-memory SQLite for tests BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.main import app  # noqa: E402
from app.storage.db.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
async def setup_db():
    """Create fresh tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
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
